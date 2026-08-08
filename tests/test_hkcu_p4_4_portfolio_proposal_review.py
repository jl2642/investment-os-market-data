from __future__ import annotations

import json
from pathlib import Path

from pipeline import hkcu_p4_4_portfolio_proposal_review as p4

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return json.loads((ROOT / "config/hkcu_p4_4_portfolio_proposal_review_contract.json").read_text(encoding="utf-8"))


def test_contract_closes_phase4_and_forbids_more_p4_subphases():
    c = contract()
    p = c["proposal_policy"]
    a = c["acceptance"]
    assert p["weighted_score_allowed"] is False
    assert p["fixed_top_n_allowed"] is False
    assert p["candidate_rank_may_authorize_proposal"] is False
    assert p["real_preferred_scenario"] == "REAL_CONSERVATIVE"
    assert p["simulation_preferred_scenario"] == "SIM_BALANCED"
    assert p["ah_stress_scenarios_are_research_only"] is True
    assert p["phase_4_is_closed_on_pass"] is True
    assert p["additional_p4_subphases_after_pass_allowed"] is False
    assert a["phase_close_status"] == "PHASE_4_CLOSED"
    assert a["next_phase_on_pass"] == "PHASE_5_PRETRADE_AND_STAGED_MIGRATION"
    assert c["phase_boundary"]["pretrade_memo_authorized"] is False
    assert c["phase_boundary"]["order_creation_authorized"] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_real_scenario_review_uses_staged_capital_migration():
    p = contract()["proposal_policy"]
    state, rationale = p4.scenario_review_state("REAL_CONSERVATIVE", "BASE_NEW_BUILD", p)
    assert state == "PREFERRED_PORTFOLIO_PROPOSAL"
    assert "external funding" in rationale
    state, _ = p4.scenario_review_state("REAL_BALANCED", "BASE_NEW_BUILD", p)
    assert state == "CONDITIONAL_EXPANSION_ALTERNATIVE"
    state, _ = p4.scenario_review_state("REAL_EXPANDED", "BASE_NEW_BUILD", p)
    assert state == "HOLD_EXPANSION"


def test_simulation_balanced_is_observation_proposal_not_expected_return_claim():
    p = contract()["proposal_policy"]
    state, rationale = p4.scenario_review_state("SIM_BALANCED", "BASE_NEW_BUILD", p)
    assert state == "PREFERRED_PORTFOLIO_PROPOSAL"
    assert "observation" in rationale
    state, _ = p4.scenario_review_state("SIM_CONSERVATIVE", "BASE_NEW_BUILD", p)
    assert state == "CONSERVATIVE_ALTERNATIVE"
    state, _ = p4.scenario_review_state("SIM_EXPANDED", "BASE_NEW_BUILD", p)
    assert state == "CONDITIONAL_EXPANSION_ALTERNATIVE"


def test_ah_stress_never_becomes_preferred_proposal():
    p = contract()["proposal_policy"]
    state, rationale = p4.scenario_review_state("SIM_BALANCED_AH_STRESS", "MAX_AH_SUBSTITUTION_STRESS", p)
    assert state == "RESEARCH_ONLY_AH_SUBSTITUTION"
    assert "not alpha" in rationale


def test_account_weight_helpers_are_non_authoritative():
    state = {
        "summary": {"account_total_assets": 1_000_000.0, "execution_cash_balance": 10_000.0},
        "holdings": [
            {"security_id": "HKEX:00001", "market_value": 50_000.0},
            {"security_id": "SHSE:600000.SH", "market_value": 940_000.0},
        ],
        "trade_authority": "NONE",
    }
    assert p4.account_assets(state) == 1_000_000.0
    assert abs(p4.current_weight(state, "HKEX:00001") - 0.05) < 1e-12
    assert p4.current_weight(state, "HKEX:99999") == 0.0
