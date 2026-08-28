from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def validate():
    errors=[]
    a=load_json("PROGRAM_AMENDMENT_A1.json")
    c=load_json("PROGRAM_CONTRACT.json")
    s=load_json("PROGRAM_STATE.json")
    cur=load_json("CURRENT_PHASE_STATUS.json")
    texts={name:(ROOT/name).read_text(encoding="utf-8") for name in [
        "MASTER_PROGRAM_CHARTER.md","DEVELOPMENT_ROADMAP.md","PHASE_EXECUTION_PLAN.md","PLAN_CHANGELOG.md"
    ]}

    if a.get("amendment_id")!="STRATEGY_KERNEL_PROGRAM_AMENDMENT_A1": errors.append("A1_ID")
    if a.get("status")!="FROZEN_PRE_IMPLEMENTATION": errors.append("A1_STATUS")
    if a["trigger"].get("phase4_v1_forward_observation_count")!=0: errors.append("A1_OBSERVATION_NOT_ZERO")
    if a["trigger"].get("phase4_v1_realized_outcome_read_count")!=0: errors.append("A1_OUTCOME_NOT_ZERO")
    if not a["macro_lifecycle"].get("unchanged"): errors.append("A1_MACRO_CHANGED")
    if a["macro_lifecycle"].get("phase0_through_phase3_reopened"): errors.append("A1_REOPENS_HISTORY")
    if a["macro_lifecycle"].get("phase3_r2_model_reopened"): errors.append("A1_REOPENS_R2")
    if a["macro_lifecycle"].get("phase5_authorized"): errors.append("A1_PHASE5_AUTHORIZED")

    e=a["effective_execution_control"]
    if not e.get("forward_observation_execution_hold"): errors.append("A1_HOLD_MISSING")
    if e.get("effective_forward_observation_start_allowed"): errors.append("A1_EFFECTIVE_START_OPEN")
    if e.get("first_forward_observation_may_be_consumed_before_rebaseline"): errors.append("A1_PRE_REBASE_OBSERVATION_ALLOWED")
    if not e.get("new_clean_baseline_and_future_cutoff_required"): errors.append("A1_REBASE_NOT_REQUIRED")
    if e.get("observed_phase4_results_used_to_design_amendment"): errors.append("A1_OUTCOME_TUNING")

    stages=[x["stage"] for x in a["phase4_internal_sequence"]]
    if stages != ["P4-0","P4-1","P4-2","P4-3","P4-4","P4-5"]: errors.append("A1_SEQUENCE")

    k=a["preserved_strategy_kernel_semantics"]
    if k.get("candidate_model")!="EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2": errors.append("A1_MODEL_DRIFT")
    if k.get("candidate_version")!="R2.0.1_RESEARCH": errors.append("A1_VERSION_DRIFT")
    if k.get("transform_rule_count")!=20: errors.append("A1_TRANSFORM_DRIFT")
    if k.get("fixed_horizons_exchange_sessions")!=[1,3,5]: errors.append("A1_HORIZON_DRIFT")
    if k.get("aggregation_schemes")!=["EQUAL_EDGE","EQUAL_CHECKPOINT","EQUAL_SIGNATURE"]: errors.append("A1_AGG_DRIFT")
    if float(k.get("minimum_concordance_rate"))!=0.5 or float(k.get("minimum_mean_edge_return_spread"))!=0.0: errors.append("A1_THRESHOLD_DRIFT")
    if k.get("model_or_threshold_change_authorized"): errors.append("A1_MODEL_CHANGE_AUTHORIZED")

    p=a["protected_state"]
    for key in ["effective_core_static_changes","candidate_membership_mutations","real_account_mutations","simulation_mutations","target_portfolio_writebacks","user_decisions_generated","orders"]:
        if p.get(key)!=0: errors.append("A1_PROTECTED_NONZERO_"+key)
    if p.get("trade_authority")!="NONE": errors.append("A1_TRADE_AUTHORITY")

    ca=c.get("program_amendment_a1",{})
    if ca.get("status")!="FROZEN_PRE_IMPLEMENTATION" or not ca.get("phase4_forward_execution_hold"): errors.append("A1_CONTRACT_NOT_FROZEN")
    if ca.get("effective_forward_observation_start_allowed"): errors.append("A1_CONTRACT_START_OPEN")
    if ca.get("phase4_internal_sequence")!=stages: errors.append("A1_CONTRACT_SEQUENCE")

    if not s.get("program_amendment_a1_frozen"): errors.append("A1_STATE_NOT_FROZEN")
    baseline_accepted = s.get("phase4_p4_5_clean_baseline_accepted") is True
    if not baseline_accepted:
        if not s.get("phase4_effective_execution_hold"): errors.append("A1_STATE_HOLD_MISSING")
        if s.get("phase4_effective_forward_observation_start_allowed"): errors.append("A1_STATE_EFFECTIVE_START_OPEN")
        if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0: errors.append("A1_STATE_FORWARD_EVIDENCE_NONZERO")
    else:
        if s.get("phase4_effective_execution_hold"): errors.append("A1_STATE_HOLD_NOT_RELEASED_AFTER_BASELINE")
        if s.get("phase4_effective_forward_observation_start_allowed") is not True: errors.append("A1_STATE_START_NOT_OPEN_AFTER_BASELINE")
        if not s.get("phase4_p4_5_effective_cutoff_utc"): errors.append("A1_STATE_CUTOFF_MISSING_AFTER_BASELINE")
    if s.get("orders")!=0 or s.get("trade_authority")!="NONE": errors.append("A1_STATE_AUTHORITY")

    cu=cur.get("program_amendment_a1",{})
    if cu.get("status") not in {"FROZEN_PRE_IMPLEMENTATION","ACTIVE_PRODUCTION_CLOSURE","ACTIVE_FORWARD_VALIDATION"}:
        errors.append("A1_CURRENT_STATUS")
    if not baseline_accepted:
        if not cu.get("phase4_effective_execution_hold"): errors.append("A1_CURRENT_NOT_HELD")
        if cu.get("effective_forward_observation_start_allowed"): errors.append("A1_CURRENT_START_OPEN")
    else:
        if cu.get("phase4_effective_execution_hold"): errors.append("A1_CURRENT_HOLD_NOT_RELEASED")
        if cu.get("effective_forward_observation_start_allowed") is not True: errors.append("A1_CURRENT_START_NOT_OPEN")
    allowed_next = {
        "P4_1_PRODUCTION_BACKBONE_REPAIR",
        "P4_1_MAIN_BASED_OPERATIONAL_REPAIR_IMPLEMENTATION",
        "P4_2_CONTINUOUS_OPPORTUNITY_FUNNEL",
        "P4_2_MAIN_BASED_CONTINUOUS_OPPORTUNITY_FUNNEL_IMPLEMENTATION",
        "P4_3_UNIFIED_DECISION_AND_RECOMMENDATION_ENGINE",
        "P4_3_MAIN_BASED_UNIFIED_RECOMMENDATION_IMPLEMENTATION",
        "P4_4_TRIGGER_MONITOR_AND_AUTONOMOUS_SHADOW_BOOK",
        "P4_4_MAIN_BASED_TRIGGER_SHADOW_IMPLEMENTATION",
        "P4_5_CLEAN_BASELINE_FORWARD_PARALLEL_SHADOW_VALIDATION",
        "P4_5_MAIN_BASED_CLEAN_BASELINE_AND_FORWARD_COLLECTOR_IMPLEMENTATION",
        "P4_5_ACTIVE_FORWARD_ACCUMULATION",
    }
    if cur.get("next_governed_work") not in allowed_next:
        errors.append("A1_NEXT_WORK")

    for token in ["PROGRAM_AMENDMENT_A1","P4-1","P4-5"]:
        for name,body in texts.items():
            if token not in body: errors.append("A1_TEXT_TOKEN_"+name+"_"+token)

    return sorted(set(errors))

if __name__=="__main__":
    errors=validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(f"PROGRAM_AMENDMENT_A1_PASS next={load_json('CURRENT_PHASE_STATUS.json').get('next_governed_work')} observations=0 outcomes=0 orders=0 trade_authority=NONE")
