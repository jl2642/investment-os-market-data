from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

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


ROOT = Path(__file__).resolve().parents[1]


def test_s2_is_registered_as_primary_and_old_p4_producers_are_retired() -> None:
    system = json.loads(
        (ROOT / "investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    registry = json.loads(
        (
            ROOT
            / "investment_os_runtime/00_CONTROL/ACTIVE_WORKFLOW_REGISTRY.json"
        ).read_text(encoding="utf-8")
    )
    assert system["acceptance"]["s2"] == "COMPLETE_ON_MAIN"
    assert system["s2_scope"]["candidate_membership_as_research_gate"] is False
    assert system["s2_scope"]["d1_batch_size"] == 10
    assert system["s2_scope"]["d2_capacity"] == 3

    active = {row["path"] for row in registry["active_runtime_core"]}
    transitional = set(registry["transitional_investment_runtime_until_s2_s3"])
    retired = {row["path"] for row in registry["retired_automatic_workflows_s1"]}
    assert ".github/workflows/s2-investment-pipeline.yml" in active
    assert ".github/workflows/p4-2-continuous-opportunity-funnel.yml" in retired
    assert ".github/workflows/p4-3-unified-recommendation.yml" in retired
    assert ".github/workflows/p4-2-continuous-opportunity-funnel.yml" not in transitional
    assert ".github/workflows/p4-3-unified-recommendation.yml" not in transitional


def test_retired_p4_workflows_have_no_automatic_production_triggers() -> None:
    for path in (
        ".github/workflows/p4-2-continuous-opportunity-funnel.yml",
        ".github/workflows/p4-3-unified-recommendation.yml",
    ):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "\n  schedule:" not in text
        assert "\n  push:" not in text
        assert "\n  workflow_run:" not in text


def test_s2_workflow_uses_one_transactional_callback_not_duplicate_dispatch() -> None:
    text = (
        ROOT / ".github/workflows/s2-investment-pipeline.yml"
    ).read_text(encoding="utf-8")
    d2_text = (
        ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml"
    ).read_text(encoding="utf-8")
    assert 'workflows:' in text
    assert '"FMDL Daily A-share Governed Production"' in text
    assert '"FMDL daily market, factor and screening transaction"' not in text
    assert '"Research Queue D2 Auto Consumer"' in text
    assert "Candidate membership is not a research gate." in text
    explicit_callback = (
        "gh workflow run s2-investment-pipeline.yml --ref main -f mode=d2_callback"
    )
    assert d2_text.count(explicit_callback) == 1
    assert (
        "gh workflow run s2-investment-pipeline.yml --ref main\n"
        not in d2_text
    )
    assert "operating_current/investment_pipeline/D1_CURRENT.json" in d2_text


def test_s2_runtime_binds_screen_vars_before_same_step_use() -> None:
    text = (
        ROOT / ".github/workflows/s2-investment-pipeline.yml"
    ).read_text(encoding="utf-8")
    fetch_token = 'git fetch origin "refs/heads/$SCREEN_BRANCH:refs/remotes/origin/s2-screening"'
    bind_token = 'SCREEN_BRANCH="$(python -c'
    assert bind_token in text
    assert fetch_token in text
    assert text.index(bind_token) < text.index(fetch_token)


def test_s4_explicit_transaction_callbacks_avoid_github_token_workflow_run_gap() -> None:
    s2 = (
        ROOT / ".github/workflows/s2-investment-pipeline.yml"
    ).read_text(encoding="utf-8")
    d2 = (
        ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml"
    ).read_text(encoding="utf-8")
    s3 = (
        ROOT / ".github/workflows/s3-portfolio-product-surface.yml"
    ).read_text(encoding="utf-8")

    assert 'mode:' in s2
    assert '"d2_callback"' in s2
    assert s2.count("inputs.mode == 'd2_callback'") >= 4
    assert (
        "gh workflow run s2-investment-pipeline.yml --ref main -f mode=d2_callback"
        in d2
    )
    assert "actions: write" in d2
    assert "GH_TOKEN: ${{ github.token }}" in d2
    assert "gh workflow run s3-portfolio-product-surface.yml --ref main" in s2

    s3_trigger = s3.split("permissions:", 1)[0]
    assert '- "S2 Investment Pipeline"' not in s3_trigger
    assert '- "R2 WP2-R Market Marks Refresh"' in s3_trigger

    combined = s2 + d2 + s3
    assert "secrets.PAT" not in combined
    assert "personal_access_token" not in combined.lower()
