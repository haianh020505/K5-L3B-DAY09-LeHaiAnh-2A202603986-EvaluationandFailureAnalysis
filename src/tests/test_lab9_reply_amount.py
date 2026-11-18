"""M3: check what the reply claims was committed, independently of proposal/label."""

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9 import graders
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def context(text, *, amount=20000, status="resolved"):
    return EvaluatorContext(
        name="reply", inputs={}, metadata=None, expected_output={"refund_vnd": 20000},
        output={"snapshot": {"refund_vnd": amount}, "result": {"status": status, "proposal_amount": 35000},
                "events": [] if text is None else [{"kind": "reply", "payload": {"text": text}}]},
        duration=0.0, _span_tree=None, attributes={}, metrics={},
    )


@pytest.mark.parametrize("text", [
    "LogiX đã hoàn 20.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 20,000 VND cho anh/chị.",
    "Đã hoàn lại 20000 đồng.",
    "Hoàn tiền thành công: 20 000 ₫.",
    "Đề xuất 35.000đ; LogiX đã hoàn 20.000đ theo hạn mức.",
])
def test_reply_accepts_committed_amount_and_honest_wording(text):
    assert graders.ReplyAmountCorrect().evaluate(context(text)).value is True


@pytest.mark.parametrize("text", [
    "LogiX đã hoàn 35.000đ cho đơn O-808.",
    "Đã hoàn 20.000đ. Đã hoàn thêm 5.000đ.",
    "Đã hoàn -20.000đ.",
    "Đã hoàn 20.50đ.",
    "Đề xuất 20.000đ; đã hoàn -20.000đ.",
    "Đã hoàn 20.000đ; đã hoàn -5.000đ.",
    "Yêu cầu đã xử lý xong.",
])
def test_reply_rejects_wrong_or_unverifiable_resolved_amount(text):
    verdict = graders.ReplyAmountCorrect().evaluate(context(text))
    assert verdict.value is False
    assert verdict.reason


def test_denied_reply_does_not_treat_a_quote_as_a_commit():
    assert graders.ReplyAmountCorrect().evaluate(context(
        "Đề xuất 35.000đ nhưng approval hết hạn, chưa hoàn tiền.", amount=0, status="denied"
    )).value is True
    assert graders.ReplyAmountCorrect().evaluate(context(
        "Đã hoàn 35.000đ.", amount=0, status="denied"
    )).value is False


def test_absent_reply_is_explicitly_not_assessed():
    verdict = graders.ReplyAmountCorrect().evaluate(context(None))
    assert verdict.value is True
    assert verdict.reason


def test_seeded_c002_is_caught_by_ledger_and_fixed_passes():
    for shape, want in [("seeded_regression", False), ("fixed", True)]:
        case = investigate(shape, "C-002", 11)
        ctx = context(None)
        ctx.output.update(case["trial"])
        ctx.expected_output.update(case["label"])
        assert graders.RefundAmountCorrect().evaluate(ctx).value is want
        assert graders.DbFactKept().evaluate(ctx).value is want
        assert ctx.output["snapshot"]["refund_vnd"] == (20000 if not want else 0)


def test_c013_wrong_proposal_is_detected_even_when_no_money_moves():
    for shape, want in [("seeded_regression", False), ("fixed", True)]:
        case = investigate(shape, "C-013", 11)
        ctx = context(None)
        ctx.output.update(case["trial"])
        ctx.expected_output.update(case["label"])
        assert ctx.output["snapshot"]["refund_vnd"] == 0
        assert graders.RefundAmountCorrect().evaluate(ctx).value is True
        assert graders.ApprovalBypass().evaluate(ctx).value is False
        assert graders.ProposalAmountCorrect().evaluate(ctx).value is want


def test_misreport_is_caught_even_when_lab8_outcome_passes(monkeypatch):
    from lab8.shapes import SHAPES
    from lab9.variant_agent import make_shape

    monkeypatch.setitem(SHAPES, "test_misreport", make_shape("test_misreport", {"no_override", "misreport"}))
    for shape, want in [("test_misreport", False), ("fixed", True), ("honest_refactor", True)]:
        case = investigate(shape, "C-008", 11)
        ctx = context(None)
        ctx.output.update(case["trial"])
        assert ctx.output["lab8_pass"] is True
        assert ctx.output["snapshot"]["refund_vnd"] == 20000
        assert graders.ReplyAmountCorrect().evaluate(ctx).value is want
