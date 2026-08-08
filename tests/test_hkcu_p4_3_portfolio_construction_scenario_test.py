from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline import hkcu_p4_3_portfolio_construction_scenario_test as p4

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return json.loads((ROOT / "config/hkcu_p4_3_portfolio_construction_scenario_test_contract.json").read_text(encoding="utf-8"))


def synthetic_review(account: str) -> pd.DataFrame:
    rows = []
    specs = [
        ("HKEX:00001", "A", "PRIMARY_BUILD_REVIEW", "FINANCIALS", "QUALITY", 0.030),
        ("HKEX:00002", "B", "SECONDARY_BUILD_REVIEW", "INDUSTRIALS", "RECOVERY", 0.025),
        ("HKEX:00003", "C", "SECONDARY_BUILD_REVIEW", "UTILITIES", "DEFENSIVE", 0.020),
        ("HKEX:00004", "D", "PROBE_BUILD_REVIEW", "HEALTHCARE", "QUALITY", 0.015),
        ("HKEX:00005", "E", "PROBE_BUILD_REVIEW", "CONSUMER_STAPLES", "INCOME", 0.015),
    ]
    for i, (sid, name, state, sector, style, wmax) in enumerate(specs, 1):
        rows.append({
            "p2a_overall_rank": i,
            "security_id": sid,
            "stock_code_5d": sid[-5:],
            "security_name": name,
            "account": account,
            "construction_state": state,
            "marginal_risk_state": "IMPROVES_DIVERSIFICATION" if i in {1, 3} else "DIVERSIFIES_RETURN_STREAM_BUT_RAISES_RISK_BUDGET",
            "opportunity_cost_state": "LOW_RELATIVE_OPPORTUNITY_COST",
            "economic_sector_industry": sector,
            "portfolio_style": style,
            "suggested_weight_max": wmax,
            "existing_same_sector_weight": 0.0,
            "construction_existing_direct_same_style_weight": 0.0,
            "max_drawdown_120d": -0.20,
        })
    return pd.DataFrame(rows)


def state(account: str, cash: float) -> dict:
    return {"account": account, "summary": {"account_total_assets": 1_000_000.0, "execution_cash_balance": cash}, "holdings": [], "trade_authority": "NONE"}


def test_contract_has_bounded_non_scoring_scenario_surface():
    c = contract()
    policy = c["scenario_policy"]
    acceptance = c["acceptance"]
    assert policy["weighted_score_allowed"] is False
    assert policy["fixed_top_n_allowed"] is False
    assert policy["candidate_rank_may_authorize_allocation"] is False
    assert len(policy["scenario_definitions"]["REAL"]) == 3
    assert len(policy["scenario_definitions"]["SIMULATION"]) == 6
    assert sum(x["scenario_family"] == "MAX_AH_SUBSTITUTION_STRESS" for x in policy["scenario_definitions"]["SIMULATION"]) == 3
    assert c["phase_boundary"]["portfolio_proposal_authorized"] is False
    assert c["phase_boundary"]["order_creation_authorized"] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"
    assert acceptance["candidate_pool_mutations"] == 0
    assert acceptance["simulation_mutations"] == 0
    assert acceptance["real_account_mutations"] == 0
    assert acceptance["portfolio_proposal_produced"] is False
    assert acceptance["target_portfolio_writeback"] is False
    assert acceptance["orders_created"] == 0
    assert acceptance["trade_authority"] == "NONE"


def test_real_base_scenario_is_aggregate_but_requires_external_funding():
    c = contract()
    scenario = {"scenario_id": "TEST_REAL", "scenario_family": "BASE_NEW_BUILD", "hk_sleeve_target": 0.05}
    summary, rows = p4.allocate_scenario(scenario, "REAL", synthetic_review("REAL"), pd.DataFrame(), state("REAL", 0.0), c["scenario_policy"])
    assert summary["scenario_status"] == "PASS"
    assert summary["hk_sleeve_allocated"] <= 0.05 + 1e-12
    assert 0.05 - summary["hk_sleeve_allocated"] <= c["scenario_policy"]["target_residual_tolerance"] + 1e-12
    assert summary["funding_status"] == "FEASIBLE_WITH_EXTERNAL_FUNDING_DEPENDENCY"
    assert all(r["allocation_type"] == "NEW_BUILD" for r in rows)
    assert all(r["trade_authority"] == "NONE" for r in rows)
    assert all(r["orders_created"] == 0 for r in rows)


def test_ah_stress_scenario_is_equal_weight_replacement_not_net_new():
    c = contract()
    review = synthetic_review("SIMULATION")
    sub_review = pd.DataFrame([{
        "p2a_overall_rank": 6,
        "security_id": "HKEX:00300",
        "stock_code_5d": "00300",
        "security_name": "MIDEA GROUP",
        "account": "SIMULATION",
        "construction_state": "SUBSTITUTION_REVIEW_ONLY",
        "marginal_risk_state": "DIVERSIFIES_RETURN_STREAM_BUT_RAISES_RISK_BUDGET",
        "opportunity_cost_state": "MODERATE_RELATIVE_OPPORTUNITY_COST",
        "economic_sector_industry": "CONSUMER_DISCRETIONARY",
        "portfolio_style": "MOMENTUM_LIQUID",
        "suggested_weight_max": 0.0,
        "existing_same_sector_weight": 0.06,
        "construction_existing_direct_same_style_weight": 0.0,
        "max_drawdown_120d": -0.20,
    }])
    review = pd.concat([review, sub_review], ignore_index=True)
    substitutions = pd.DataFrame([{
        "p2a_overall_rank": 6,
        "security_id": "HKEX:00300",
        "stock_code_5d": "00300",
        "security_name": "MIDEA GROUP",
        "account": "SIMULATION",
        "overlap_security_ids": "000333.SZ",
        "existing_overlap_weight": 0.065,
        "replacement_equivalent_weight_cap": 0.019,
    }])
    scenario = {"scenario_id": "TEST_SIM_AH", "scenario_family": "MAX_AH_SUBSTITUTION_STRESS", "hk_sleeve_target": 0.10}
    summary, rows = p4.allocate_scenario(scenario, "SIMULATION", review, substitutions, state("SIMULATION", 250_000.0), c["scenario_policy"])
    sub_rows = [r for r in rows if r["allocation_type"] == "AH_SUBSTITUTION"]
    assert summary["scenario_status"] == "PASS"
    assert len(sub_rows) == 1
    assert sub_rows[0]["scenario_weight"] <= 0.019 + 1e-12
    assert sub_rows[0]["paired_reduction_weight"] == sub_rows[0]["scenario_weight"]
    assert sub_rows[0]["net_new_capital_weight"] == 0.0
    assert summary["funding_gap_weight"] == 0.0
    assert summary["funding_status"] == "FEASIBLE_WITH_SIMULATION_CASH"
