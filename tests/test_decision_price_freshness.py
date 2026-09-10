from __future__ import annotations

from automation.investment_pipeline.rebase_decision_to_marks import rebase_decisions


def _comparison():
    return {
        "state_id": "C_OLD",
        "status": "PASS_LIVE_CAPITAL_COMPARISON",
        "rows": [
            {
                "security_id": "600941.SH",
                "security_name": "中国移动",
                "d2_status": "D2_RESEARCH_COMPLETE",
                "comparison_status": "AVOID_NEGATIVE_EXPECTED_RETURN",
                "existing_position": True,
                "capital_hurdle": 0.10,
                "cash_hurdle": 0.04,
                "metrics": {
                    "current_price": 100.80,
                    "entry_price": 96.00,
                    "bear_value": 82.00,
                    "base_value": 97.00,
                    "bull_value": 112.00,
                    "probability_weighted_value": 96.52,
                    "expected_return": 96.52 / 100.80 - 1,
                    "bear_downside": 82.00 / 100.80 - 1,
                    "confidence": "HIGH",
                    "price_as_of": "2026-09-03",
                },
                "controls": {"orders": 0, "trade_authority": "NONE"},
            }
        ],
        "controls": {"orders": 0, "trade_authority": "NONE"},
    }


def _recommendation():
    return {
        "state_id": "R_OLD",
        "status": "PASS_S2_RECOMMENDATION",
        "summary": {"action_counts": {"TRIM": 1}, "ready_for_user_decision_count": 1},
        "records": [
            {
                "security_id": "600941.SH",
                "security_name": "中国移动",
                "action": "TRIM",
                "current_price": 100.80,
                "entry_price": 96.00,
                "probability_weighted_value": 96.52,
                "expected_return": 96.52 / 100.80 - 1,
                "bear_downside": 82.00 / 100.80 - 1,
                "portfolio_implication": "EXISTING_POSITION",
                "ready_for_user_decision": True,
                "top_reasons": ["D2_EXPLICIT_POSITION_ACTION_TRIM"],
                "orders": 0,
                "trade_authority": "NONE",
            }
        ],
        "controls": {"orders": 0, "trade_authority": "NONE"},
    }


def _marks():
    return {
        "status": "CURRENT_COMPLETE",
        "data_watermark": {"latest_mark_date": "2026-09-09"},
        "marks": [
            {
                "security_id": "600941.SH",
                "as_of_date": "2026-09-09",
                "mark": 97.11,
                "freshness_status": "FRESH",
            }
        ],
        "orders": 0,
        "trade_authority": "NONE",
    }


def test_current_decision_rebases_to_latest_mark_without_mutating_underwriting_snapshot():
    comparison, recommendation = rebase_decisions(
        _comparison(), _recommendation(), _marks(), {"queue": []}
    )
    metrics = comparison["rows"][0]["metrics"]
    rec = recommendation["records"][0]
    assert metrics["underwriting_price"] == 100.80
    assert metrics["underwriting_price_as_of"] == "2026-09-03"
    assert metrics["current_market_price"] == 97.11
    assert metrics["current_price"] == 97.11
    assert metrics["expected_return"] == 96.52 / 97.11 - 1
    assert rec["underwriting_price"] == 100.80
    assert rec["current_market_price"] == 97.11
    assert rec["current_price"] == 97.11
    assert rec["expected_return"] == 96.52 / 97.11 - 1
    assert rec["price_basis"] == "PORTFOLIO_MARKS_CURRENT"
    assert recommendation["price_freshness_policy"]["latest_mark_date"] == "2026-09-09"


def test_price_dependent_trim_is_rechecked_after_mark_rebase():
    comparison, recommendation = rebase_decisions(
        _comparison(), _recommendation(), _marks(), {"queue": []}
    )
    # The original -4.2% thesis-price return becomes near-flat at the 9/9 mark;
    # it must not remain a stale negative-return TRIM solely because D2 was priced at 100.80.
    assert comparison["rows"][0]["comparison_status"] == "PRICE_BLOCKED"
    assert recommendation["records"][0]["action"] == "HOLD"
    assert recommendation["records"][0]["ready_for_user_decision"] is False


def test_active_semantic_refresh_fails_closed_even_if_old_d2_is_carried_forward():
    raw_d2 = {
        "queue": [
            {
                "security_id": "600941.SH",
                "status": "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
                "semantic_research_required": True,
            }
        ]
    }
    comparison, recommendation = rebase_decisions(
        _comparison(), _recommendation(), _marks(), raw_d2
    )
    assert comparison["rows"][0]["comparison_status"] == "RESEARCH_REFRESH_PENDING"
    rec = recommendation["records"][0]
    assert rec["research_freshness"] == "RESEARCH_REFRESH_PENDING"
    assert rec["action"] == "HOLD"
    assert rec["ready_for_user_decision"] is False
    assert rec["top_blocker"] == "RESEARCH_REFRESH_PENDING"
    assert rec["orders"] == 0
    assert rec["trade_authority"] == "NONE"
