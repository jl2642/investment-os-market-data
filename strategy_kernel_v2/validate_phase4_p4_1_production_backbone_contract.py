from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def validate():
    e=[]
    c=load("PHASE4_P4_1_PRODUCTION_BACKBONE_CONTRACT.json")
    a=load("PROGRAM_AMENDMENT_A1.json")
    s=load("PROGRAM_STATE.json")
    if c.get("status")!="FROZEN_PRE_IMPLEMENTATION": e.append("P41_NOT_FROZEN")
    if c["parent_amendment"].get("pr")!=338: e.append("P41_PARENT")
    if not c["parent_amendment"].get("phase4_effective_forward_execution_hold"): e.append("P41_FORWARD_HOLD")
    if c["authority_model"]["governance_canonical"].get("branch")!="main": e.append("P41_MAIN_AUTHORITY")
    op=c["authority_model"]["operating_current"]
    if op.get("branch")!="operating-current" or op.get("authoritative_path_prefix")!="operating_current/": e.append("P41_OPERATING_SURFACE")
    if op.get("may_mutate_protected_economic_state"): e.append("P41_OPERATING_MUTATION")
    p=c["publication_semantics"]
    for k in ["successful_validated_run_may_update_operating_current_pointer","source_result_commit_must_exist_before_pointer_update","pointer_must_bind_exact_source_commit","failed_run_may_replace_current_pointer"]:
        if k=="failed_run_may_replace_current_pointer":
            if p.get(k) is not False: e.append("P41_FAIL_REPLACES_CURRENT")
        elif p.get(k) is not True: e.append("P41_PUBLICATION_"+k)
    if p.get("direct_push_to_protected_main") is not False: e.append("P41_DIRECT_MAIN")
    domains={x["domain_id"] for x in c["initial_domains"]}
    expected={"A_SHARE_FULL_MARKET","PORTFOLIO_MARKS","CANDIDATE_WEEKLY_OBSERVATION","RESEARCH_D2","CROSS_MARKET_LIMITED"}
    if domains!=expected: e.append("P41_DOMAINS")
    if c["centralized_observability"].get("index_path")!="operating_current/OPERATING_CURRENT_INDEX.json": e.append("P41_INDEX")
    if not c["implementation_lane"].get("must_be_based_on_protected_main"): e.append("P41_IMPLEMENTATION_BASE")
    if not c["implementation_lane"].get("must_not_merge_strategy_kernel_stacked_chain_into_main"): e.append("P41_STACK_GUARD")
    if a["effective_execution_control"].get("effective_forward_observation_start_allowed"): e.append("P41_A1_START_OPEN")
    if s.get("phase4_forward_observation_count")!=0 or s.get("phase4_realized_outcome_read_count")!=0: e.append("P41_FORWARD_EVIDENCE_NONZERO")
    for k,v in c["protected_state"].items():
        if k=="trade_authority":
            if v!="NONE": e.append("P41_TRADE")
        elif v!=0: e.append("P41_PROTECTED_"+k)
    return sorted(set(e))

if __name__=="__main__":
    err=validate()
    if err: raise AssertionError(";".join(err))
    print("PHASE4_P4_1_PRODUCTION_BACKBONE_CONTRACT_PASS forward_observations=0 orders=0 trade_authority=NONE")
