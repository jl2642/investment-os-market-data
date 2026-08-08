from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.hkcu_p4_1_portfolio_fit_reassessment import (
    combined_route,
    compound_no_incremental,
    runtime_context_gaps,
)

ROOT = Path(__file__).resolve().parents[1]


def contract() -> dict:
    return json.loads((ROOT / "config/hkcu_p4_1_portfolio_fit_reassessment_contract.json").read_text(encoding="utf-8"))


def test_contract_entry_and_boundary() -> None:
    c = contract()
    assert c["program_id"] == "HKCU-P4-1-REASSESSMENT"
    assert c["entry_contract"]["entry_candidate_count"] == 70
    assert c["entry_contract"]["account_security_assessment_count"] == 140
    assert c["entry_contract"]["rule_assessment_row_count"] == 2100
    assert c["entry_contract"]["combined_routing_count"] == 70
    assert c["runtime_context_contract"]["required_status"] == "PASS_P4_1R_PORTFOLIO_CONTEXT_COMPLETION"
    assert c["runtime_context_contract"]["required_context_ready_account_security_count"] == 140
    assert c["runtime_context_contract"]["required_residual_gap_count"] == 0
    for key in [
        "candidate_pool_mutation_authorized",
        "simulation_admission_authorized",
        "simulation_mutation_authorized",
        "real_account_admission_authorized",
        "real_account_mutation_authorized",
        "portfolio_allocation_authorized",
        "position_sizing_authorized",
        "order_creation_authorized",
    ]:
        assert c["phase_boundary"][key] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_forbidden_shortcuts_remain_disabled() -> None:
    p = contract()["decision_policy"]
    assert p["weighted_score_allowed"] is False
    assert p["fixed_top_n_allowed"] is False
    assert p["fuzzy_identity_matching_allowed"] is False
    assert p["sector_neutral_fill_allowed"] is False
    assert p["ticker_count_diversification_inference_allowed"] is False
    assert p["trailing_return_may_be_called_expected_return"] is False
    assert p["ah_discount_may_be_called_alpha"] is False
    assert p["exact_ah_overlap_is_named_constraint_not_automatic_rejection"] is True
    assert p["pooled_exposure_is_named_constraint_not_automatic_defer"] is True


def test_combined_route_is_derived_only_from_account_states() -> None:
    assert combined_route("FIT_WITH_CONSTRAINTS", "FIT_WITH_CONSTRAINTS") == "ADVANCE_DUAL_CONSTRUCTION_REVIEW"
    assert combined_route("FIT_WITH_CONSTRAINTS", "NO_INCREMENTAL_ROLE") == "ADVANCE_REAL_ACCOUNT_REVIEW"
    assert combined_route("NO_INCREMENTAL_ROLE", "FIT_WITH_CONSTRAINTS") == "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW"
    assert combined_route("NO_INCREMENTAL_ROLE", "NO_INCREMENTAL_ROLE") == "HOLD_PORTFOLIO_WATCH"
    assert combined_route("DEFER_PORTFOLIO_CONTEXT", "FIT_WITH_CONSTRAINTS") == "DEFER_PORTFOLIO_CONTEXT"
    assert combined_route("BLOCK_PORTFOLIO_FIT", "BLOCK_PORTFOLIO_FIT") == "BLOCK_PORTFOLIO_FIT"


def test_non_direct_no_incremental_requires_joint_evidence() -> None:
    base = {
        "marginal_risk_state": "ADDS_CORRELATED_RISK",
        "opportunity_cost_state": "HIGH_RELATIVE_OPPORTUNITY_COST",
        "sector_impact_state": "INCREASES_EXISTING_DIRECT_SECTOR",
        "style_impact_state": "INCREASES_EXISTING_STYLE",
    }
    assert compound_no_incremental(pd.Series(base)) is True
    for key in list(base):
        altered = dict(base)
        altered[key] = {
            "marginal_risk_state": "MIXED_RISK_CONTRIBUTION",
            "opportunity_cost_state": "MODERATE_RELATIVE_OPPORTUNITY_COST",
            "sector_impact_state": "ADDS_NEW_DIRECT_SECTOR_EXPOSURE",
            "style_impact_state": "ADDS_DISTINCT_STYLE_EXPOSURE",
        }[key]
        assert compound_no_incremental(pd.Series(altered)) is False


def test_runtime_context_gate_accepts_only_complete_p4_1r() -> None:
    c = contract()
    decision = {
        "program_id": "HKCU-P4-1R",
        "status": "PASS_P4_1R_PORTFOLIO_CONTEXT_COMPLETION",
        "candidate_context_count": 70,
        "account_holding_context_count": 24,
        "account_security_context_count": 140,
        "context_ready_account_security_count": 140,
        "exact_ah_mapped_count": 13,
        "candidate_industry_coverage": 1.0,
        "residual_decision_critical_gap_count": 0,
        "trade_authority": "NONE",
    }
    gaps = pd.DataFrame(columns=["context_id", "scope", "reason"])
    assert runtime_context_gaps(decision, gaps, c) == []
    bad = dict(decision)
    bad["context_ready_account_security_count"] = 139
    assert runtime_context_gaps(bad, gaps, c)[0]["context_id"] == "P4_1R_RUNTIME_CONTEXT"


def test_acceptance_remains_assessment_only() -> None:
    a = contract()["acceptance"]
    assert a["pass_status"] == "PASS_P4_1_PORTFOLIO_FIT_REASSESSMENT"
    assert a["next_gate_on_pass"] == "P4_2_PORTFOLIO_CONSTRUCTION_REVIEW"
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "portfolio_allocations", "orders_created"]:
        assert a[key] == 0
    assert a["trade_authority"] == "NONE"
