from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def validate():
    e=[]
    plan=load("PHASE5_READINESS_PREAUTHORIZATION_PLAN.json")
    t1=load("PHASE5_T1_MIGRATION_RULE_TREATMENT_READINESS.json")
    t2=load("PHASE5_T2_LIMITED_ACTIVATION_ROLLBACK_READINESS.json")
    t3=load("PHASE5_T3_FINAL_GOVERNED_ACCEPTANCE_READINESS.json")
    s=load("PROGRAM_STATE.json")

    if plan.get("status")!="PREAUTHORIZATION_READINESS_ONLY": e.append("P5R_PLAN_STATUS")
    if plan.get("phase5_execution_authorized") is not False: e.append("P5R_EXEC_AUTH")
    if plan.get("p4_5_completion_required_before_execution") is not True: e.append("P5R_P45_GATE")
    if [x["transaction_id"] for x in plan.get("transactions",[])]!=["T1","T2","T3"]: e.append("P5R_TX_ORDER")

    for name,obj in [("T1",t1),("T2",t2),("T3",t3)]:
        if obj.get("status")!="FROZEN_PREAUTHORIZATION": e.append(f"P5R_{name}_STATUS")
        if obj.get("execution_authorized") is not False: e.append(f"P5R_{name}_EXEC_AUTH")

    rows=t1.get("rule_treatment_matrix",[])
    responsibilities={x.get("responsibility") for x in rows}
    required={
        "FULL_MARKET_AND_CANDIDATE_DISCOVERY_ROUTING",
        "RESEARCH_EVIDENCE_PRODUCTION",
        "OPPORTUNITY_AND_POSITION_RECOMMENDATION_STATE",
        "PORTFOLIO_SIZING_AND_POSITION_LEVEL_CONTEXT",
        "TRIGGER_AND_INVALIDATION_MONITORING",
        "COUNTERFACTUAL_SHADOW_ACTION_RECORD",
        "PROTECTED_SIMULATION_ECONOMIC_STATE",
        "REAL_ACCOUNT_ECONOMIC_STATE",
        "FORMAL_CANDIDATE_MEMBERSHIP",
        "EXISTING_USER_APPROVED_OR_USER_SPECIFIC_DECISIONS",
    }
    if responsibilities!=required: e.append("P5R_T1_MATRIX")
    keep={x["responsibility"]:x["treatment"] for x in rows}
    if keep.get("REAL_ACCOUNT_ECONOMIC_STATE")!="KEEP_AUTHORITY": e.append("P5R_REAL")
    if keep.get("FORMAL_CANDIDATE_MEMBERSHIP")!="KEEP_AUTHORITY": e.append("P5R_CAND")
    if keep.get("PROTECTED_SIMULATION_ECONOMIC_STATE")!="KEEP_AUTHORITY": e.append("P5R_SIM")
    if keep.get("PORTFOLIO_SIZING_AND_POSITION_LEVEL_CONTEXT")!="SUPPORT_ONLY": e.append("P5R_SIZING")
    if keep.get("OPPORTUNITY_AND_POSITION_RECOMMENDATION_STATE")!="MIGRATE_PRIMARY_AUTHORITY": e.append("P5R_REC")

    scope=t2.get("activation_scope",{})
    if scope.get("orders")!=0 or scope.get("trade_authority")!="NONE": e.append("P5R_T2_TRADE")
    if t2.get("live_limited_activation",{}).get("additional_calendar_wait_required") is not False:
        e.append("P5R_T2_EXTRA_WAIT")
    if t2.get("acceptance_gate",{}).get("separate_waiting_period_after_success_required") is not False:
        e.append("P5R_T2_WAIT_GATE")

    final=t3.get("final_authority_map",{})
    if final.get("recommendation_state")!="P4_3_RECOMMENDATION_PRIMARY": e.append("P5R_T3_REC")
    if final.get("formal_candidate_membership")!="USER_GOVERNED_MAIN_KEEP": e.append("P5R_T3_CAND")
    if final.get("real_account_state")!="PROTECTED_MAIN_REAL_ACCOUNT_KEEP": e.append("P5R_T3_REAL")
    if final.get("protected_simulation_state")!="PROTECTED_MAIN_SIMULATION_KEEP": e.append("P5R_T3_SIM")
    if t3.get("controls",{}).get("automatic_orders")!=0 or t3.get("controls",{}).get("trade_authority")!="NONE":
        e.append("P5R_T3_TRADE")

    if s.get("phase5_readiness_status")!="PREPARED_NOT_AUTHORIZED": e.append("P5R_STATE")
    for k in ["phase5_readiness_plan_frozen","phase5_t1_readiness_frozen","phase5_t2_readiness_frozen","phase5_t3_readiness_frozen"]:
        if s.get(k) is not True: e.append("P5R_STATE_"+k)
    if s.get("phase5_execution_authorized") is not False: e.append("P5R_STATE_EXEC")
    if s.get("phase5_migration_allowed") is not False: e.append("P5R_STATE_MIGRATION")
    if s.get("phase4_p4_5_complete") is not False: e.append("P5R_P45_PREMATURE")
    if s.get("phase4_p4_5_status")!="ACTIVE_FORWARD_ACCUMULATION": e.append("P5R_P45_STATUS")
    return sorted(set(e))

if __name__=="__main__":
    err=validate()
    if err: raise AssertionError(";".join(err))
    print("PHASE5_READINESS_PREAUTHORIZATION_PASS T1=T2=T3_PREPARED execution_authorized=false phase5=false orders=0 trade_authority=NONE")
