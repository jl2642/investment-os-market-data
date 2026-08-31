from __future__ import annotations

from copy import deepcopy

import pytest

from automation.portfolio_freshness.build_portfolio_decision_freshness import build_context


def fixtures() -> dict:
    marks_domain = {
        "domain_id": "PORTFOLIO_MARKS",
        "status": "PASS",
        "data_watermark": "2026-08-28",
        "source_workflow": "R2 WP2-R Market Marks Refresh",
        "source_run_id": "1",
        "source_branch": "automation/wp2r-eod-1-a1",
        "source_commit_sha": "a" * 40,
        "trade_authority": "NONE",
    }
    recommendation_domain = {
        "domain_id": "RECOMMENDATION",
        "status": "PASS",
        "data_watermark": "2026-08-31T13:10:23+00:00",
        "source_workflow": "P4-3 Unified Decision Recommendation",
        "source_run_id": "2",
        "source_branch": "main",
        "source_commit_sha": "b" * 40,
        "trade_authority": "NONE",
    }
    marks = {
        "status": "CURRENT_COMPLETE",
        "data_watermark": {"latest_mark_date": "2026-08-28"},
        "marks": [
            {"security_id": "000001.SZ", "freshness_status": "FRESH"},
            {"security_id": "000002.SZ", "freshness_status": "ACCEPTABLE_LAG"},
        ],
        "trade_authority": "NONE",
    }
    real = {
        "holdings": [{"security_id": "000001.SZ"}],
        "mark_watermark": {
            "latest_mark_date": "2026-08-28",
            "all_positions_marked": True,
        },
        "trade_authority": "NONE",
    }
    simulation = {
        "holdings": [{"security_id": "000002.SZ"}],
        "mark_watermark": {
            "latest_mark_date": "2026-08-28",
            "all_positions_marked": True,
        },
        "trade_authority": "NONE",
    }
    recommendation = {
        "generated_at_utc": "2026-08-31T13:10:23+00:00",
        "overall_status": "CURRENT_EXPLICIT_NON_ACTIONABLE_JUDGMENTS",
        "recommendation_fingerprint": "f" * 64,
        "records": [
            {
                "security_id": "000719.SZ",
                "recommendation_state": "WATCH_NORMAL",
                "ready_for_user_decision": False,
                "trade_authority": "NONE",
            }
        ],
        "controls": {"orders": 0, "trade_authority": "NONE"},
        "trade_authority": "NONE",
    }
    legacy = {
        "state_id": "WP5_PORTFOLIO_DECISION_CURRENT",
        "generated_at": "2026-07-27T01:52:38+00:00",
        "status": "CONDITIONAL_PORTFOLIO_REVIEW_NOT_IMPLEMENTATION_READY",
        "trade_authority": "NONE",
    }
    return {
        "marks_domain": marks_domain,
        "recommendation_domain": recommendation_domain,
        "marks": marks,
        "real_positions": real,
        "simulation_positions": simulation,
        "recommendation": recommendation,
        "legacy_decision": legacy,
    }


def test_fresh_inputs_bind_and_stale_legacy_decision_is_blocked() -> None:
    result = build_context(**fixtures())
    assert result["status"] == "PASS_PORTFOLIO_DECISION_FRESHNESS_ALIGNED"
    assert result["as_of_date"] == "2026-08-28"
    assert result["decision_freshness"]["fresh_input_surface"] is True
    assert result["decision_freshness"]["legacy_action_matrix_current"] is False
    assert result["decision_freshness"]["implementation_ready"] is False
    assert result["recommendation_current"]["portfolio_overlap_count"] == 0
    assert result["controls"]["orders"] == 0
    assert result["trade_authority"] == "NONE"


def test_current_recommendation_overlap_remains_governed_not_actionable() -> None:
    data = fixtures()
    data["recommendation"]["records"][0]["security_id"] = "000001.SZ"
    result = build_context(**data)
    assert result["recommendation_current"]["portfolio_overlap_security_ids"] == ["000001.SZ"]
    assert result["decision_freshness"]["portfolio_action_state"].startswith(
        "BLOCKED_FRESH_RECOMMENDATION_OVERLAP"
    )
    assert result["decision_freshness"]["ready_for_user_decision"] is False
    assert result["controls"]["real_account_mutations"] == 0
    assert result["controls"]["simulation_mutations"] == 0


def test_mark_domain_watermark_mismatch_fails_closed() -> None:
    data = fixtures()
    data["marks_domain"]["data_watermark"] = "2026-08-27"
    with pytest.raises(ValueError, match="PORTFOLIO_MARK_DOMAIN_WATERMARK_MISMATCH"):
        build_context(**data)


def test_non_none_trade_authority_fails_closed() -> None:
    data = fixtures()
    bad = deepcopy(data["recommendation"])
    bad["controls"]["trade_authority"] = "AUTO"
    data["recommendation"] = bad
    with pytest.raises(ValueError, match="TRADE_AUTHORITY_VIOLATION"):
        build_context(**data)
