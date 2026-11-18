"""Optional Inspect scorer port and offline, same-Trial comparison (Task 8)."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from importlib.metadata import version
import json
from pathlib import Path
import platform
import tempfile

from inspect_ai.model import ModelName
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState
from pydantic_evals.evaluators import EvaluatorContext

from lab8.console import utf8_stdio
from lab8.shapes import SHAPES
from lab9 import evalset, variants
from lab9.eval import load_spec, load_world, make_task
from lab9.graders import GRADERS, Label, Trial
from lab9.variant_agent import make_shape


def _native(metric: str, trial: Trial, label: Label):
    ctx = EvaluatorContext(name=metric, inputs={}, metadata=None, expected_output=label, output=trial,
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    return GRADERS[metric]().evaluate(ctx)


def _port(metric: str) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        label = json.loads(target.text)
        if not isinstance(label, dict):
            raise ValueError("Inspect target must contain a JSON label object")
        verdict = _native(metric, state.metadata["trial"], label)
        # Preserve native polarity: approval_bypass=1 is BAD; correctness=1 is GOOD.
        return Score(value=int(verdict.value), explanation=verdict.reason)

    return score


@scorer(metrics=[mean()])
def approval_bypass() -> Scorer:
    return _port("approval_bypass")


@scorer(metrics=[mean()])
def refund_amount_correct() -> Scorer:
    return _port("refund_amount_correct")


@scorer(metrics=[mean()])
def reply_amount_correct() -> Scorer:
    return _port("reply_amount_correct")


SCORERS = {"approval_bypass": approval_bypass, "refund_amount_correct": refund_amount_correct,
           "reply_amount_correct": reply_amount_correct}


async def compare_trial(trial: Trial, label: Label) -> dict:
    state = TaskState(model=ModelName("mockllm/model"), sample_id=trial["result"].get("run_id", "trial"),
                      epoch=1, input="", messages=[], metadata={"trial": trial})
    target = Target(json.dumps(label, ensure_ascii=False))
    native, inspected, mismatches = {}, {}, []
    for metric, factory in SCORERS.items():
        expected = _native(metric, trial, label)
        actual = await factory()(state, target)
        native[metric], inspected[metric] = int(expected.value), actual.value
        if actual.value != native[metric] or actual.explanation != expected.reason:
            mismatches.append(metric)
    return {"native": native, "inspect": inspected, "mismatched_metrics": mismatches,
            "reply_assessed": any(e.get("kind") == "reply" for e in trial["events"])}


async def run_comparison(spec: dict) -> dict:
    items = evalset.load_jsonl(Path(spec["eval_set"]))
    labels = json.loads(Path(spec["labels"]).read_text(encoding="utf-8"))
    if not items or not spec["seeds"]:
        raise ValueError("comparison needs non-empty items and seeds")
    world, claims = load_world(spec)
    variants.register()
    # Exercise the two missing positive branches without editing provided variant files.
    SHAPES["bonus_misreport"] = make_shape("bonus_misreport", {"no_override", "misreport"})
    SHAPES["bonus_sibling_refund"] = make_shape("bonus_sibling_refund", {"no_override", "sibling_refund"})
    shapes = ["swarm", *variants.VARIANTS, "bonus_misreport", "bonus_sibling_refund"]
    rows = []
    with tempfile.TemporaryDirectory(prefix="lab9-inspect-", ignore_cleanup_errors=True) as folder:
        for shape in shapes:
            task = make_task(shape, world, claims, labels, Path(folder))
            for item in items:
                for seed in spec["seeds"]:
                    trial = task({"claim_id": item["claim_id"], "seed": seed})
                    if trial["result"].get("status") == "error":
                        raise RuntimeError(f"agent failed: {shape} {item['claim_id']}@{seed}")
                    row = await compare_trial(trial, labels[item["claim_id"]])
                    rows.append({"shape": shape, "item_id": item["item_id"], "claim_id": item["claim_id"],
                                 "seed": seed, **row})
    summary = {metric: {"comparisons": len(rows),
                        "mismatches": sum(metric in r["mismatched_metrics"] for r in rows),
                        "native_ones": sum(r["native"][metric] for r in rows),
                        "inspect_ones": sum(r["inspect"][metric] for r in rows)} for metric in SCORERS}
    sha = evalset.sha12(Path(spec["eval_set"]))
    return {"run_id": f"B-inspect-{date.today():%Y%m%d}-{sha[:4]}",
            "framework": {"inspect_ai": version("inspect-ai"), "pydantic_evals": version("pydantic-evals"),
                          "python": platform.python_version()},
            "eval_set_sha": sha, "eval_set_version": spec["eval_set_version"],
            "seeds": spec["seeds"], "shapes": shapes, "trials": len(rows),
            "comparisons": len(rows) * len(SCORERS), "metrics": summary,
            "mismatches": sum(s["mismatches"] for s in summary.values()),
            "reply_not_assessed": sum(not r["reply_assessed"] for r in rows), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(prog="lab9.inspect_bonus")
    parser.add_argument("--spec", default="config/metric_spec_v2.yaml")
    parser.add_argument("--out", default="reports/bonus_inspect_v2.json")
    args = parser.parse_args(argv)
    report = asyncio.run(run_comparison(load_spec(Path(args.spec))))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"{report['run_id']}: {report['trials']} trials, {report['comparisons']} comparisons, "
          f"{report['mismatches']} mismatches; wrote {out}")
    return 1 if report["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
