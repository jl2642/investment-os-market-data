from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def validate():
    e=[]
    c=load("PHASE4_P4_4_TRIGGER_MONITOR_AUTONOMOUS_SHADOW_BOOK_CONTRACT.json")
    s=load("PROGRAM_STATE.json")
    a=load("PROGRAM_AMENDMENT_A1.json")

    if c.get("status")!="FROZEN_PRE_IMPLEMENTATION": e.append("P44_NOT_FROZEN")
    p=c.get("parent",{})
    if p.get("p4_3_status")!="COMPLETE_ACCEPTED": e.append("P44_P43_NOT_ACCEPTED")
    if not p.get("phase4_effective_forward_execution_hold"): e.append("P44_FORWARD_HOLD")
    if not p.get("p4_3_recommendation_fingerprint"): e.append("P44_P43_FINGERPRINT")

    snap=c.get("pre_implementation_audit",{}).get("current_recommendation_snapshot",{})
    if snap.get("record_count")!=3: e.append("P44_RECORD_COUNT")
    if snap.get("explicit_trigger_clause_count")!=7: e.append("P44_TRIGGER_COUNT")
    if snap.get("explicit_invalidation_clause_count")!=6: e.append("P44_INVALIDATION_COUNT")
    if snap.get("buy_now_count")!=0 or snap.get("add_count")!=0: e.append("P44_ACTIONABLE_CURRENT")

    tm=c.get("trigger_monitor",{})
    if tm.get("natural_language_clause_keyword_inference_authorized") is not False: e.append("P44_NLP")
    if tm.get("semantic_clause_may_fire_without_governed_evidence") is not False: e.append("P44_SEMANTIC_FIRE")
    if tm.get("duplicate_event_policy")!="NO_OP_ALREADY_PROCESSED": e.append("P44_IDEMPOTENCY")
    if tm.get("out_of_order_event_policy")!="REJECT_AND_PRESERVE_CURRENT": e.append("P44_ORDERING")

    sb=c.get("shadow_book",{})
    units=sb.get("exposure_unit_policy",{})
    if float(units.get("normalized_research_units_per_open_signal",0))!=1.0: e.append("P44_UNIT")
    for k in ["units_are_capital_weights","cash_budget_exists","portfolio_sizing_claim_allowed","cross_security_portfolio_return_claim_allowed"]:
        if units.get(k) is not False: e.append("P44_UNIT_POLICY_"+k)

    entry=sb.get("entry_policy",{})
    if entry.get("action_states")!=["BUY_NOW","ADD"]: e.append("P44_ENTRY")
    if entry.get("no_direct_natural_language_trigger_to_entry") is not True: e.append("P44_DIRECT_NLP_ENTRY")
    exitp=sb.get("exit_policy",{})
    if exitp.get("action_states")!=["AVOID","EXIT_REVIEW"]: e.append("P44_EXIT")
    if exitp.get("trim_review_is_not_automatic_exit") is not True: e.append("P44_TRIM")
    if exitp.get("watch_or_hold_is_not_automatic_exit") is not True: e.append("P44_WATCH_EXIT")

    mark=sb.get("mark_binding",{})
    for k in ["same_session_hindsight_fill_forbidden","future_mark_required_for_pending_action","missing_mark_keeps_action_pending","mark_source_identity_required","market_session_identity_required"]:
        if mark.get(k) is not True: e.append("P44_MARK_"+k)

    fw=c.get("pre_baseline_firewall",{})
    if fw.get("p4_4_live_runs_are_infrastructure_validation_only") is not True: e.append("P44_FIREWALL")
    if fw.get("pre_p4_5_actions_may_count_as_phase4_forward_observations") is not False: e.append("P44_OBS_LEAK")
    if fw.get("pre_p4_5_market_outcomes_may_tune_model") is not False: e.append("P44_TUNING_LEAK")
    if fw.get("p4_5_must_freeze_new_clean_cutoff") is not True: e.append("P44_CLEAN_CUTOFF")
    if fw.get("p4_5_may_not_backdate_clean_cutoff") is not True: e.append("P44_BACKDATE")

    live=c.get("current_live_expected_result",{})
    if live.get("registered_subject_count")!=3 or live.get("registered_trigger_clause_count")!=7 or live.get("registered_invalidation_clause_count")!=6:
        e.append("P44_LIVE_REGISTRY")
    if live.get("shadow_action_count")!=0 or live.get("shadow_open_position_count")!=0:
        e.append("P44_LIVE_SHADOW")

    gate=c.get("acceptance_gate",{})
    required=[
        "all_current_recommendation_clauses_registered",
        "semantic_clauses_not_auto_fired_without_evidence",
        "current_live_zero_action_result_matches_recommendation_state",
        "deterministic_same_input_same_semantics",
        "duplicate_signal_idempotent",
        "out_of_order_signal_rejected",
        "synthetic_watch_to_buy_now_creates_one_entry_pending_action",
        "synthetic_repeated_buy_now_creates_no_duplicate_action",
        "synthetic_next_completed_session_mark_opens_shadow_position",
        "synthetic_buy_now_to_avoid_creates_exit_pending_action",
        "synthetic_next_completed_session_mark_closes_shadow_position",
        "same_session_hindsight_fill_rejected",
        "protected_simulation_unchanged",
        "protected_real_unchanged",
        "candidate_unchanged",
        "target_portfolio_unchanged",
        "pre_baseline_forward_observation_count_zero",
    ]
    for k in required:
        if gate.get(k) is not True: e.append("P44_GATE_"+k)
    if gate.get("orders")!=0 or gate.get("trade_authority")!="NONE": e.append("P44_AUTHORITY")

    if a["effective_execution_control"].get("effective_forward_observation_start_allowed"): e.append("P44_A1_OPEN")
    if s.get("phase4_p4_3_complete") is not True: e.append("P44_STATE_P43")
    stage=s.get("phase4_reconciliation_current_stage")
    if stage not in {
        "P4_4_TRIGGER_MONITOR_AND_AUTONOMOUS_SHADOW_BOOK",
        "P4_5_CLEAN_BASELINE_FORWARD_PARALLEL_SHADOW_VALIDATION",
    }:
        e.append("P44_STAGE")
    if s.get("phase4_p4_4_contract_frozen") is not True: e.append("P44_CONTRACT")
    if stage=="P4_4_TRIGGER_MONITOR_AND_AUTONOMOUS_SHADOW_BOOK":
        if s.get("phase4_p4_4_implementation_started") is not False or s.get("phase4_p4_4_complete") is not False:
            e.append("P44_IMPL")
    else:
        if s.get("phase4_p4_4_contract_status")!="COMPLETE_ACCEPTED":
            e.append("P44_ACCEPTANCE")
        if s.get("phase4_p4_4_implementation_started") is not True:
            e.append("P44_IMPL_NOT_STARTED")
        if s.get("phase4_p4_4_complete") is not True:
            e.append("P44_NOT_COMPLETE_BEFORE_P45")
        if not s.get("phase4_p4_4_source_fingerprint"):
            e.append("P44_SOURCE_FINGERPRINT_MISSING")
    if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0: e.append("P44_FORWARD_EVIDENCE")

    for k,v in c.get("protected_state",{}).items():
        if k=="trade_authority":
            if v!="NONE": e.append("P44_TRADE")
        elif v!=0:
            e.append("P44_PROTECTED_"+k)

    lane=c.get("implementation_lane",{})
    if lane.get("main_based_operational_pr_required") is not True: e.append("P44_MAIN")
    if lane.get("must_not_merge_strategy_kernel_stacked_chain_into_main") is not True: e.append("P44_STACKED")
    if lane.get("expected_transaction_count_after_contract")!=1: e.append("P44_TX_COUNT")
    if lane.get("next_after_acceptance")!="P4_5_CLEAN_BASELINE_FORWARD_PARALLEL_SHADOW_VALIDATION": e.append("P44_NEXT")
    return sorted(set(e))

if __name__=="__main__":
    err=validate()
    if err: raise AssertionError(";".join(err))
    print("PHASE4_P4_4_TRIGGER_MONITOR_AUTONOMOUS_SHADOW_BOOK_CONTRACT_PASS subjects=3 clauses=13 shadow_actions=0 observations=0 orders=0 trade_authority=NONE")
