#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTROL = Path("investment_os_runtime/00_CONTROL")
SCHEMAS = Path("investment_os_runtime/20_SCHEMAS_AND_INTERFACES")
REQUIRED_NEW = [
 "CORE_STATIC_CONSTITUTION_CURRENT.md","CORE_RULE_CATALOG_CURRENT.json","CANONICAL_IO_CONTRACT_CURRENT.json",
 "MARKET_DATA_EOD_CONTRACT_CURRENT.json","PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json","PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json",
 "REPORTING_MANIFEST_CONTRACT_CURRENT.json","RESEARCH_FUNNEL_CONTRACT_CURRENT.json","OBSERVABILITY_CONTRACT_CURRENT.json",
 "P0_ACCEPTANCE_REGISTER_CURRENT.json","R6_P0_ACCEPTANCE_CHECKLIST_CURRENT.md"]
REQUIRED_EXISTING = [
 "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json",
 "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json",
 "investment_os_runtime/00_CONTROL/R5_ATTRIBUTION_CONTRACT_CURRENT.json",
 "investment_os_runtime/00_CONTROL/R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json",
 "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/R6_OBSERVATION_LEDGER_CURRENT.json",
 "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
 "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
 "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"]

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def stable_id(prefix: str, payload: dict[str, Any]) -> str:
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"

def validate(repo: Path) -> dict[str, Any]:
    errors:list[Any]=[]; blockers:list[Any]=[]; facts:dict[str,Any]={}
    for name in REQUIRED_NEW:
        if not (repo/CONTROL/name).exists(): errors.append(f"MISSING_P0_ASSET:{name}")
    for rel in REQUIRED_EXISTING:
        if not (repo/rel).exists(): errors.append(f"MISSING_CANONICAL_ASSET:{rel}")
    for name in ["CORE_RULE_CATALOG_CURRENT.json","CANONICAL_IO_CONTRACT_CURRENT.json","MARKET_DATA_EOD_CONTRACT_CURRENT.json","PORTFOLIO_SNAPSHOT_CONTRACT_CURRENT.json","PERFORMANCE_ATTRIBUTION_CONTRACT_CURRENT.json","REPORTING_MANIFEST_CONTRACT_CURRENT.json","RESEARCH_FUNNEL_CONTRACT_CURRENT.json","OBSERVABILITY_CONTRACT_CURRENT.json","P0_ACCEPTANCE_REGISTER_CURRENT.json"]:
        p=repo/CONTROL/name
        if p.exists():
            try:
                d=load(p)
                if d.get("trade_authority") != "NONE": errors.append(f"TRADE_AUTHORITY_VIOLATION:{name}")
            except Exception as exc: errors.append(f"INVALID_JSON:{name}:{exc}")
    for name in ["canonical_run_manifest.schema.json","report_manifest.schema.json","p0_acceptance_register.schema.json"]:
        p=repo/SCHEMAS/name
        if not p.exists(): errors.append(f"MISSING_SCHEMA:{name}")
        else:
            try:
                if load(p).get("$schema")!="https://json-schema.org/draft/2020-12/schema": errors.append(f"SCHEMA_DIALECT:{name}")
            except Exception as exc: errors.append(f"INVALID_SCHEMA:{name}:{exc}")
    if errors:
        return {"status":"FAIL","errors":errors,"blockers":blockers,"facts":facts,"trade_authority":"NONE"}
    execution=load(repo/REQUIRED_EXISTING[0]); r4=load(repo/REQUIRED_EXISTING[1]); r5=load(repo/REQUIRED_EXISTING[2]); r6=load(repo/REQUIRED_EXISTING[3]); ledger=load(repo/REQUIRED_EXISTING[4]); real=load(repo/REQUIRED_EXISTING[5]); sim=load(repo/REQUIRED_EXISTING[6]); cand=load(repo/REQUIRED_EXISTING[7])
    for label,d in [("execution",execution),("r4",r4),("r5",r5),("r6",r6),("ledger",ledger),("real",real),("simulation",sim),("candidate",cand)]:
        if d.get("trade_authority")!="NONE": errors.append(f"CANONICAL_TRADE_AUTHORITY_VIOLATION:{label}")
    counts={"real":len(real.get("holdings",[])),"simulation":len(sim.get("holdings",[])),"candidate_core":cand.get("counts",{}).get("candidate_core"),"research_queue":cand.get("counts",{}).get("research_queue"),"shadow_track":cand.get("counts",{}).get("shadow_track"),"ready":cand.get("counts",{}).get("ready_for_user_decision")}
    facts.update(counts)
    if counts["real"]!=7: errors.append(f"REAL_HOLDING_COUNT:{counts['real']}")
    if counts["simulation"]!=16: errors.append(f"SIM_HOLDING_COUNT:{counts['simulation']}")
    if (counts["candidate_core"],counts["research_queue"],counts["shadow_track"],counts["ready"])!=(2,33,38,0): errors.append(f"CANDIDATE_COUNTS:{counts}")
    facts["r6_checkpoint"]=f"{ledger.get('checkpoint_passed')}/{ledger.get('checkpoint_total')}"
    if ledger.get("checkpoint_passed",0) < ledger.get("checkpoint_total",0): blockers.append("R6_CHECKPOINTS_INCOMPLETE")
    if not r6.get("production_completion_definition",{}).get("full_month_complete"): blockers.append("R6_FULL_MONTH_NOT_COMPLETE")
    if r4.get("development_mode") is True: blockers.append("OPERATING_PRODUCTS_NOT_LIVE")
    if any("BLOCKED" in str(layer.get("status")) or "PARTIAL" in str(layer.get("status")) for layer in r5.get("layers",[])): blockers.append("EXACT_PERIOD_ATTRIBUTION_INPUTS_INCOMPLETE")
    md=load(repo/CONTROL/"MARKET_DATA_EOD_CONTRACT_CURRENT.json")
    blockers.extend(md.get("current_blockers",[]))
    status="FAIL" if errors else ("PASS_WITH_BLOCKERS" if blockers else "PASS")
    return {"status":status,"errors":errors,"blockers":sorted(set(blockers)),"facts":facts,"trade_authority":"NONE"}

def build_run(args: argparse.Namespace) -> dict[str,Any]:
    payload={"workflow_name":args.workflow_name,"trigger_type":args.trigger_type,"started_at":args.started_at,"completed_at":args.completed_at,"canonical_commit_before":args.commit_before,"canonical_commit_after":args.commit_after,"market_data_watermark":args.market_watermark,"position_watermark":args.position_watermark,"inputs":sorted(args.input),"outputs":sorted(args.output_asset),"exceptions":args.exception,"idempotency_key":args.idempotency_key,"status":args.status,"trade_authority":"NONE"}
    payload["run_id"]=stable_id("RUN",payload); return payload

def build_report(args: argparse.Namespace) -> dict[str,Any]:
    status="FORMAL" if not args.exception and args.completeness==1 else ("BLOCKED" if args.completeness<0.5 else "PROVISIONAL")
    payload={"report_type":args.report_type,"period_start":args.period_start,"period_end":args.period_end,"generated_at":args.generated_at,"canonical_commit_sha":args.commit,"market_data_watermark":args.market_watermark,"position_watermark":args.position_watermark,"candidate_watermark":args.candidate_watermark,"input_assets":sorted(args.input),"exceptions":args.exception,"publication_status":status,"trade_authority":"NONE"}
    payload["report_id"]=stable_id(args.report_type,payload); return payload

def write_or_print(payload:dict[str,Any], path:str|None) -> None:
    text=json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if path:
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding="utf-8")
    print(text,end="")

def main() -> int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    v=sub.add_parser("validate"); v.add_argument("--repo-root",default="."); v.add_argument("--output")
    r=sub.add_parser("build-run-manifest")
    for n in ["workflow-name","trigger-type","started-at","completed-at","commit-before","commit-after","idempotency-key","status"]: r.add_argument("--"+n,required=True)
    r.add_argument("--market-watermark"); r.add_argument("--position-watermark"); r.add_argument("--input",action="append",default=[]); r.add_argument("--output-asset",action="append",default=[]); r.add_argument("--exception",action="append",default=[]); r.add_argument("--output")
    q=sub.add_parser("build-report-manifest"); q.add_argument("--report-type",choices=["STATUS","DAILY","WEEKLY","MONTHLY","QUARTERLY","ANNUAL","EVENT"],required=True); q.add_argument("--period-start",required=True); q.add_argument("--period-end",required=True); q.add_argument("--generated-at",default=datetime.now(timezone.utc).isoformat()); q.add_argument("--commit",required=True); q.add_argument("--market-watermark"); q.add_argument("--position-watermark"); q.add_argument("--candidate-watermark"); q.add_argument("--completeness",type=float,required=True); q.add_argument("--input",action="append",default=[]); q.add_argument("--exception",action="append",default=[]); q.add_argument("--output")
    args=ap.parse_args()
    if args.cmd=="validate":
        out=validate(Path(args.repo_root)); write_or_print(out,args.output); return 1 if out["status"]=="FAIL" else 0
    if args.cmd=="build-run-manifest": write_or_print(build_run(args),args.output); return 0
    write_or_print(build_report(args),args.output); return 0
if __name__=="__main__": raise SystemExit(main())
