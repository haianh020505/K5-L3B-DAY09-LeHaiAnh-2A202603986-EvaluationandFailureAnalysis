"""M5/M6 boundaries; M7 report integrity is deliberately a separate task."""

import pytest

from lab9 import gate, stats

pytestmark = pytest.mark.student


@pytest.mark.parametrize("fn", [stats.pass_at_k, stats.pass_hat_k])
@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 2, 0),
                                 (3, 1, 4), (5.0, 2, 1), (5, True, 1)])
def test_estimators_reject_invalid_trial_counts(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_estimators_distinguish_one_success_from_all_successes():
    assert stats.pass_at_k(5, 4, 5) == 1.0
    assert stats.pass_hat_k(5, 4, 5) == 0.0
    assert stats.pass_hat_k(5, 4, 3) == pytest.approx(0.4)
    assert stats.pass_hat_k(5, 4, 3) <= 4 / 5 <= stats.pass_at_k(5, 4, 3)


def report(values, *, slice_name="critical"):
    return {"rows": [{"item_id": f"X-{i}", "seed": seed, "pass_rate": value,
                      "slices": [slice_name]} for i, value in enumerate(values) for seed in (11, 22)]}


def test_slice_ci_blocks_a_paired_drop_even_above_floor():
    spec = {"slices": [{"name": "critical", "metric": "pass_rate", "min": 0.5,
                        "no_significant_drop": True, "blocking": True}]}
    pr = report([0.8, 0.8, 0.8, 0.8])
    pr["rows"].reverse()
    blocked, lines = gate.slice_check(pr, report([1, 1, 1, 1]), spec)
    assert blocked == ["slice:critical/pass_rate"]
    assert any("CI" in line for line in lines)


def test_slice_does_not_block_unchanged_or_improved_results():
    spec = {"slices": [{"name": "critical", "metric": "pass_rate", "min": 0.5,
                        "no_significant_drop": True, "blocking": True}]}
    base = report([0.6, 0.8, 1, 1])
    assert gate.slice_check(base, base, spec)[0] == []
    assert gate.slice_check(report([1, 1, 1, 1]), base, spec)[0] == []


def test_missing_or_unpaired_blocking_slice_does_not_silently_pass():
    spec = {"slices": [{"name": "critical", "metric": "pass_rate", "min": 0.9, "blocking": True}]}
    for pr in (report([], slice_name="other"), report([1])):
        assert gate.slice_check(pr, report([1, 1]), spec)[0] == ["slice:critical/pass_rate"]


def test_nonblocking_slice_warns_without_blocking():
    spec = {"slices": [{"name": "critical", "metric": "pass_rate", "min": 0.9, "blocking": False}]}
    blocked, lines = gate.slice_check(report([0, 0]), report([1, 1]), spec)
    assert blocked == []
    assert lines
