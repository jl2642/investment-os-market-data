from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

WORKFLOWS={
    "A_SHARE_FULL_MARKET":[
        ".github/workflows/fmdl-daily-production.yml",
        ".github/workflows/fmdl-2b4-full-rebase.yml",
    ],
    "PORTFOLIO_MARKS":[".github/workflows/wp2_r_market_marks_refresh.yml"],
    "CANDIDATE_WEEKLY_OBSERVATION":[".github/workflows/wp3_r_weekly_screen.yml"],
    "RESEARCH_D2":[".github/workflows/research-queue-d2-auto-consumer.yml"],
    "CROSS_MARKET_LIMITED":[".github/workflows/round3-cross-market-limited-production.yml"],
}

def validate():
    errors=[]
    contract=json.loads((ROOT/"investment_os_runtime/00_CONTROL/P4_1_OPERATING_CURRENT_CONTRACT.json").read_text(encoding="utf-8"))
    if contract.get("status")!="IMPLEMENTATION_CANDIDATE": errors.append("CONTRACT_STATUS")
    if contract["authority"]["governance_canonical"].get("branch")!="main": errors.append("MAIN_AUTHORITY")
    op=contract["authority"]["operating_current"]
    if op.get("branch")!="operating-current" or op.get("authoritative_prefix")!="operating_current/": errors.append("OPERATING_AUTHORITY")
    if op.get("may_mutate_protected_economic_state"): errors.append("OPERATING_MUTATION")
    if contract["pointer_rules"].get("failed_blocked_or_stale_run_may_replace_current"): errors.append("FAIL_REPLACE")
    if not contract["pointer_rules"].get("source_commit_must_be_remote_reachable_before_advance"): errors.append("SOURCE_GUARD")
    if contract["permanent_boundaries"].get("orders")!=0 or contract["permanent_boundaries"].get("trade_authority")!="NONE": errors.append("AUTHORITY")
    pub=(ROOT/"automation/operating_current/publish_operating_current.py").read_text(encoding="utf-8")
    for token in ["WATERMARK_REGRESSION","SOURCE_COMMIT_NOT_BRANCH_HEAD","ONLY_PASS_MAY_ADVANCE_CURRENT","operating-current"]:
        if token not in pub: errors.append("PUBLISHER_MISSING_"+token)
    for domain,paths in WORKFLOWS.items():
        for path in paths:
            body=(ROOT/path).read_text(encoding="utf-8")
            if "publish_operating_current.py" not in body: errors.append("WORKFLOW_NOT_INTEGRATED_"+path)
            if domain not in body: errors.append("WORKFLOW_DOMAIN_MISSING_"+path)
    return sorted(set(errors))

if __name__=="__main__":
    e=validate()
    if e: raise AssertionError(";".join(e))
    print("P4_1_OPERATING_CURRENT_IMPLEMENTATION_PASS orders=0 trade_authority=NONE")
