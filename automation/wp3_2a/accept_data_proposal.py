from __future__ import annotations
import argparse, hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

INVESTMENT_OBJECTS = {
    "real_account": "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json",
    "simulation": "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json",
    "research": "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_OBJECTS_CURRENT.json",
    "thesis": "investment_os_runtime/30_STATE_CURRENT/31_RESEARCH/THESIS_CURRENT.json",
    "candidate": "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",
}

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",required=True)
    ap.add_argument("--proposal-path",required=True)
    ap.add_argument("--confirmation",required=True)
    ap.add_argument("--config",required=True)
    a=ap.parse_args()
    if a.confirmation != "ACCEPT_UNIVERSE_PROPOSAL":
        raise SystemExit("confirmation mismatch")
    repo=Path(a.repo_root); proposal=(repo/a.proposal_path).resolve()
    if repo.resolve() not in proposal.parents: raise SystemExit("proposal outside repository")
    config=json.loads(Path(a.config).read_text(encoding="utf-8"))
    manifest=json.loads((proposal/"PROPOSAL_MANIFEST.json").read_text(encoding="utf-8"))
    lineage=json.loads((proposal/"LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if lineage.get("status")!="PASS": raise SystemExit("proposal lineage not PASS")
    data=proposal/"A_SHARE_FULL_UNIVERSE.csv"
    if sha(data)!=manifest["data_sha256"]: raise SystemExit("proposal data hash mismatch")
    before={k:sha(repo/v) for k,v in INVESTMENT_OBJECTS.items()}
    current=repo/config["current_root"]
    if current.exists(): shutil.rmtree(current)
    current.mkdir(parents=True)
    for name in ["A_SHARE_FULL_UNIVERSE.csv","ACQUISITION_MANIFEST.json","LINEAGE_ACCEPTANCE.json","PROPOSAL_MANIFEST.json","ZERO_INVESTMENT_MUTATION_PROOF.json"]:
        shutil.copy2(proposal/name,current/name)
    if (proposal/"RAW").exists(): shutil.copytree(proposal/"RAW",current/"RAW")
    acquisition=json.loads((current/"ACQUISITION_MANIFEST.json").read_text(encoding="utf-8"))
    binding_path=repo/"investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    binding=json.loads(binding_path.read_text(encoding="utf-8"))
    binding.update({
        "binding_id":"MARKET_BINDING_A_SHARE_WP3_2A_ACCEPTANCE_CANDIDATE",
        "status":"ACCEPTED_IF_AND_ONLY_IF_MERGED_TO_MAIN",
        "as_of_date":manifest["session"],
        "generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_provider":manifest["provider"],
        "authority":"DATA_EVIDENCE_RESEARCH_PRIORITY_ONLY",
        "live_action_scope":"BLOCKED_PENDING_HUMAN_MERGE_AND_SEPARATE_RESEARCH_REVIEW",
        "trade_authority":"NONE",
    })
    binding.setdefault("datasets",{})["universe"]={
        "path":str((current/"A_SHARE_FULL_UNIVERSE.csv").relative_to(repo)),
        "rows":manifest["rows"],"sha256":sha(current/"A_SHARE_FULL_UNIVERSE.csv"),
        "maximum_age_calendar_days":7,"stale_behavior":"LABEL_AND_RESTRICT"
    }
    binding["datasets"]["daily_market_snapshot"]={
        "path":str((current/"A_SHARE_FULL_UNIVERSE.csv").relative_to(repo)),
        "rows":manifest["rows"],"sha256":sha(current/"A_SHARE_FULL_UNIVERSE.csv"),
        "maximum_age_calendar_days":3,"requires_latest_completed_session":True,
        "stale_behavior":"BLOCK"
    }
    binding["wp3_2a_lineage"]={
        "proposal_id":manifest["proposal_id"],"lineage_status":"PASS",
        "lineage_path":str((current/"LINEAGE_ACCEPTANCE.json").relative_to(repo)),
        "provider_change_reviewed_by_merge":True,
        "automatic_candidate_admission":False,"orders":0,
    }
    binding_path.write_text(json.dumps(binding,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    record=repo/"investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_ACCEPTANCE_RECORD.json"
    record.write_text(json.dumps({
        "record_id":"WP3_2A_UNIVERSE_ACCEPTANCE_"+manifest["session"].replace("-",""),
        "status":"ACCEPTED_IF_AND_ONLY_IF_MERGED_TO_MAIN","proposal_id":manifest["proposal_id"],
        "session":manifest["session"],"provider":manifest["provider"],"rows":manifest["rows"],
        "data_sha256":sha(current/"A_SHARE_FULL_UNIVERSE.csv"),
        "candidate_membership_mutations":0,"research_object_mutations":0,
        "simulation_trade_mutations":0,"real_account_mutations":0,"orders":0,
        "trade_authority":"NONE"
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    execution_path=repo/"investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    execution=json.loads(execution_path.read_text(encoding="utf-8"))
    execution.update({
        "register_id":"INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V3_2A_UNIVERSE_ACCEPTED_ON_MAIN_MERGE",
        "overall_status":"WP3_IN_PROGRESS_UNIVERSE_ACCEPTED_ON_MAIN_MERGE",
        "current_step":"WP3-2A_ACCEPTANCE_PR_PENDING_HUMAN_MERGE",
        "trade_authority":"NONE",
    })
    execution["wp3_status"]={
        "WP3-1":"COMPLETED_STRATEGY_AND_REBUILD_PREPARATION",
        "WP3-2":"COMPLETED_IF_ACCEPTANCE_PR_MERGED_TO_MAIN",
        "WP3-2A":"DATA_ACCEPTED_IF_PR_MERGED_TO_MAIN",
        "WP3-3":"READY_IF_ACCEPTANCE_PR_MERGED_TO_MAIN",
        "WP3-4":"PLANNED",
    }
    execution["next_task"]="MERGE_ACCEPTANCE_PR_THEN_RUN_PROPOSAL_ONLY_SCREENING"
    execution_path.write_text(json.dumps(execution,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    after={k:sha(repo/v) for k,v in INVESTMENT_OBJECTS.items()}
    changed=[k for k in before if before[k]!=after[k]]
    if changed: raise RuntimeError(f"investment objects changed: {changed}")
    print(json.dumps({"session":manifest["session"],"proposal_id":manifest["proposal_id"],"changed_investment_objects":changed},ensure_ascii=False))

if __name__=="__main__": main()
