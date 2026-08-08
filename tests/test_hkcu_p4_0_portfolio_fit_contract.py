from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p4_0_portfolio_fit_contract.json"
VALIDATOR = ROOT / "scripts/validate_hkcu_p4_0_portfolio_fit_contract.py"


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_identity_and_zero_mutation_boundary():
    c = load_contract()
    assert c["program_id"] == "HKCU-P4-0"
    assert c["phase"] == "P4_0_PORTFOLIO_FIT_CONTRACT"
    assert c["as_of_date"] == "2026-08-07"
    b = c["phase_boundary"]
    assert b["contract_definition_authorized"] is True
    for key in [
        "portfolio_fit_assessment_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_admission_authorized",
        "simulation_mutation_authorized",
        "real_account_admission_authorized",
        "real_account_mutation_authorized",
        "portfolio_sizing_authorized",
        "portfolio_allocation_authorized",
        "order_creation_authorized",
    ]:
        assert b[key] is False
    assert b["trade_authority"] == "NONE"


def test_p3_2_formal_candidate_entry_is_frozen():
    a = load_contract()["authoritative_upstream"]
    assert a["required_program_id"] == "HKCU-P3-2"
    assert a["required_pass_status"] == "PASS_P3_2_CANDIDATE_POOL_PROMOTION"
    assert a["required_next_gate"] == "P4_0_PORTFOLIO_FIT_CONTRACT"
    assert a["entry_candidate_count"] == 70
    assert a["core_candidate_count"] == 2
    assert a["watch_candidate_count"] == 68
    assert a["accepted_candidate_current_sha256"] == "6b6487a157208e8d5a29fcf37b60b86799a3ed0cf8f206b884dbb4892e6f8f0f"


def test_portfolio_context_preserves_real_and_simulation_semantics():
    p = load_contract()["portfolio_context"]
    assert p["required_real_state_id"] == "WP2R_REAL_POSITIONS_CURRENT"
    assert p["required_simulation_state_id"] == "WP2R_SIMULATION_POSITIONS_CURRENT"
    assert p["required_portfolio_fit_permission"] is True
    assert p["required_trade_authority"] == "NONE"
    assert p["real_cash_semantics"] == "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED"
    assert p["simulation_cash_semantics"] == "SIMULATION_LEDGER_AVAILABLE_CASH"
    assert p["real_account_fixed_strategic_cash_target_allowed"] is False
    assert p["portfolio_state_must_be_current_at_assessment_time"] is True
    assert p["all_positions_must_be_marked_for_assessment"] is True
    assert p["marks_must_be_fresh_or_acceptable_for_assessment"] is True


def test_fit_philosophy_is_marginal_separate_and_non_scored():
    p = load_contract()["portfolio_fit_philosophy"]
    for key in [
        "candidate_quality_is_not_portfolio_fit",
        "candidate_core_is_not_automatic_allocation",
        "candidate_watch_is_not_automatic_rejection",
        "portfolio_fit_is_marginal_not_standalone",
        "real_and_simulation_fit_must_be_assessed_separately",
        "existing_exposure_is_not_automatic_rejection",
        "diversification_claim_requires_explicit_portfolio_evidence",
        "strong_company_thesis_can_have_no_incremental_portfolio_role",
        "missing_decision_critical_portfolio_context_requires_defer",
        "fit_assessment_is_not_position_sizing",
        "fit_assessment_is_not_trade_authority",
    ]:
        assert p[key] is True
    for key in [
        "weighted_composite_score_allowed",
        "neutral_fill_allowed",
        "automatic_waiver_allowed",
        "arbitrary_fixed_top_n_allowed",
        "real_account_fixed_strategic_cash_target_allowed",
    ]:
        assert p[key] is False


def test_rule_registry_covers_portfolio_fit_dimensions():
    rules = load_contract()["portfolio_fit_rules"]
    assert len(rules) == 15
    assert {r["rule_id"] for r in rules} == {f"P4R{i:02d}" for i in range(1, 16)}
    assert sum(r["type"] == "HARD" for r in rules) == 7
    assert sum(r["type"] == "DECISION" for r in rules) == 8
    names = {r["name"] for r in rules}
    for required in [
        "FORMAL_ACTIVE_HK_CANDIDATE_LINEAGE",
        "CURRENT_PORTFOLIO_STATE_AND_MARK_WATERMARKS",
        "EXPOSURE_IDENTITY_MAPPING_COMPLETE",
        "PORTFOLIO_ROLE_EXPLICIT",
        "DIRECT_AND_CROSS_LISTED_OVERLAP_REVIEW",
        "SECTOR_AND_INDUSTRY_CONCENTRATION_IMPACT",
        "FACTOR_STYLE_AND_THEME_CONCENTRATION_IMPACT",
        "MARGINAL_DIVERSIFICATION_AND_RISK_CONTRIBUTION",
        "VALUATION_EXPECTED_RETURN_AND_OPPORTUNITY_COST",
        "DOWNSIDE_BUDGET_AND_SIZING_ENVELOPE_EXPLICIT",
        "FUNDING_AND_CASH_SEMANTICS_PRESERVED",
    ]:
        assert required in names


def test_account_fit_states_and_combined_routes_are_separate():
    c = load_contract()
    assert set(c["account_fit_states"]) == {
        "FIT",
        "FIT_WITH_CONSTRAINTS",
        "NO_INCREMENTAL_ROLE",
        "DEFER_PORTFOLIO_CONTEXT",
        "BLOCK_PORTFOLIO_FIT",
    }
    assert set(c["combined_routing_states"]) == {
        "ADVANCE_DUAL_CONSTRUCTION_REVIEW",
        "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW",
        "ADVANCE_REAL_ACCOUNT_REVIEW",
        "HOLD_PORTFOLIO_WATCH",
        "DEFER_PORTFOLIO_CONTEXT",
        "BLOCK_PORTFOLIO_FIT",
    }
    r = c["routing_contract"]
    assert r["positive_fit_requires_all_applicable_hard_rules_pass"] is True
    assert r["simulation_and_real_account_states_must_both_be_explicit"] is True
    assert r["p4_1_is_assessment_only"] is True
    assert r["p4_1_portfolio_mutation_authorized"] is False
    assert r["construction_or_admission_requires_separate_later_gate"] is True


def test_acceptance_freezes_contract_only_and_next_gate():
    a = load_contract()["acceptance"]
    assert a["portfolio_fit_rule_count"] == 15
    assert a["hard_rule_count"] == 7
    assert a["decision_rule_count"] == 8
    assert a["entry_candidate_count"] == 70
    assert a["core_candidate_count"] == 2
    assert a["watch_candidate_count"] == 68
    assert a["portfolio_fit_assessment_count"] == 0
    assert a["candidate_pool_mutations"] == 0
    assert a["simulation_mutations"] == 0
    assert a["real_account_mutations"] == 0
    assert a["portfolio_allocations"] == 0
    assert a["orders_created"] == 0
    assert a["pass_status"] == "PASS_P4_0_PORTFOLIO_FIT_CONTRACT"
    assert a["next_gate"] == "P4_1_PORTFOLIO_FIT_ASSESSMENT"
    assert a["trade_authority"] == "NONE"


def test_validator_enforces_required_semantics():
    text = VALIDATOR.read_text(encoding="utf-8")
    for token in [
        "EXPECTED_RULE_IDS",
        "EXPECTED_ACCOUNT_STATES",
        "EXPECTED_COMBINED_ROUTES",
        "accepted_candidate_current_sha256",
        "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED",
        "SIMULATION_LEDGER_AVAILABLE_CASH",
        "P4_1_PORTFOLIO_FIT_ASSESSMENT",
        "weighted_composite_score_allowed",
        "arbitrary_fixed_top_n_allowed",
        "portfolio_fit_assessment_count",
        "trade_authority",
    ]:
        assert token in text
