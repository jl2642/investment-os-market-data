import json
from pathlib import Path

import pandas as pd

from pipeline import hkcu_p4_2_portfolio_construction_review as p4
from pipeline import hkcu_p4_2_portfolio_construction_review_decision_adapter as p4a


def policy():
    return {
        "tier_weight_cap": {"CORE": 0.08, "WATCH": 0.05},
        "tier_risk_reference_weight": {"CORE": 0.06, "WATCH": 0.04},
        "single_name_loss_budget": {"CORE": 0.0125, "WATCH": 0.009},
        "drawdown_floor_abs": 0.15,
        "direct_sector_weight_limit": 0.20,
        "direct_style_weight_limit": 0.30,
        "max_position_fraction_of_adv": 0.0025,
        "minimum_actionable_weight": 0.005,
        "probe_hard_cap": {"REAL": 0.015, "SIMULATION": 0.02},
        "material_confidence_cap": {"REAL": 0.0, "SIMULATION": 0.015},
        "bounded_confidence_cap_two_plus": 0.025,
        "quantitative_only_thesis_cap": 0.03,
        "marginal_risk_multiplier": {
            "IMPROVES_DIVERSIFICATION": 1.0,
            "DIVERSIFIES_RETURN_STREAM_BUT_RAISES_RISK_BUDGET": 0.8,
            "MIXED_RISK_CONTRIBUTION": 0.6,
            "ADDS_CORRELATED_RISK": 0.4,
            "UNRESOLVED": 0.0,
        },
        "opportunity_cost_multiplier": {
            "LOW_RELATIVE_OPPORTUNITY_COST": 1.0,
            "MODERATE_RELATIVE_OPPORTUNITY_COST": 0.75,
            "HIGH_RELATIVE_OPPORTUNITY_COST": 0.0,
            "UNRESOLVED": 0.0,
        },
        "suggested_range_fraction": {
            "PRIMARY_BUILD_REVIEW": {"min": 0.5, "max": 1.0},
            "SECONDARY_BUILD_REVIEW": {"min": 0.35, "max": 1.0},
            "PROBE_BUILD_REVIEW": {"min": 0.25, "max": 1.0},
        },
    }


def row(**kw):
    x = {
        "fit_state": "FIT",
        "opportunity_cost_state": "LOW_RELATIVE_OPPORTUNITY_COST",
        "marginal_risk_state": "IMPROVES_DIVERSIFICATION",
        "sector_impact_state": "ADDS_NEW_DIRECT_SECTOR_EXPOSURE",
        "style_impact_state": "ADDS_DISTINCT_STYLE_EXPOSURE",
        "portfolio_style": "QUALITY",
        "ah_overlap_security_ids": "",
        "direct_overlap_security_ids": "",
        "candidate_annualized_volatility": 0.20,
        "portfolio_annualized_volatility": 0.20,
        "max_drawdown_120d": -0.20,
        "existing_same_sector_weight": 0.0,
        "existing_same_style_weight": 0.0,
    }
    x.update(kw)
    return pd.Series(x)


def candidate(**kw):
    x = {
        "candidate_tier": "WATCH",
        "material_confidence_cap_count": 0,
        "bounded_confidence_cap_count": 0,
        "thesis_strength": "COMPANY_EVIDENCE_SUPPORTED",
    }
    x.update(kw)
    return pd.Series(x)


def account_state():
    return {"summary": {"account_total_assets": 1_000_000.0, "execution_cash_balance": 0.0}, "holdings": []}


def test_classification_semantics():
    assert p4.classify_state(row(), candidate(), "REAL")[0] == "PRIMARY_BUILD_REVIEW"
    assert p4.classify_state(row(opportunity_cost_state="HIGH_RELATIVE_OPPORTUNITY_COST"), candidate(), "REAL")[0] == "WATCH_NO_SIZE"
    assert p4.classify_state(row(ah_overlap_security_ids="000333.SZ"), candidate(), "SIMULATION")[0] == "SUBSTITUTION_REVIEW_ONLY"
    assert p4.classify_state(row(fit_state="NO_INCREMENTAL_ROLE"), candidate(), "REAL")[0] == "NO_INCREMENTAL_ROLE"
    assert p4.classify_state(row(), candidate(material_confidence_cap_count=1), "REAL")[0] == "WATCH_NO_SIZE"
    assert p4.classify_state(row(), candidate(material_confidence_cap_count=1), "SIMULATION")[0] == "PROBE_BUILD_REVIEW"


def test_independent_caps_are_non_offsetting_minimum():
    hk = pd.Series({"avg_turnover_hkd_20d": 100_000_000.0})
    caps = p4.independent_caps(row(), candidate(), hk, "REAL", account_state(), policy())
    assert caps["tier_cap"] == 0.05
    assert abs(caps["volatility_cap"] - 0.04) < 1e-12
    assert abs(caps["historical_drawdown_loss_cap"] - 0.045) < 1e-12
    wmin, wmax, cap = p4.apply_envelope("PRIMARY_BUILD_REVIEW", caps, policy(), "REAL")
    assert abs(cap - 0.04) < 1e-12
    assert abs(wmin - 0.02) < 1e-12
    assert abs(wmax - 0.04) < 1e-12


def test_concentration_room_can_close_envelope():
    hk = pd.Series({"avg_turnover_hkd_20d": 100_000_000.0})
    r = row(sector_impact_state="INCREASES_EXISTING_DIRECT_SECTOR", existing_same_sector_weight=0.20)
    caps = p4.independent_caps(r, candidate(), hk, "REAL", account_state(), policy())
    assert caps["sector_room_cap"] == 0.0
    assert p4.apply_envelope("SECONDARY_BUILD_REVIEW", caps, policy(), "REAL")[1] == 0.0


def test_probe_hard_cap_and_nonactionable_zero():
    caps = {k: 0.05 for k in [
        "tier_cap", "volatility_cap", "historical_drawdown_loss_cap", "marginal_risk_cap",
        "opportunity_cost_cap", "confidence_cap", "sector_room_cap", "style_room_cap", "liquidity_cap",
    ]}
    _, wmax, cap = p4.apply_envelope("PROBE_BUILD_REVIEW", caps, policy(), "REAL")
    assert wmax == 0.015
    assert cap == 0.015
    assert p4.apply_envelope("WATCH_NO_SIZE", caps, policy(), "REAL") == (0.0, 0.0, 0.0)


def test_combined_routes():
    assert p4.combined_route("PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW") == "ADVANCE_DUAL_SCENARIO_TEST"
    assert p4.combined_route("PRIMARY_BUILD_REVIEW", "WATCH_NO_SIZE") == "ADVANCE_REAL_SCENARIO_TEST"
    assert p4.combined_route("WATCH_NO_SIZE", "PROBE_BUILD_REVIEW") == "ADVANCE_SIMULATION_SCENARIO_TEST"
    assert p4.combined_route("SUBSTITUTION_REVIEW_ONLY", "WATCH_NO_SIZE") == "ADVANCE_SUBSTITUTION_SCENARIO_TEST"
    assert p4.combined_route("WATCH_NO_SIZE", "NO_INCREMENTAL_ROLE") == "HOLD_PORTFOLIO_WATCH"
    assert p4a.combined_route("PROBE_BUILD_REVIEW", "SUBSTITUTION_REVIEW_ONLY") == "ADVANCE_MIXED_NEW_AND_SUBSTITUTION_SCENARIO_TEST"


def test_direct_equity_style_scope_excludes_fixed_income():
    state = {
        "summary": {"account_total_assets": 1_000_000.0},
        "holdings": [
            {"security_id": "FUND:1.OF", "asset_class": "BOND_FUND", "market_value": 400_000.0},
            {"security_id": "SHSE:510500.SH", "asset_class": "ETF", "security_name": "A500 ETF", "code": "510500", "market_value": 100_000.0},
        ],
    }
    assert abs(p4a.non_direct_style_weight(state, "DEFENSIVE") - 0.4) < 1e-12
    assert abs(p4a.non_direct_style_weight(state, "BROAD_MARKET") - 0.1) < 1e-12
    r = row(
        portfolio_style="DEFENSIVE",
        style_impact_state="INCREASES_EXISTING_STYLE",
        existing_same_style_weight=0.4,
    )
    hk = pd.Series({"avg_turnover_hkd_20d": 100_000_000.0})
    caps = p4a.construction_caps(r, candidate(), hk, "REAL", state, policy())
    assert r["existing_same_style_weight"] == 0.0
    assert caps["style_room_cap"] == 0.30
    assert min(caps.values()) <= 0.05


def test_ah_substitution_ignores_net_new_sector_style_room():
    r = row(
        ah_overlap_security_ids="000333.SZ",
        sector_impact_state="INCREASES_EXISTING_DIRECT_SECTOR",
        style_impact_state="INCREASES_EXISTING_STYLE",
        existing_same_sector_weight=0.30,
        existing_same_style_weight=0.40,
    )
    hk = pd.Series({"avg_turnover_hkd_20d": 100_000_000.0})
    caps = p4a.construction_caps(r, candidate(), hk, "SIMULATION", account_state(), policy())
    assert caps["sector_room_cap"] == 0.05
    assert caps["style_room_cap"] == 0.05


def test_contract_keeps_phase_boundary_closed():
    contract = json.loads(Path("config/hkcu_p4_2_portfolio_construction_review_contract.json").read_text(encoding="utf-8"))
    assert contract["construction_policy"]["weighted_score_allowed"] is False
    assert contract["construction_policy"]["fixed_top_n_allowed"] is False
    assert contract["construction_policy"]["individual_envelopes_are_non_additive"] is True
    assert contract["construction_policy"]["direct_style_scope"] == "DIRECT_EQUITY_ONLY_EXCLUDES_FIXED_INCOME_AND_GENERIC_POOLED"
    assert contract["construction_policy"]["substitution_policy"]["substitution_is_exposure_neutral_for_net_new_sector_style_room"] is True
    assert contract["phase_boundary"]["aggregate_portfolio_allocation_authorized"] is False
    assert contract["phase_boundary"]["order_creation_authorized"] is False
    assert contract["phase_boundary"]["trade_authority"] == "NONE"
