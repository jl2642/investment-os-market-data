from __future__ import annotations

from datetime import datetime, timezone

from automation.investment_pipeline.build_pipeline import (
    build_capital_comparison,
    build_d1,
    build_opportunity_queue,
    build_recommendations,
)

NOW = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)


def screen_row(i: int, priority: str = "A_IMMEDIATE_RESEARCH") -> dict:
    return {
        "as_of_date": "2026-08-28",
        "overall_rank": str(i),
        "research_priority": priority,
        "symbol": f"{i:06d}.SZ",
        "name": f"Name{i}",
        "primary_sleeve": (
            "DEFENSIVE_STABILITY" if i % 2 else "TREND_PERSISTENCE"
        ),
        "sleeves": "DEFENSIVE_STABILITY",
        "aggregate_score": str(1 - i / 1000),
        "return_60d": "0.10",
        "volatility_60d": "0.20",
        "max_drawdown_120d": "-0.10",
        "avg_turnover_cny_20d": "100000000",
        "confidence_grade": "A",
        "factor_record_quality": "VALID",
    }


def uw(
    current: float,
    entry: float,
    bear: float,
    base: float,
    bull: float,
    confidence: str = "HIGH",
) -> dict:
    return {
        "current_price": current,
        "price_as_of": "2026-08-28",
        "entry_price": entry,
        "confidence": confidence,
        "normalized_earnings_basis": "SYNTHETIC_TEST_NORMALIZED_EARNINGS",
        "scenarios": [
            {"name": "BEAR", "value": bear, "probability": 0.25},
            {"name": "BASE", "value": base, "probability": 0.50},
            {"name": "BULL", "value": bull, "probability": 0.25},
        ],
        "kill_thesis": "Synthetic kill thesis",
        "catalysts": ["Synthetic catalyst"],
        "portfolio_role": "COMPOUNDER",
    }


def test_opportunity_bypasses_candidate_and_d1_processes_ten() -> None:
    longlist = [screen_row(i) for i in range(1, 16)]
    opportunity = build_opportunity_queue(
        longlist,
        screen_source={
            "qc_status": "PASS_CHAIN_COHERENT",
            "data_watermark": "2026-08-28",
        },
        now=NOW,
    )
    assert opportunity["opportunity_count"] == 15
    assert all(
        row["candidate_membership_required"] is False
        for row in opportunity["rows"]
    )

    d1 = build_d1(opportunity, now=NOW)
    assert d1["batch_size"] == 10
    assert d1["routing_summary"]["advance_to_d2_count"] == 3
    assert all(
        row["candidate_membership_required"] is False
        for row in d1["research_objects"]
    )
    assert all(row["d2_questions"] for row in d1["research_objects"])
    assert d1["controls"]["orders"] == 0
    assert d1["controls"]["trade_authority"] == "NONE"


def test_all_s2_actions_are_reachable_from_underwriting_not_boolean_gates() -> None:
    d2 = {
        "state_id": "D2_SYNTHETIC",
        "queue": [
            {
                "security_id": "000001.SZ",
                "security_name": "Buy",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(10, 11, 8, 13, 18),
            },
            {
                "security_id": "000002.SZ",
                "security_name": "BuyBelow",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(15, 12, 10, 18, 24),
            },
            {
                "security_id": "000003.SZ",
                "security_name": "Evidence",
                "status": "D2_RESEARCH_HOLD_EVIDENCE_GAP",
                "research_disposition": "HOLD",
                "evidence_gap": "Missing utilization evidence",
                "first_rejection_test": "NOT_TRIGGERED",
            },
            {
                "security_id": "000004.SZ",
                "security_name": "Avoid",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(20, 21, 14, 17, 20),
            },
            {
                "security_id": "000005.SZ",
                "security_name": "Add",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(10, 11, 8, 13, 18),
            },
            {
                "security_id": "000006.SZ",
                "security_name": "Hold",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(15, 12, 10, 18, 24),
            },
            {
                "security_id": "000007.SZ",
                "security_name": "Trim",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
                "underwriting": uw(20, 21, 14, 17, 20),
            },
            {
                "security_id": "000008.SZ",
                "security_name": "Exit",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "TRIGGERED_BY_KILL_THESIS",
                "underwriting": uw(10, 11, 8, 13, 18),
            },
        ],
    }
    real = {
        "holdings": [
            {"security_id": "000005.SZ"},
            {"security_id": "000006.SZ"},
            {"security_id": "000007.SZ"},
            {"security_id": "000008.SZ"},
        ]
    }

    comparison = build_capital_comparison(
        d2,
        real_positions=real,
        simulation_positions={},
        now=NOW,
    )
    recommendation = build_recommendations(d2, comparison, now=NOW)

    actions = {
        row["security_id"]: row["action"]
        for row in recommendation["records"]
    }
    assert actions == {
        "000001.SZ": "BUY",
        "000002.SZ": "BUY_BELOW",
        "000003.SZ": "WATCH_FOR_EVIDENCE",
        "000004.SZ": "AVOID",
        "000005.SZ": "ADD",
        "000006.SZ": "HOLD",
        "000007.SZ": "TRIM",
        "000008.SZ": "EXIT",
    }
    assert recommendation["summary"]["ready_for_user_decision_count"] == 4
    assert all(
        row["orders"] == 0 and row["trade_authority"] == "NONE"
        for row in recommendation["records"]
    )


def test_missing_underwriting_fails_closed_to_watch() -> None:
    d2 = {
        "state_id": "D2_MISSING_UW",
        "queue": [
            {
                "security_id": "000009.SZ",
                "security_name": "NoUW",
                "status": "D2_RESEARCH_COMPLETE",
                "research_disposition": "COMPLETE",
                "first_rejection_test": "NOT_TRIGGERED",
            }
        ],
    }
    comparison = build_capital_comparison(
        d2,
        real_positions={},
        simulation_positions={},
        now=NOW,
    )
    assert (
        comparison["rows"][0]["comparison_status"]
        == "UNDERWRITING_INCOMPLETE"
    )
    recommendation = build_recommendations(d2, comparison, now=NOW)
    assert recommendation["records"][0]["action"] == "WATCH"
    assert (
        recommendation["records"][0]["ready_for_user_decision"]
        is False
    )
