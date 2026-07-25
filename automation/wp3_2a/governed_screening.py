from __future__ import annotations
import argparse, csv, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",required=True); ap.add_argument("--config",required=True); ap.add_argument("--max-proposals",type=int,default=100); ap.add_argument("--confirmation",required=True); ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    if a.confirmation!="RUN_PROPOSAL_ONLY_SCREENING": raise SystemExit("confirmation mismatch")
    repo=Path(a.repo_root); config=json.loads(Path(a.config).read_text(encoding="utf-8")); current=repo/config["current_root"]
    manifest=json.loads((current/"PROPOSAL_MANIFEST.json").read_text(encoding="utf-8")); lineage=json.loads((current/"LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
    binding=json.loads((repo/"investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json").read_text(encoding="utf-8"))
    if lineage.get("status")!="PASS": raise SystemExit("accepted Current lineage not PASS")
    if binding.get("as_of_date") != manifest.get("session"): raise SystemExit("Current binding session mismatch")
    if binding.get("status") != "ACCEPTED_IF_AND_ONLY_IF_MERGED_TO_MAIN": raise SystemExit("Current binding is not human-merge accepted")
    with (current/"A_SHARE_FULL_UNIVERSE.csv").open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    triage=[]
    for r in rows:
        price=num(r.get("last_price")); volume=num(r.get("volume")); turnover=num(r.get("turnover_amount")); mcap=num(r.get("total_market_cap"))
        completeness=sum(x is not None for x in [price,volume,turnover,mcap])
        if price is None or volume is None or volume<=0: status="NOT_READY_MARKET_DATA"
        elif completeness<3: status="REVIEW_DATA_GAPS"
        else: status="ELIGIBLE_FOR_RESEARCH_TRIAGE"
        triage.append({
            "security_code":r.get("security_code"),"security_name":r.get("security_name"),"exchange":r.get("exchange"),
            "market_data_readiness":status,"field_completeness_count":completeness,
            "turnover_amount":turnover,"total_market_cap":mcap,
            "investment_quality_status":"NOT_EVALUATED","valuation_status":"NOT_EVALUATED",
            "thesis_status":"NOT_CREATED","entry_baseline_status":"MISSING",
            "candidate_admission_authority":False,"research_priority_basis":"DATA_READINESS_AND_LIQUIDITY_ONLY_NOT_INVESTMENT_RANK"
        })
    eligible=[r for r in triage if r["market_data_readiness"]=="ELIGIBLE_FOR_RESEARCH_TRIAGE"]
    eligible.sort(key=lambda r:((r["turnover_amount"] or -1),(r["total_market_cap"] or -1)),reverse=True)
    selected=eligible[:max(0,a.max_proposals)]
    proposal_id=f"WP3_2A_SCREENING_PROPOSAL_{manifest['session'].replace('-','')}_{a.run_id}"
    out=repo/config["screening_root"]/proposal_id; out.mkdir(parents=True,exist_ok=False)
    fields=list(triage[0].keys()) if triage else []
    with (out/"FULL_MARKET_RESEARCH_READINESS.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(triage)
    with (out/"RESEARCH_WORKLOAD_QUEUE.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(selected)
    result={
        "proposal_id":proposal_id,"status":"PROPOSAL_ONLY_PENDING_HUMAN_REVIEW","session":manifest["session"],
        "universe_rows":len(rows),"eligible_research_triage":len(eligible),"workload_queue_rows":len(selected),
        "method":"DATA_READINESS_AND_LIQUIDITY_ONLY","investment_ranking":False,"quality_score":False,
        "valuation_conclusion":False,"research_objects_created":0,"candidate_membership_mutations":0,
        "simulation_trade_mutations":0,"real_account_mutations":0,"orders":0,"trade_authority":"NONE"
    }
    (out/"SCREENING_PROPOSAL_MANIFEST.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"README.md").write_text(
        f"# {proposal_id}\n\n本输出仅用于研究工作量排序，不是投资吸引力排名，不创建Research Object，不改变Candidate。\n\n"
        f"- Universe: {len(rows)}\n- Research-ready data rows: {len(eligible)}\n- Queue: {len(selected)}\n",
        encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
