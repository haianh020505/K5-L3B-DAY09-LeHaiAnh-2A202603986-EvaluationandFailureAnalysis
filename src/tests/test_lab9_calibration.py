"""M2 edge cases and replay calibration, separate from the M4 bootstrap tests."""

from pathlib import Path
import math

import pytest

from lab9 import stats
from lab9.judge import calibrate

pytestmark = pytest.mark.student


@pytest.mark.parametrize("human,judge", [(["PASS"], []), (["UNKNOWN"], ["PASS"]), (["PASS"], ["FAIL "])])
def test_confusion_rejects_unpaired_or_unknown_labels(human, judge):
    with pytest.raises(ValueError):
        stats.confusion(human, judge)


def test_precision_recall_zero_denominators():
    assert stats.precision_recall(["PASS"], ["PASS"]) == (0.0, 0.0)
    assert stats.precision_recall(["FAIL"], ["PASS"]) == (0.0, 0.0)


def test_kappa_empty_has_no_calibration_signal():
    with pytest.raises(ValueError):
        stats.cohen_kappa([], [])


def test_kappa_perfect_agreement_and_disagreement():
    assert stats.cohen_kappa(["PASS", "FAIL"], ["PASS", "FAIL"]) == 1.0
    assert stats.cohen_kappa(["PASS", "FAIL"], ["FAIL", "PASS"]) == -1.0


def test_rogan_gladen_upper_clip_and_unidentifiable_rate():
    assert stats.rogan_gladen(1.0, 0.8, 0.9) == 1.0
    with pytest.raises(ValueError):
        stats.rogan_gladen(0.4, 0.5, 0.5)


@pytest.mark.parametrize("rates", [(-0.1, 0.8, 0.9), (0.3, 1.1, 0.9), (0.3, 0.8, float("nan"))])
def test_rogan_gladen_rejects_invalid_rates(rates):
    with pytest.raises(ValueError):
        stats.rogan_gladen(*rates)


def test_helpful_replay_is_rejected_despite_perfect_precision():
    result = calibrate(Path("data/eval/judge_helpful_public.csv"))
    assert result["confusion"] == {"tp": 9, "fp": 0, "fn": 21, "tn": 70}
    assert result["precision"] == 1.0
    assert result["recall"] == 0.3
    assert result["kappa"] == 0.375
    assert result["passed"] is False


def test_constant_replay_fails_floors_without_a_corrected_rate(tmp_path):
    path = tmp_path / "constant.csv"
    path.write_text("item_id,reply,human,judge\nX-1,OK,PASS,PASS\n", encoding="utf-8")
    result = calibrate(path)
    assert result["passed"] is False
    assert math.isnan(result["kappa"])
    assert math.isnan(result["corrected_fail_rate"])
