from __future__ import annotations

from automation.investment_pipeline.rebase_decision_to_marks import rebase_decisions


def _controls() -> dict:
    return {"orders": 0, "trade_authority": "NONE"}


def test_mark_rebase_clears_stale_price_blocker_when_existing_position_crosses_entry_gate() -> None:
    comparison = {
        "controls": _controls(),
        "rows": [
            {
                "security_id": "601138.SH",
                "existing_position": True,
                "comparison_status": "PRICE_BLOCKED",
                "metrics": {
                    "current_price": 63.91,
                    "price_as_of": "2026-09-15",
                    "entry_price": 63.46,
                    "probability_weighted_value": 72.975,
                    "bear_value": 51.60,
                    "expected_return": 72.975 / 63.91 - 1.0,
                    "bear_downside": 51.60 / 63.91 - 1.0,
                    "confidence": "MEDIUM_HIGH",
                },
            }
        ],
    }
    recommendation = {
        "controls": _controls(),
        "summary": {},
        "records": [
            {
                "security_id": "601138.SH",
                "security_name": "工业富联",
                "action": "HOLD",
                "top_blocker": "PRICE_BLOCKED",
                "ready_for_user_decision": False,
                "top_reasons": [
                    "HOLD_RESEARCH_COMPLETE_CURRENT_MARK_NEAR_BUT_ABOVE_15PCT_ADD_HURDLE",
                    "D2_EXPLICIT_POSITION_ACTION_HOLD",
                    "PRICE_BLOCKED",
                    "D2_CAPITAL_RANK_5",
                ],
            }
        ],
    }
    marks = {
        "data_watermark": {"latest_mark_date": "2026-09-15"},
        "marks": [
            {
                "security_id": "601138.SH",
                "mark": 60.80,
                "as_of_date": "2026-09-15",
            }
        ],
    }

    rebased_comparison, rebased_recommendation = rebase_decisions(
        comparison, recommendation, marks, {"queue": []}
    )

    assert rebased_comparison["rows"][0]["comparison_status"] == "PASS_NEW_CAPITAL"
    record = rebased_recommendation["records"][0]
    assert record["action"] == "ADD"
    assert record["ready_for_user_decision"] is True
    assert record["top_blocker"] is None
    assert "PASS_NEW_CAPITAL" in record["top_reasons"]
    assert "PRICE_BLOCKED" not in record["top_reasons"]
    assert "D2_EXPLICIT_POSITION_ACTION_HOLD" not in record["top_reasons"]
    assert not any(str(reason).startswith("HOLD_") for reason in record["top_reasons"])
    assert "MARK_REBASE_ACTION_HOLD_TO_ADD" in record["top_reasons"]


def test_mark_rebase_preserves_price_blocker_when_gate_is_not_crossed() -> None:
    comparison = {
        "controls": _controls(),
        "rows": [
            {
                "security_id": "002832.SZ",
                "existing_position": False,
                "comparison_status": "PRICE_BLOCKED",
                "metrics": {
                    "current_price": 25.55,
                    "price_as_of": "2026-09-15",
                    "entry_price": 23.35,
                    "probability_weighted_value": 26.85,
                    "bear_value": 17.25,
                    "expected_return": 26.85 / 25.55 - 1.0,
                    "bear_downside": 17.25 / 25.55 - 1.0,
                    "confidence": "MEDIUM_HIGH",
                },
            }
        ],
    }
    recommendation = {
        "controls": _controls(),
        "summary": {},
        "records": [
            {
                "security_id": "002832.SZ",
                "security_name": "比音勒芬",
                "action": "BUY_BELOW",
                "top_blocker": "PRICE_BLOCKED",
                "ready_for_user_decision": False,
                "top_reasons": [
                    "BUY_BELOW_RESEARCH_COMPLETE_QUALITY_GROWTH",
                    "D2_EXPLICIT_POSITION_ACTION_BUY_BELOW",
                    "PRICE_BLOCKED",
                ],
            }
        ],
    }
    marks = {
        "data_watermark": {"latest_mark_date": "2026-09-15"},
        "marks": [
            {
                "security_id": "002832.SZ",
                "mark": 25.55,
                "as_of_date": "2026-09-15",
            }
        ],
    }

    _, rebased_recommendation = rebase_decisions(
        comparison, recommendation, marks, {"queue": []}
    )

    record = rebased_recommendation["records"][0]
    assert record["action"] == "BUY_BELOW"
    assert record["ready_for_user_decision"] is False
    assert record["top_blocker"] == "PRICE_BLOCKED"
    assert record["top_reasons"].count("PRICE_BLOCKED") == 1
    assert "BUY_BELOW_RESEARCH_COMPLETE_QUALITY_GROWTH" in record["top_reasons"]
    assert "D2_EXPLICIT_POSITION_ACTION_BUY_BELOW" in record["top_reasons"]
    assert not any(str(reason).startswith("MARK_REBASE_ACTION_") for reason in record["top_reasons"])
