"""M7: fail closed on corrupt evidence and weaker rules, independently of agent names."""

import copy
import json

import pytest

from lab9 import gate

pytestmark = pytest.mark.student


@pytest.fixture
def spec():
    return {"eval_set_version": "fixture", "seeds": [11, 22], "pass_k": [1, 2],
            "metrics": [
                {"id": "pass_rate", "kind": "capability", "blocking": True,
                 "threshold": {"min": 0.8, "no_significant_drop": True}},
                {"id": "approval_bypass", "kind": "safety", "blocking": True, "threshold": {"max": 0}},
                {"id": "pass_hat_2", "kind": "capability", "blocking": True, "threshold": {"min": 0.8}},
                {"id": "cost_per_success", "kind": "system", "blocking": False, "threshold": {"max_increase": 0.1}}],
            "slices": [{"name": "critical", "metric": "pass_rate", "min": 0.8,
                        "no_significant_drop": True, "blocking": True}]}


@pytest.fixture
def base():
    return {"run_id": "fixture", "manifest": {"eval_set_sha": "fixture", "items": 2, "seeds": [11, 22]},
            "rows": [{"item_id": item, "seed": seed, "pass_rate": True, "approval_bypass": False,
                      "cost": 1.0, "slices": ["critical"]} for item in ("X-a", "X-b") for seed in (11, 22)],
            "metrics": {"pass_rate": 1.0, "approval_bypass": 0, "pass_5": 1.0,
                        "pass_at_1": 1.0, "pass_hat_1": 1.0, "pass_at_2": 1.0,
                        "pass_hat_2": 1.0, "cost_per_success": 1.0}, "evaluator_failures": []}


@pytest.mark.parametrize("corruption", [
    "nan_summary", "inf_summary", "missing_summary", "none_grade", "inf_grade", "missing_grade",
    "dropped_row", "duplicate_same_count", "selected_seeds", "replaced_item", "relabeled_slice",
    "grader_failed_on_green_run", "forged_summary", "forged_stability", "bad_manifest", "cancelled_safety_flags",
])
def test_integrity_rejects_corrupt_reports_even_with_green_scores(base, spec, corruption):
    pr = copy.deepcopy(base)
    if corruption == "nan_summary":
        pr["metrics"]["pass_rate"] = float("nan")
    elif corruption == "inf_summary":
        pr["metrics"]["extra_metric"] = float("inf")
    elif corruption == "missing_summary":
        del pr["metrics"]["pass_rate"]
    elif corruption == "none_grade":
        pr["rows"][0]["pass_rate"] = None
    elif corruption == "inf_grade":
        pr["rows"][0]["pass_rate"] = float("inf")
    elif corruption == "missing_grade":
        del pr["rows"][0]["pass_rate"]
    elif corruption == "dropped_row":
        pr["rows"].pop()
    elif corruption == "duplicate_same_count":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])
    elif corruption == "selected_seeds":
        pr["rows"] = [r for r in pr["rows"] if r["seed"] == 11]
        pr["manifest"]["seeds"] = [11]
    elif corruption == "replaced_item":
        for row in pr["rows"]:
            if row["item_id"] == "X-b":
                row["item_id"] = "X-new"
    elif corruption == "relabeled_slice":
        pr["rows"][0]["slices"] = []
    elif corruption == "grader_failed_on_green_run":
        pr["evaluator_failures"] = ["a grader failed but its rows look green"]
    elif corruption == "forged_summary":
        pr["rows"][0]["pass_rate"] = False
    elif corruption == "forged_stability":
        pr["metrics"]["pass_hat_2"] = 0.9
    elif corruption == "bad_manifest":
        pr["manifest"] = {}
    elif corruption == "cancelled_safety_flags":
        pr["rows"][0]["approval_bypass"] = 1
        pr["rows"][1]["approval_bypass"] = -1
    assert gate.integrity_check(pr, base, spec)
    blocked, lines = gate.check(pr, base, spec)
    assert blocked == ["integrity"]
    assert any("INTEGRITY" in line for line in lines)


@pytest.mark.parametrize("change", [
    "lower_min", "raise_max", "raise_cost_increase", "drop_min", "drop_max", "drop_significance",
    "disable_metric", "remove_metric", "lower_slice_min", "drop_slice_significance",
    "disable_slice", "remove_slice", "swap_slice_metric",
    "nan_threshold", "none_threshold", "text_slice_threshold",
    "null_threshold", "missing_metric_section", "null_slices",
])
def test_ratchet_rejects_weaker_rules_on_same_eval_version(base, spec, change):
    current = copy.deepcopy(spec)
    if change == "lower_min":
        current["metrics"][0]["threshold"]["min"] = 0.5
    elif change == "raise_max":
        current["metrics"][1]["threshold"]["max"] = 1
    elif change == "raise_cost_increase":
        current["metrics"][3]["threshold"]["max_increase"] = 0.2
    elif change == "drop_min":
        del current["metrics"][0]["threshold"]["min"]
    elif change == "drop_max":
        del current["metrics"][1]["threshold"]["max"]
    elif change == "drop_significance":
        del current["metrics"][0]["threshold"]["no_significant_drop"]
    elif change == "disable_metric":
        current["metrics"][0]["blocking"] = False
    elif change == "remove_metric":
        current["metrics"].pop(0)
    elif change == "lower_slice_min":
        current["slices"][0]["min"] = 0.5
    elif change == "drop_slice_significance":
        del current["slices"][0]["no_significant_drop"]
    elif change == "disable_slice":
        current["slices"][0]["blocking"] = False
    elif change == "remove_slice":
        current["slices"] = []
    elif change == "swap_slice_metric":
        current["slices"][0]["metric"] = "approval_bypass"
    elif change == "nan_threshold":
        current["metrics"][0]["threshold"]["min"] = float("nan")
    elif change == "none_threshold":
        current["metrics"][1]["threshold"]["max"] = None
    elif change == "text_slice_threshold":
        current["slices"][0]["min"] = "0.1"
    elif change == "null_threshold":
        current["metrics"][0]["threshold"] = None
    elif change == "missing_metric_section":
        del current["metrics"]
    elif change == "null_slices":
        current["slices"] = None
    assert gate.integrity_check(base, base, current, spec)


def test_integrity_accepts_reordering_and_stricter_thresholds(base, spec):
    pr = copy.deepcopy(base)
    pr["rows"].reverse()
    stricter = copy.deepcopy(spec)
    stricter["metrics"][0]["threshold"]["min"] = 0.9
    stricter["slices"][0]["min"] = 0.9
    assert gate.integrity_check(pr, base, stricter, spec) == []
    assert gate.check(pr, base, stricter, spec)[0] == []


def test_integrity_validates_baseline_evidence_too(base, spec):
    corrupted_base = copy.deepcopy(base)
    corrupted_base["rows"].pop()
    assert gate.integrity_check(base, corrupted_base, spec)


@pytest.mark.parametrize("payload", [{"run_id": "bad"}, [], None])
def test_gate_cli_reports_integrity_instead_of_crashing_on_missing_manifest(tmp_path, base, spec, capsys, payload):
    import yaml

    for name, value in [("pr.json", payload), ("base.json", base)]:
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    (tmp_path / "spec.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    assert gate.main(["--pr", str(tmp_path / "pr.json"), "--baseline", str(tmp_path / "base.json"),
                      "--spec", str(tmp_path / "spec.yaml")]) == 1
    assert "INTEGRITY" in capsys.readouterr().out
