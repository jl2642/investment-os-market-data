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
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gate-result", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-id", required=True)
    a=ap.parse_args()
    repo=Path(a.repo_root); run=Path(a.run_dir)
    config=json.loads(Path(a.config).read_text(encoding="utf-8"))
    acquisition=json.loads((run/"ACQUISITION_MANIFEST.json").read_text(encoding="utf-8"))
    gate=json.loads(Path(a.gate_result).read_text(encoding="utf-8"))
    if acquisition.get("run_status") != "PASS": raise SystemExit("acquisition not PASS")
    if gate.get("status") != "PASS": raise SystemExit("Gate v3 not PASS")
    session=acquisition["session"]
    proposal_id=f"WP3_2A_UNIVERSE_PROPOSAL_{session.replace('-','')}_{a.run_id}"
    proposal=repo/config["proposal_root"]/proposal_id
    proposal.mkdir(parents=True, exist_ok=False)
    before={k:sha(repo/v) for k,v in INVESTMENT_OBJECTS.items()}
    shutil.copy2(run/"A_SHARE_FULL_UNIVERSE_CURRENT.csv", proposal/"A_SHARE_FULL_UNIVERSE.csv")
    shutil.copy2(run/"ACQUISITION_MANIFEST.json", proposal/"ACQUISITION_MANIFEST.json")
    shutil.copy2(Path(a.gate_result), proposal/"LINEAGE_ACCEPTANCE.json")
    if (run/"raw").exists(): shutil.copytree(run/"raw", proposal/"RAW")
    after={k:sha(repo/v) for k,v in INVESTMENT_OBJECTS.items()}
    changed=[k for k in before if before[k]!=after[k]]
    if changed: raise RuntimeError(f"investment objects changed: {changed}")
    data=proposal/"A_SHARE_FULL_UNIVERSE.csv"
    manifest={
        "proposal_id":proposal_id,"status":"ACCEPTANCE_CANDIDATE_PENDING_HUMAN_REVIEW",
        "session":session,"provider":acquisition["selected_provider"],
        "rows":acquisition["rows"],"data_sha256":sha(data),
        "acquisition_sha256":sha(proposal/"ACQUISITION_MANIFEST.json"),
        "lineage_sha256":sha(proposal/"LINEAGE_ACCEPTANCE.json"),
        "provider_changed_from_previous":acquisition.get("provider_changed_from_previous",False),
        "human_review_required":True,"automatic_current_promotion":False,
        "candidate_membership_mutations":0,"research_object_mutations":0,
        "simulation_trade_mutations":0,"real_account_mutations":0,"orders":0,
        "investment_object_hashes_before":before,"investment_object_hashes_after":after,
        "trade_authority":"NONE",
    }
    (proposal/"PROPOSAL_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (proposal/"ZERO_INVESTMENT_MUTATION_PROOF.json").write_text(json.dumps({
        "proof_id":proposal_id+"_ZERO_MUTATION","changed_objects":changed,
        "before":before,"after":after,"orders":0,"trade_authority":"NONE"
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (proposal/"README.md").write_text(
        f"# {proposal_id}\n\n- Session: `{session}`\n- Provider: `{acquisition['selected_provider']}`\n"
        f"- Rows: `{acquisition['rows']}`\n- Gate v3: `PASS`\n- Status: `PENDING_HUMAN_REVIEW`\n\n"
        "合并本提案不会自动覆盖Current；须再运行人工确认的接受工作流。\n",
        encoding="utf-8")
    pointer=repo/"investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/PROPOSAL_POINTER_CURRENT.json"
    pointer.parent.mkdir(parents=True,exist_ok=True)
    pointer.write_text(json.dumps({
        "proposal_id":proposal_id,"proposal_path":str(proposal.relative_to(repo)),
        "session":session,"status":"PENDING_HUMAN_REVIEW","trade_authority":"NONE"
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"proposal_id":proposal_id,"proposal_path":str(proposal.relative_to(repo)),"session":session},ensure_ascii=False))

if __name__=="__main__": main()
