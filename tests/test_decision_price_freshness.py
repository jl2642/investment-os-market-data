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


def test_price_dependent_classification_is_recomputed_after_mark_rebase():
    comparison, recommendation = rebase_decisions(
        _comparison(), _recommendation(), _marks(), {"queue": []}
    )
    rec = recommendation["records"][0]
    # The original roughly -4.2% thesis-price return becomes roughly -0.6% at the 9/9 mark.
    # The action may remain TRIM under the existing <=0 hurdle, but its return basis must be current.
    assert comparison["rows"][0]["comparison_status"] == "AVOID_NEGATIVE_EXPECTED_RETURN"
    assert rec["action"] == "TRIM"
    assert rec["ready_for_user_decision"] is True
    assert rec["expected_return"] > 96.52 / 100.80 - 1
    assert rec["expected_return"] == 96.52 / 97.11 - 1


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


def test_mark_rebase_formal_buy_pass_cannot_promote_existing_hold_to_add():
    comparison = {
        "state_id": "C_HOLD",
        "status": "PASS_LIVE_CAPITAL_COMPARISON",
        "rows": [{
            "security_id": "000333.SZ",
            "security_name": "Existing",
            "d2_status": "D2_RESEARCH_COMPLETE",
            "comparison_status": "PRICE_BLOCKED",
            "existing_position": True,
            "capital_hurdle": 0.10,
            "cash_hurdle": 0.04,
            "metrics": {
                "current_price": 10.5,
                "entry_price": 9.0,
                "preferred_entry_price": 9.0,
                "bear_value": 9.0,
                "base_value": 13.0,
                "bull_value": 18.0,
                "probability_weighted_value": 13.25,
                "expected_return": 13.25 / 10.5 - 1,
                "bear_downside": 9.0 / 10.5 - 1,
                "confidence": "HIGH",
                "price_as_of": "2026-09-01",
            },
        }],
        "controls": {"orders": 0, "trade_authority": "NONE"},
    }
    recommendation = {
        "state_id": "R_HOLD",
        "status": "PASS_S2_RECOMMENDATION",
        "summary": {"action_counts": {"HOLD": 1}, "ready_for_user_decision_count": 0},
        "records": [{
            "security_id": "000333.SZ",
            "security_name": "Existing",
            "action": "HOLD",
            "current_price": 10.5,
            "entry_price": 9.0,
            "portfolio_implication": "EXISTING_POSITION",
            "ready_for_user_decision": False,
            "top_reasons": ["PRICE_BLOCKED"],
            "orders": 0,
            "trade_authority": "NONE",
        }],
        "controls": {"orders": 0, "trade_authority": "NONE"},
    }
    marks = {
        "status": "CURRENT_COMPLETE",
        "data_watermark": {"latest_mark_date": "2026-09-22"},
        "marks": [{"security_id": "000333.SZ", "as_of_date": "2026-09-22", "mark": 10.0}],
        "orders": 0,
        "trade_authority": "NONE",
    }
    comparison, recommendation = rebase_decisions(
        comparison,
        recommendation,
        marks,
        {"queue": []},
    )
    assert comparison["rows"][0]["comparison_status"] == "PASS_NEW_CAPITAL"
    assert recommendation["records"][0]["action"] == "HOLD"
    assert recommendation["records"][0]["ready_for_user_decision"] is False


def test_new_capital_buy_is_downgraded_when_latest_full_market_price_exhausts_hurdle():
    comparison = {
        "controls": {"orders": 0, "trade_authority": "NONE"},
        "rows": [{
            "security_id": "301109.SZ",
            "existing_position": False,
            "comparison_status": "PASS_NEW_CAPITAL",
            "metrics": {
                "current_price": 12.75, "price_as_of": "2026-09-15",
                "entry_price": 12.4, "bear_value": 11.0,
                "probability_weighted_value": 14.265,
                "expected_return": 14.265 / 12.75 - 1.0,
                "bear_downside": 11.0 / 12.75 - 1.0,
            },
        }],
    }
    rec = {
        "controls": {"orders": 0, "trade_authority": "NONE"},
        "records": [{"security_id": "301109.SZ", "action": "BUY",
                     "ready_for_user_decision": True, "top_reasons": []}],
    }
    _, current = rebase_decisions(
        comparison, rec, {"data_watermark": {"latest_mark_date": "2026-10-27"}, "marks": []},
        {"queue": []},
        market_rows={"301109.SZ": {
            "resolved_mark": 13.83, "as_of_date": "2026-10-27",
        }},
        market_watermark="2026-10-27",
    )
    item = current["records"][0]
    assert item["current_price"] == 13.83
    assert abs(item["expected_return"] - (14.265 / 13.83 - 1)) < 1e-12
    assert item["action"] == "BUY_BELOW"
    assert item["top_blocker"] == "PRICE_BLOCKED"
    assert item["ready_for_user_decision"] is False
    assert item["price_basis"] == "A_SHARE_FULL_MARKET"
    assert item["orders"] if "orders" in item else True


def test_new_capital_missing_or_mismatched_full_market_close_fails_closed():
    for market_rows in ({}, {"301109.SZ": {
        "resolved_mark": 12.0, "as_of_date": "2026-10-23",
    }}):
        comparison = {
            "controls": {"orders": 0, "trade_authority": "NONE"},
            "rows": [{
                "security_id": "301109.SZ", "existing_position": False,
                "comparison_status": "PASS_NEW_CAPITAL",
                "metrics": {
                    "current_price": 12.75, "entry_price": 12.4,
                    "bear_value": 11.0, "probability_weighted_value": 14.265,
                    "expected_return": 0.1188, "bear_downside": -0.14,
                },
            }],
        }
        rec = {
            "controls": {"orders": 0, "trade_authority": "NONE"},
            "records": [{"security_id": "301109.SZ", "action": "BUY",
                         "ready_for_user_decision": True, "top_reasons": []}],
        }
        _, current = rebase_decisions(
            comparison, rec, {"data_watermark": {"latest_mark_date": "2026-10-27"}, "marks": []},
            {"queue": []}, market_rows=market_rows,
            market_watermark="2026-10-27",
        )
        item = current["records"][0]
        assert item["action"] == "WATCH"
        assert item["top_blocker"] == "PRICE_FRESHNESS_BLOCKED"
        assert item["ready_for_user_decision"] is False
