"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _report_problems(report: dict, spec: dict) -> list[str]:
    if not isinstance(report, dict):
        return ["report must be an object"]
    manifest, rows, metrics = (report.get(k) for k in ("manifest", "rows", "metrics"))
    if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(metrics, dict):
        return ["manifest, rows or metrics missing/invalid"]
    if not isinstance(report.get("evaluator_failures"), list) or report["evaluator_failures"]:
        return ["evaluator_failures missing/invalid or non-empty"]
    items, seeds = manifest.get("items"), manifest.get("seeds")
    if (type(items) is not int or items < 1 or not isinstance(seeds, list) or not seeds
            or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)):
        return ["invalid item count or seed manifest"]
    if "seeds" in spec and set(seeds) != set(spec["seeds"]):
        return ["manifest seeds differ from the metric spec"]
    if not isinstance(manifest.get("eval_set_sha"), str) or not manifest["eval_set_sha"]:
        return ["eval_set_sha missing/invalid"]
    if len(rows) != items * len(seeds):
        return ["row count differs from manifest items x seeds"]
    required = {m["id"] for m in spec["metrics"]}
    finite = lambda value: isinstance(value, (int, float)) and math.isfinite(value)
    if not required <= metrics.keys() or not all(finite(v) for v in metrics.values()):
        return ["aggregate metrics missing or non-finite"]
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS or m.get("grader") == "code"]
    keys, tags_by_item = [], {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or not row["item_id"]
                or type(row.get("seed")) is not int or row["seed"] not in seeds):
            return ["invalid row item_id/seed"]
        if any(not finite(row.get(mid)) or row[mid] not in (0, 1) for mid in graded):
            return ["row grader value missing, non-finite or not binary"]
        if ("cost" in row or "cost_per_success" in required) and not finite(row.get("cost")):
            return ["row cost missing or non-finite"]
        tags = row.get("slices", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            return ["invalid slice tags"]
        tags = frozenset(tags)
        item = row["item_id"]
        if item in tags_by_item and tags_by_item[item] != tags:
            return ["slice tags differ between seeds of the same item"]
        tags_by_item[item] = tags
        keys.append((item, row["seed"]))
    expected = {(item, seed) for item in tags_by_item for seed in seeds}
    if len(tags_by_item) != items or len(set(keys)) != len(keys) or set(keys) != expected:
        return ["duplicate or missing item/seed pairs"]
    ks = set(spec.get("pass_k", []))
    for mid in metrics:
        if mid.startswith(("pass_at_", "pass_hat_")) and mid.rsplit("_", 1)[1].isdigit():
            ks.add(int(mid.rsplit("_", 1)[1]))
    # Cost defaults only support fixtures/specs without a cost metric; required costs were checked above.
    recomputed = aggregate([{**r, "cost": r.get("cost", 0.0)} for r in rows], graded, k_values=sorted(ks))
    if any(value is None or not math.isclose(metrics[mid], value, rel_tol=0, abs_tol=1e-9)
           for mid, value in recomputed.items() if mid in metrics):
        return ["aggregate metrics disagree with row evidence"]
    return []


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    problems = []
    for section in ("metrics", "slices"):
        key = (lambda entry: entry["id"]) if section == "metrics" else (lambda entry: (entry["name"], entry["metric"]))
        current = {key(entry): entry for entry in spec.get(section, [])}
        if len(current) != len(spec.get(section, [])):
            problems.append(f"RATCHET duplicate {section}")
        for old in base_spec.get(section, []):
            identity = key(old)
            new = current.get(identity)
            if new is None:
                problems.append(f"RATCHET removed {section}:{identity}")
                continue
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"RATCHET disabled blocking {section}:{identity}")
            before = old.get("threshold", {}) if section == "metrics" else old
            after = new.get("threshold", {}) if section == "metrics" else new
            for bound in ("min", "max", "max_increase"):
                if bound in before and (bound not in after or
                        (after[bound] < before[bound] if bound == "min" else after[bound] > before[bound])):
                    problems.append(f"RATCHET loosened {bound} {section}:{identity}")
            if before.get("no_significant_drop") and not after.get("no_significant_drop"):
                problems.append(f"RATCHET removed no_significant_drop {section}:{identity}")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    for name, rules in (("spec", spec), ("base_spec", base_spec)):
        if rules is None:
            continue
        if (not isinstance(rules, dict) or not isinstance(rules.get("metrics"), list)
                or not rules["metrics"] or not isinstance(rules.get("slices", []), list)):
            problems.append(f"{name}: missing/invalid metric or slice definitions")
            continue
        for section in ("metrics", "slices"):
            for entry in rules.get(section, []):
                required = ("id",) if section == "metrics" else ("name", "metric")
                if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str) for k in required):
                    problems.append(f"{name}: invalid {section} definition")
                    continue
                thresholds = entry.get("threshold", {}) if section == "metrics" else entry
                if not isinstance(thresholds, dict):
                    problems.append(f"{name}: invalid {section} thresholds")
                    continue
                if any(not isinstance(value, (int, float)) or not math.isfinite(value)
                       for key, value in thresholds.items() if key in ("min", "max", "max_increase")):
                    problems.append(f"{name}: non-finite/invalid {section} threshold")
    if problems:
        return problems
    problems = [f"{name}: {problem}" for name, report, report_spec in
                (("PR", pr, spec), ("baseline", base, base_spec or spec))
                for problem in _report_problems(report, report_spec)]
    if problems:
        return problems
    pr_rows = {(r["item_id"], r["seed"]): frozenset(r.get("slices", [])) for r in pr["rows"]}
    base_rows = {(r["item_id"], r["seed"]): frozenset(r.get("slices", [])) for r in base["rows"]}
    if pr_rows.keys() != base_rows.keys():
        problems.append("PR item/seed set differs from baseline")
    elif pr_rows != base_rows:
        problems.append("PR slice tags differ from baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems.extend(_ratchet_problems(spec, base_spec))
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        failed, note = False, ""
        if not a or a.keys() != b.keys() or not all(math.isfinite(v) for v in (*a.values(), *b.values())):
            failed, note = True, "missing, non-finite or unpaired slice items"
            value = None
        else:
            value = sum(a.values()) / len(a)
            failed = "min" in s and value < s["min"]
            if s.get("no_significant_drop") and len(a) >= 2:
                keys = sorted(a)
                delta, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                note = f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed = failed or hi < 0
            elif s.get("no_significant_drop"):
                note = "CI not assessed: fewer than two items"
        if failed and s.get("blocking"):
            blocked.append(sid)
        verdict = "BLOCK" if failed and s.get("blocking") else "warn" if failed else "ok"
        lines.append(f"  {sid:<38} {value!s:<8} {note:<32} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    pr_info = pr if isinstance(pr, dict) else {}
    base_info = base if isinstance(base, dict) else {}
    manifest = pr_info.get("manifest") or {}
    sha = manifest.get("eval_set_sha", "<missing>") if isinstance(manifest, dict) else "<invalid>"
    print(f"gate: PR {pr_info.get('run_id', '<missing>')} vs main {base_info.get('run_id', '<missing>')} · eval set {sha}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
