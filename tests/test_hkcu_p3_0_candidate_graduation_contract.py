from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p3_0_candidate_graduation_contract.json"
VALIDATOR = ROOT / "scripts/validate_hkcu_p3_0_candidate_graduation_contract.py"


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_identity_and_boundary():
    c = load_contract()
    assert c["program_id"] == "HKCU-P3-0"
    assert c["phase"] == "P3_0_CANDIDATE_GRADUATION_CONTRACT"
    assert c["as_of_date"] == "2026-08-07"
    b = c["phase_boundary"]
    assert b["contract_definition_authorized"] is True
    for key in [
        "security_assessment_authorized",
        "formal_candidate_graduation_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_mutation_authorized",
        "real_account_mutation_authorized",
        "order_creation_authorized",
    ]:
        assert b[key] is False
    assert b["trade_authority"] == "NONE"


def test_upstream_counts_and_blockers_are_frozen():
    c = load_contract()["authoritative_upstream"]
    assert c["required_program_id"] == "HKCU-P2B-FINAL"
    assert c["required_pass_status"] == "PASS_P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS"
    assert c["required_next_gate"] == "P3_0_CANDIDATE_GRADUATION_CONTRACT"
    assert c["entry_security_count"] == 77
    assert c["evaluation_eligible_security_count"] == 72
    assert c["retained_blocker_security_count"] == 5
    assert set(c["retained_blocker_security_ids"]) == {
        "HKEX:00551", "HKEX:01114", "HKEX:02313", "HKEX:06110", "HKEX:09636"
    }


def test_graduation_philosophy_has_no_score_fill_or_fixed_topn():
    p = load_contract()["graduation_philosophy"]
    assert p["all_applicable_hard_rules_must_pass"] is True
    assert p["weighted_composite_score_allowed"] is False
    assert p["neutral_fill_allowed"] is False
    assert p["automatic_waiver_allowed"] is False
    assert p["arbitrary_fixed_top_n_allowed"] is False
    assert p["p2a_rank_is_context_not_graduation_authority"] is True
    assert p["missing_consensus_is_not_bearish"] is True
    assert p["confidence_cap_is_not_automatic_rejection"] is True
    assert p["ah_relative_value_is_context_not_alpha"] is True
    assert p["candidate_graduation_is_not_portfolio_allocation"] is True
    assert p["candidate_graduation_is_not_trade_authority"] is True


def test_rule_registry_is_explicit_and_complete():
    rules = load_contract()["graduation_rules"]
    assert len(rules) == 12
    assert {r["rule_id"] for r in rules} == {f"P3R{i:02d}" for i in range(1, 13)}
    assert sum(r["type"] == "HARD" for r in rules) == 9
    assert sum(r["type"] == "DECISION" for r in rules) == 3
    names = {r["name"] for r in rules}
    for required in [
        "NO_RETAINED_INVESTMENT_BLOCKER",
        "CURRENT_INVESTABILITY_AND_BUY_ELIGIBILITY",
        "DECISION_GRADE_MARKET_AND_FACTOR_FRESHNESS",
        "GOVERNANCE_VALUE_TRAP_NOT_SUBSTANTIVELY_BLOCKED",
        "EARNINGS_RISK_NOT_SUBSTANTIVELY_BLOCKED",
        "VALUATION_SUPPORT_EXPLICIT",
        "THESIS_FALSIFIER_AND_MONITOR_TRIGGER_EXPLICIT",
        "CROSS_LISTING_AND_DUPLICATE_EXPOSURE_REVIEW",
    ]:
        assert required in names


def test_assessment_and_promotion_are_separated():
    c = load_contract()
    assert set(c["assessment_states"]) == {
        "PROPOSE_CORE_CANDIDATE",
        "PROPOSE_WATCH_CANDIDATE",
        "DEFER_RESEARCH_MONITOR",
        "HOLD_RETAINED_INVESTMENT_BLOCKER",
    }
    p = c["promotion_contract"]
    assert p["p3_1_is_assessment_only"] is True
    assert p["p3_1_candidate_pool_mutation_authorized"] is False
    assert p["formal_promotion_requires_separate_gate"] == "P3_2_CANDIDATE_POOL_PROMOTION"
    assert p["promotion_does_not_authorize_simulation_or_real_trade"] is True
    assert p["automatic_trade_authority_after_promotion"] is False


def test_acceptance_freezes_zero_mutation_and_next_gate():
    a = load_contract()["acceptance"]
    assert a["graduation_rule_count"] == 12
    assert a["entry_security_count"] == 77
    assert a["evaluation_eligible_security_count"] == 72
    assert a["retained_blocker_security_count"] == 5
    assert a["formal_candidate_graduation_count"] == 0
    assert a["candidate_pool_mutations"] == 0
    assert a["simulation_mutations"] == 0
    assert a["real_account_mutations"] == 0
    assert a["orders_created"] == 0
    assert a["pass_status"] == "PASS_P3_0_CANDIDATE_GRADUATION_CONTRACT"
    assert a["next_gate"] == "P3_1_CANDIDATE_GRADUATION_ASSESSMENT"
    assert a["trade_authority"] == "NONE"


def test_validator_enforces_contract_semantics():
    text = VALIDATOR.read_text(encoding="utf-8")
    for token in [
        "EXPECTED_BLOCKERS",
        "EXPECTED_RULE_IDS",
        "P3_1_CANDIDATE_GRADUATION_ASSESSMENT",
        "P3_2_CANDIDATE_POOL_PROMOTION",
        "weighted_composite_score_allowed",
        "neutral_fill_allowed",
        "arbitrary_fixed_top_n_allowed",
        "formal_candidate_graduation_count",
        "trade_authority",
    ]:
        assert token in text
