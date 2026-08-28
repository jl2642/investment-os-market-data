from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))


def validate():
    e=[]
    c=load("PHASE4_P4_3_UNIFIED_DECISION_RECOMMENDATION_CONTRACT.json")
    s=load("PROGRAM_STATE.json")
    a=load("PROGRAM_AMENDMENT_A1.json")

    if c.get("status")!="FROZEN_PRE_IMPLEMENTATION":
        e.append("P43_NOT_FROZEN")
    p=c.get("parent",{})
    if p.get("p4_2_status")!="COMPLETE_ACCEPTED":
        e.append("P43_P42_NOT_ACCEPTED")
    fps=p.get("p4_2_cycle_fingerprints",[])
    if len(fps)<2 or len(set(fps))<2:
        e.append("P43_P42_FINGERPRINT_EVIDENCE")
    if not p.get("phase4_effective_forward_execution_hold"):
        e.append("P43_FORWARD_HOLD")

    audit=c.get("pre_implementation_audit",{})
    if audit.get("finding")!="DECISION_CAPABILITY_EXISTS_BUT_IS_FRAGMENTED_STALE_AND_NOT_UNIFIED_UNDER_ONE_CURRENT_AUTHORITY":
        e.append("P43_AUDIT_FINDING")
    d2=audit.get("current_d2_snapshot",{})
    if d2.get("research_complete_count")!=2 or d2.get("research_hold_evidence_gap_count")!=1:
        e.append("P43_D2_AUDIT_COUNTS")

    reuse=c.get("existing_capability_reuse",{})
    if reuse.get("new_ranking_model_authorized"):
        e.append("P43_NEW_RANKER")
    if reuse.get("legacy_recommendation_reactivation_without_revalidation_authorized"):
        e.append("P43_STALE_REACTIVATION")

    tax=c.get("recommendation_state_taxonomy",{})
    if tax.get("opportunity_states") != [
        "BUY_NOW","BUY_ON_PRICE","BUY_ON_EVIDENCE","WATCH_HIGH_PRIORITY","WATCH_NORMAL","AVOID"
    ]:
        e.append("P43_OPPORTUNITY_TAXONOMY")
    if tax.get("existing_position_states") != ["ADD","HOLD","TRIM_REVIEW","EXIT_REVIEW"]:
        e.append("P43_POSITION_TAXONOMY")
    if tax.get("states_are_research_judgments_not_orders") is not True:
        e.append("P43_STATE_AUTHORITY")

    required=set(c.get("required_record_fields",[]))
    required_expected={
        "security_id","security_name","market","subject_type","recommendation_state",
        "judgment_basis","research_status","evidence_status","valuation_status",
        "portfolio_fit_status","capital_comparison_status","triggers",
        "invalidation_conditions","portfolio_role","source_bindings","source_watermarks",
        "ready_for_user_decision","orders","trade_authority"
    }
    if required != required_expected:
        e.append("P43_REQUIRED_FIELDS")

    routing=c.get("routing_semantics",{})
    if routing.get("d2_research_complete_alone_may_trigger_buy") is not False:
        e.append("P43_D2_COMPLETE_BUY")
    if routing.get("stale_historical_decision_label_may_trigger_current_recommendation") is not False:
        e.append("P43_STALE_DECISION")
    if routing.get("missing_required_input_may_be_silently_filled") is not False:
        e.append("P43_SILENT_FILL")
    if len(routing.get("buy_now_requires_all",[]))<6:
        e.append("P43_BUY_NOW_GATES")
    if "CURRENT_VERIFIED_EXISTING_POSITION" not in routing.get("add_requires",[]):
        e.append("P43_ADD_POSITION_GATE")
    if "CURRENT_VERIFIED_EXISTING_POSITION" not in routing.get("trim_review_requires",[]):
        e.append("P43_TRIM_POSITION_GATE")

    score=c.get("recommendation_score_policy",{})
    for key in [
        "global_scalar_recommendation_score_forbidden",
        "dimension_weights_forbidden",
        "outcome_tuned_thresholds_forbidden",
        "r2_exact_signature_pareto_semantics_may_not_be_rewritten",
    ]:
        if score.get(key) is not True:
            e.append("P43_SCORE_POLICY_"+key)
    if score.get("historical_realized_outcomes_may_influence_current_recommendation") is not False:
        e.append("P43_OUTCOME_LEAK")

    cross=c.get("cross_market_semantics",{})
    if cross.get("supported_market_labels") != ["A_SHARE","H_SHARE","US_SHARE"]:
        e.append("P43_MARKETS")
    if cross.get("cross_market_scalar_ranking_allowed") is not False:
        e.append("P43_CROSS_MARKET_RANK")

    op=c.get("operating_surface",{})
    if op.get("branch")!="operating-current" or op.get("operating_domain")!="RECOMMENDATION":
        e.append("P43_OPERATING_SURFACE")
    if op.get("protected_economic_authority"):
        e.append("P43_OPERATING_AUTHORITY")

    fresh=c.get("freshness_semantics",{})
    if fresh.get("same_source_fingerprint_must_not_advance_current") is not True:
        e.append("P43_FALSE_FRESHNESS")
    if fresh.get("synthetic_single_as_of_forbidden") is not True:
        e.append("P43_SYNTHETIC_ASOF")
    if fresh.get("stale_portfolio_context_must_block_position_action_escalation") is not True:
        e.append("P43_STALE_PORTFOLIO")

    gate=c.get("acceptance_gate",{})
    for key in [
        "all_current_research_complete_d2_assets_have_explicit_recommendation_state",
        "evidence_gap_d2_assets_have_explicit_non_buy_state_and_trigger",
        "every_buy_now_or_add_record_satisfies_all_mandatory_gates",
        "every_state_has_trigger_or_invalidation_context",
        "deterministic_rebuild_same_inputs_same_semantics",
        "same_source_fingerprint_no_current_advance",
        "no_stale_legacy_action_reactivated_without_revalidation",
        "a_h_us_schema_support_present",
        "protected_economic_state_unchanged",
    ]:
        if gate.get(key) is not True:
            e.append("P43_GATE_"+key)
    if gate.get("minimum_live_operating_cycles")!=1:
        e.append("P43_LIVE_GATE")
    if gate.get("orders")!=0 or gate.get("trade_authority")!="NONE":
        e.append("P43_GATE_AUTHORITY")

    if a["effective_execution_control"].get("effective_forward_observation_start_allowed"):
        e.append("P43_A1_HOLD_OPEN")
    if s.get("phase4_p4_2_complete") is not True:
        e.append("P43_STATE_P42")
    if s.get("phase4_p4_2_distinct_cycle_fingerprint_count",0)<2:
        e.append("P43_STATE_P42_CYCLES")
    if s.get("phase4_reconciliation_current_stage")!="P4_3_UNIFIED_DECISION_AND_RECOMMENDATION_ENGINE":
        e.append("P43_STATE_STAGE")
    if s.get("phase4_p4_3_contract_frozen") is not True:
        e.append("P43_STATE_CONTRACT")
    if s.get("phase4_p4_3_implementation_started") is not False or s.get("phase4_p4_3_complete") is not False:
        e.append("P43_STATE_IMPLEMENTATION")
    if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0:
        e.append("P43_FORWARD_EVIDENCE")

    for k,v in c.get("protected_state",{}).items():
        if k=="trade_authority":
            if v!="NONE":
                e.append("P43_TRADE")
        elif v!=0:
            e.append("P43_PROTECTED_"+k)

    lane=c.get("implementation_lane",{})
    if lane.get("main_based_operational_pr_required") is not True:
        e.append("P43_MAIN_LANE")
    if lane.get("must_not_merge_strategy_kernel_stacked_chain_into_main") is not True:
        e.append("P43_STACKED_BOUNDARY")
    if lane.get("expected_transaction_count_after_contract")!=1:
        e.append("P43_TRANSACTION_COUNT")
    if lane.get("next_after_acceptance")!="P4_4_TRIGGER_MONITOR_AND_AUTONOMOUS_SHADOW_BOOK":
        e.append("P43_NEXT")

    return sorted(set(e))


if __name__=="__main__":
    err=validate()
    if err:
        raise AssertionError(";".join(err))
    print("PHASE4_P4_3_UNIFIED_DECISION_RECOMMENDATION_CONTRACT_PASS p4_2_cycles=2 forward_observations=0 orders=0 trade_authority=NONE")
