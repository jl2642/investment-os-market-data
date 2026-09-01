from __future__ import annotations

import json
import pytest
from pathlib import Path

from automation.product_surface.build_product_surface import build_surface, render_daily_brief

ROOT = Path(__file__).resolve().parents[1]


def marks_domain():
    return {
        "status": "PASS",
        "data_watermark": "2026-08-31",
        "source_commit_sha": "marks-sha",
        "orders": 0,
        "trade_authority": "NONE",
    }


def investment_domain():
    return {
        "status": "PASS",
        "data_watermark": "2026-09-01T04:00:00+00:00",
        "source_commit_sha": "investment-sha",
        "orders": 0,
        "trade_authority": "NONE",
    }


def positions(real=True):
    return {
        "holdings": [
            {
                "security_id": "000005.SZ" if real else "000006.SZ",
                "security_name": "ExistingReal" if real else "ExistingSim",
            }
        ],
        "trade_authority": "NONE",
    }


def recommendation():
    return {
        "schema_version": "2.0.0",
        "state_id": "RECOMMENDATION_CURRENT_TEST",
        "status": "PASS_S2_RECOMMENDATION",
        "records": [
            {
                "security_id": "000005.SZ",
                "security_name": "ExistingReal",
                "action": "TRIM",
                "current_price": 20.0,
                "entry_price": 21.0,
                "expected_return": -0.10,
                "bear_downside": -0.30,
                "confidence": "HIGH",
                "top_blocker": "NEGATIVE_EXPECTED_RETURN",
                "ready_for_user_decision": True,
                "orders": 0,
                "trade_authority": "NONE",
            },
            {
                "security_id": "000001.SZ",
                "security_name": "NewBuy",
                "action": "BUY",
                "current_price": 10.0,
                "entry_price": 11.0,
                "expected_return": 0.30,
                "bear_downside": -0.20,
                "confidence": "HIGH",
                "top_blocker": None,
                "ready_for_user_decision": True,
                "orders": 0,
                "trade_authority": "NONE",
            },
        ],
        "controls": {
            "orders": 0,
            "trade_authority": "NONE",
        },
    }


def d1():
    return {
        "state_id": "D1_TEST",
        "status": "D1_FAST_TRIAGE_COMPLETE",
        "batch_size": 2,
        "research_objects": [
            {
                "security_id": "000001.SZ",
                "security_name": "NewBuy",
                "d1_rank": 1,
                "d1_disposition": "ADVANCE_TO_D2_FAST_TRIAGE",
                "research_priority": "A_IMMEDIATE_RESEARCH",
                "d2_questions": ["Q1"],
                "trade_authority": "NONE",
            },
            {
                "security_id": "000009.SZ",
                "security_name": "Watch",
                "d1_rank": 2,
                "d1_disposition": "WATCH_FOR_FUNDAMENTAL_CONFIRMATION",
                "research_priority": "A_IMMEDIATE_RESEARCH",
                "d2_questions": ["Q2"],
                "trade_authority": "NONE",
            },
        ],
        "routing_summary": {
            "advance_to_d2_count": 1,
            "watch_count": 1,
            "reject_count": 0,
            "ready_for_user_decision": 0,
        },
        "controls": {
            "orders": 0,
            "trade_authority": "NONE",
        },
    }


def marks():
    return {
        "status": "CURRENT_COMPLETE",
        "data_watermark": {"latest_mark_date": "2026-08-31"},
        "marks": [
            {"security_id": "000005.SZ", "mark_price": 20.0},
            {"security_id": "000006.SZ", "mark_price": 15.0},
        ],
        "trade_authority": "NONE",
    }


def test_surface_separates_existing_positions_new_capital_and_uncovered_positions():
    surface = build_surface(
        marks_domain=marks_domain(),
        investment_domain=investment_domain(),
        marks=marks(),
        real_positions=positions(True),
        simulation_positions=positions(False),
        recommendation=recommendation(),
        d1=d1(),
    )
    assert surface["status"] == "PASS_S3_PORTFOLIO_PRODUCT_SURFACE"
    assert surface["executive"]["portfolio_holding_count"] == 2
    assert surface["executive"]["portfolio_recommendation_coverage_count"] == 1
    assert surface["executive"]["portfolio_uncovered_count"] == 1
    assert surface["executive"]["new_opportunity_count"] == 1
    assert surface["executive"]["decision_review_required_count"] == 2
    assert surface["portfolio_decisions"][0]["action"] == "TRIM"
    assert surface["new_opportunities"][0]["action"] == "BUY"
    assert surface["portfolio_uncovered"][0]["action"] == "NO_CURRENT_S2_RECOMMENDATION"
    assert surface["controls"]["orders"] == 0
    assert surface["trade_authority"] == "NONE"


def test_daily_brief_is_one_readable_decision_surface_not_old_wp5_action_pack():
    surface = build_surface(
        marks_domain=marks_domain(),
        investment_domain=investment_domain(),
        marks=marks(),
        real_positions=positions(True),
        simulation_positions=positions(False),
        recommendation=recommendation(),
        d1=d1(),
    )
    brief = render_daily_brief(surface)
    assert "Daily Investment Brief" in brief
    assert "当前持仓决策面" in brief
    assert "新资本机会" in brief
    assert "研究队列" in brief
    assert "TRIM" in brief
    assert "BUY" in brief
    assert "旧 R3/R4/WP5 决策包不再作为当前产品入口" in brief
    assert "自动调仓" in brief


def test_system_authority_and_registry_keep_s3_bounded():
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
    assert system["acceptance"]["s1"] == "COMPLETE_ON_MAIN"
    assert system["acceptance"]["s2"] == "COMPLETE_ON_MAIN"
    assert system["acceptance"]["s3"] in {"IN_PROGRESS", "COMPLETE_ON_MAIN"}
    assert system["orders"] == 0
    assert system["trade_authority"] == "NONE"

    active = {row["path"] for row in registry["active_runtime_core"]}
    assert ".github/workflows/s3-portfolio-product-surface.yml" in active
    assert ".github/workflows/occ-r4-portfolio-decision-freshness.yml" not in active


def test_s3_does_not_restore_target_weight_or_automatic_mutation_engine():
    text = (
        ROOT / "automation/product_surface/build_product_surface.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "target_weight",
        "broker_order",
        "place_order",
        '"automatic_rebalance_allowed": True',
        '"automatic_position_change_allowed": True',
    ]
    assert all(token not in text for token in forbidden)


def test_retired_occ_r4_has_no_automatic_trigger():
    text = (
        ROOT / ".github/workflows/occ-r4-portfolio-decision-freshness.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  workflow_run:" not in text
    assert "\n  schedule:" not in text


def test_surface_fails_closed_on_nested_nonzero_orders():
    bad = recommendation()
    bad["records"][0]["orders"] = 1
    with pytest.raises(ValueError, match="ORDER_AUTHORITY_VIOLATION"):
        build_surface(
            marks_domain=marks_domain(),
            investment_domain=investment_domain(),
            marks=marks(),
            real_positions=positions(True),
            simulation_positions=positions(False),
            recommendation=bad,
            d1=d1(),
        )


def test_position_identity_drift_fails_closed():
    rec = recommendation()
    rec["records"][1]["portfolio_implication"] = "EXISTING_POSITION"
    surface = build_surface(
        marks_domain=marks_domain(),
        investment_domain=investment_domain(),
        marks=marks(),
        real_positions=positions(True),
        simulation_positions=positions(False),
        recommendation=rec,
        d1=d1(),
    )
    row = next(
        item
        for item in surface["new_opportunities"]
        if item["security_id"] == "000001.SZ"
    )
    assert row["original_recommendation_action"] == "BUY"
    assert row["action"] == "REVIEW_POSITION_IDENTITY_CHANGE"
    assert row["ready_for_user_decision"] is False
    assert (
        row["position_identity_alignment"]
        == "MISMATCH_REUNDERWRITE_REQUIRED"
    )
    assert (
        row["top_blocker"]
        == "POSITION_IDENTITY_CHANGED_SINCE_S2_RECOMMENDATION"
    )
    assert surface["executive"]["position_identity_mismatch_count"] == 1


def test_surface_reads_canonical_portfolio_mark_field():
    canonical_marks = {
        "status": "CURRENT_COMPLETE",
        "data_watermark": {"latest_mark_date": "2026-08-31"},
        "marks": [
            {"security_id": "000005.SZ", "mark": 20.5},
            {"security_id": "000006.SZ", "mark": 15.25},
        ],
        "trade_authority": "NONE",
    }
    rec = recommendation()
    rec["records"] = []
    surface = build_surface(
        marks_domain=marks_domain(),
        investment_domain=investment_domain(),
        marks=canonical_marks,
        real_positions=positions(True),
        simulation_positions=positions(False),
        recommendation=rec,
        d1=d1(),
    )
    prices = {
        row["security_id"]: row["current_price"]
        for row in surface["portfolio_uncovered"]
    }
    assert prices["000005.SZ"] == 20.5
    assert prices["000006.SZ"] == 15.25
