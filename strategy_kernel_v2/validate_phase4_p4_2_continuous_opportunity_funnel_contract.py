from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def validate():
    e=[]
    c=load("PHASE4_P4_2_CONTINUOUS_OPPORTUNITY_FUNNEL_CONTRACT.json")
    s=load("PROGRAM_STATE.json")
    a=load("PROGRAM_AMENDMENT_A1.json")
    if c.get("status")!="FROZEN_PRE_IMPLEMENTATION": e.append("P42_NOT_FROZEN")
    if c["parent"].get("p4_1_status")!="COMPLETE_ACCEPTED": e.append("P42_P41_NOT_COMPLETE")
    if not c["parent"].get("phase4_effective_forward_execution_hold"): e.append("P42_FORWARD_HOLD")
    if not c["existing_capability_reuse"].get("rebuild_existing_components_not_authorized"): e.append("P42_REBUILD_SCOPE")
    if c["unified_operating_surface"].get("branch")!="operating-current": e.append("P42_OPERATING_BRANCH")
    if c["unified_operating_surface"].get("protected_economic_authority"): e.append("P42_ECONOMIC_AUTHORITY")
    if c["watermark_semantics"].get("synthetic_single_as_of_date_forbidden") is not True: e.append("P42_SYNTHETIC_DATE")
    if c["throughput_semantics"].get("zero_throughput_allowed") is not True: e.append("P42_ZERO_FLOW")
    if c["throughput_semantics"].get("standards_may_not_be_relaxed_to_manufacture_flow") is not True: e.append("P42_RELAX_STANDARD")
    if c["bounded_rotation"].get("preserve_existing_d1_batch_capacity")!=5: e.append("P42_D1_CAPACITY")
    if c["bounded_rotation"].get("preserve_existing_d2_batch_capacity")!=3: e.append("P42_D2_CAPACITY")
    if c["bounded_rotation"].get("p4_2_may_change_research_priority_scoring"): e.append("P42_SCORING_CHANGE")
    if c["acceptance_gate"].get("minimum_distinct_cycle_fingerprints")!=2: e.append("P42_REPEAT_GATE")
    if c["near_miss_ledger"].get("global_scalar_near_miss_score_forbidden") is not True: e.append("P42_NEARMISS_SCORE")
    if a["effective_execution_control"].get("effective_forward_observation_start_allowed"): e.append("P42_A1_HOLD_OPEN")
    if s.get("phase4_p4_1_complete") is not True: e.append("P42_STATE_P41")
    if s.get("phase4_reconciliation_current_stage")!="P4_2_CONTINUOUS_OPPORTUNITY_FUNNEL": e.append("P42_STATE_STAGE")
    if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0: e.append("P42_FORWARD_EVIDENCE")
    for k,v in c["protected_state"].items():
        if k=="trade_authority":
            if v!="NONE": e.append("P42_TRADE")
        elif v!=0: e.append("P42_PROTECTED_"+k)
    return sorted(set(e))

if __name__=="__main__":
    err=validate()
    if err: raise AssertionError(";".join(err))
    print("PHASE4_P4_2_CONTINUOUS_OPPORTUNITY_FUNNEL_CONTRACT_PASS forward_observations=0 orders=0 trade_authority=NONE")
