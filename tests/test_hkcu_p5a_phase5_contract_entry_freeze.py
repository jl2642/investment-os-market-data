import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p5a_phase5_contract_entry_freeze.json"


def load_contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_phase5_business_gate_sequence_is_frozen_once():
    c = load_contract()
    ids = [x["gate_id"] for x in c["phase_5_gate_sequence"]]
    assert ids == ["P5A", "P5B", "P5C", "P5D", "P5E"]
    assert c["planning_governance"]["frozen_business_gate_ids"] == ids
    assert c["planning_governance"]["business_gate_count"] == 5
    assert c["planning_governance"]["additional_phase_5_business_gates_allowed"] is False
    assert c["planning_governance"]["p5f_or_later_business_gate_authorized"] is False
    assert c["planning_governance"]["phase_6_creation_authorized"] is False


def test_repair_may_not_expand_business_scope_or_authority():
    c = load_contract()
    assert c["planning_governance"]["repair_subgates_allowed"] is True
    rule = c["planning_governance"]["repair_subgate_rule"]
    assert "may not create a new business objective" in rule
    assert "expand authority" in rule
    assert "silently change the Phase 5 entry proposal" in rule


def test_p5a_is_freeze_only_and_trade_authority_none():
    c = load_contract()
    b = c["phase_boundary"]
    assert b["entry_freeze_authorized"] is True
    assert b["lineage_hashing_authorized"] is True
    assert b["gate_register_authorized"] is True
    assert b["pretrade_memo_authorized"] is False
    assert b["user_trade_confirmation_record_authorized"] is False
    assert b["manual_execution_checklist_authorized"] is False
    assert b["target_portfolio_writeback_authorized"] is False
    assert b["candidate_pool_mutation_authorized"] is False
    assert b["simulation_mutation_authorized"] is False
    assert b["real_account_mutation_authorized"] is False
    assert b["order_creation_authorized"] is False
    assert b["broker_execution_authorized"] is False
    assert b["trade_authority"] == "NONE"


def test_entry_is_exact_p4_4_preferred_surface():
    c = load_contract()
    e = c["entry_contract"]
    assert e["required_p4_4_status"] == "PASS_P4_4_PORTFOLIO_PROPOSAL_REVIEW"
    assert e["required_p4_4_phase_close_status"] == "PHASE_4_CLOSED"
    assert e["required_p4_4_additional_subphases_allowed"] is False
    assert e["required_preferred_proposal_count"] == 2
    assert e["required_real_preferred_scenario"] == "REAL_CONSERVATIVE"
    assert e["required_real_hk_sleeve"] == 0.05
    assert e["required_real_position_count"] == 4
    assert e["required_simulation_preferred_scenario"] == "SIM_BALANCED"
    assert e["required_simulation_hk_sleeve"] == 0.15
    assert e["required_simulation_position_count"] == 9
    assert e["required_proposal_allocation_count"] == 13
    assert e["required_trade_authority"] == "NONE"


def test_core_pretrade_sequence_is_preserved():
    c = load_contract()
    gates = {x["gate_id"]: x for x in c["phase_5_gate_sequence"]}
    assert gates["P5B"]["entry_permission"] == "RESEARCH_ONLY"
    assert gates["P5B"]["exit_permission"] == "USER_DECISION_REQUIRED"
    assert gates["P5C"]["approval_permission_label"] == "USER_APPROVED_MANUAL_EXECUTION"
    assert gates["P5C"]["trade_authority_after_approval"] == "NONE"
    assert gates["P5D"]["requires_explicit_user_approval"] is True
    assert gates["P5D"]["broker_execution_authorized"] is False
    assert gates["P5E"]["real_writeback_requires_user_supplied_execution_fact"] is True
    assert gates["P5E"]["simulation_writeback_requires_explicit_activation_record"] is True


def test_real_cash_rule_is_not_reintroduced_as_target_cash_bucket():
    c = load_contract()
    r = c["portfolio_and_cash_rules"]
    assert r["real_account_cash_is_execution_balance_not_strategic_asset_bucket"] is True
    assert r["ranking_or_weighted_score_may_authorize_real_capital"] is False
    assert r["simulation_result_may_authorize_real_capital"] is False


def test_acceptance_moves_only_to_p5b():
    c = load_contract()
    a = c["acceptance"]
    assert a["phase_5_plan_frozen"] is True
    assert a["additional_phase_5_business_gates_allowed"] is False
    assert a["pretrade_memo_produced"] is False
    assert a["user_trade_confirmation_recorded"] is False
    assert a["manual_execution_checklist_produced"] is False
    assert a["target_portfolio_writeback"] is False
    assert a["orders_created"] == 0
    assert a["next_gate_on_pass"] == "P5B_REAL_PRETRADE_MEMO"
    assert a["trade_authority"] == "NONE"
