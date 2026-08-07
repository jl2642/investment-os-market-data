#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
import pandas as pd

TRADE_AUTHORITY="NONE"
DIMS={"GOVERNANCE_VALUE_TRAP","EARNINGS_EXPECTATION_REVISION","CATALYST"}

def rj(p): return json.loads(p.read_text(encoding="utf-8"))
def wj(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def bv(x): return str(x).lower() in {"true","1"}
def direction(title,summary):
    t=f"{title} {summary}".lower()
    if any(x in t for x in ("profit warning","expected loss","profit to fall","profit decrease","deterioration")): return "NEGATIVE"
    if any(x in t for x in ("positive profit","profit increase","estimated profit increase","profit to rise","record profit")): return "POSITIVE"
    return "NEUTRAL_OR_UNKNOWN"

def d2_rule(root):
    p=root/"pipeline/hkcu_p2b_e2_synthesize_top20_partial.py"
    s=importlib.util.spec_from_file_location("d2rules",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m.synthesize

def rebuild_d1(root,out):
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,str(root/"pipeline/hkcu_p2b_e2_deepen_negative_catalyst.py"),"--repo-root",str(root),"--output",str(out)],check=True)
    subprocess.run([sys.executable,str(root/"scripts/validate_hkcu_p2b_e2_deepening_d1.py"),"--output",str(out)],check=True)

def normalize_partial(row,s):
    text=f"{row.evidence_title} {row.evidence_summary}".lower()
    x=dict(final_dimension_state=str(s["evidence_sufficiency"]),final_direction=str(s["finding_direction"]),
           final_materiality=str(s["materiality"]),final_blocker=bool(s["graduation_blocker"]),final_finding=str(s["finding"]),
           next_required_evidence=str(s["counterevidence_needed"]),monitor_trigger=str(s["monitor_trigger"]),decision_lineage="GENERIC_D2_PARTIAL_SYNTHESIS")
    if row.research_dimension=="GOVERNANCE_VALUE_TRAP" and any(k in text for k in ("administrative supervisory","supervisory measures","regulatory action","violation","non-compliance")):
        x.update(final_dimension_state="TARGETED_DEEPENING_REQUIRED",final_direction="NEGATIVE",final_materiality="HIGH",final_blocker=True,
                 final_finding="REGULATORY_OR_COMPLIANCE_EVENT_REVIEW_REQUIRED",next_required_evidence="Remediation completion, recurrence risk, operating impact and current regulator status.",
                 monitor_trigger="Further regulatory action, delayed remediation, client-acquisition restriction or operating impact.",decision_lineage="GENERIC_REGULATORY_BLOCKER_GUARD")
    if x["final_finding"]=="STALE_OR_ANNUAL_ONLY_OPERATING_EVIDENCE_NO_DIRECT_REVISION_SERIES":
        x.update(final_dimension_state="CONFIDENCE_CAP_MONITOR",final_direction="UNKNOWN",final_materiality="MEDIUM",final_blocker=False,
                 next_required_evidence="Current-period results/guidance or reliable dated consensus revisions.",monitor_trigger="Next current-period results/guidance or consensus-revision update.",decision_lineage="GENERIC_INFORMATION_LIMIT_CONFIDENCE_CAP")
    if x["final_finding"] in {"AUDITOR_CHANGE_OR_AUDIT_GOVERNANCE_EVENT","SENIOR_LEADERSHIP_TRANSITION"}:
        x.update(final_dimension_state="CONFIDENCE_CAP_MONITOR",final_blocker=False,decision_lineage="GENERIC_GOVERNANCE_PROCESS_CONFIDENCE_CAP")
    if x["final_finding"]=="RELATED_PARTY_OR_CONNECTED_TRANSACTION_REVIEW_REQUIRED":
        if "exceeded" in text or "breach" in text: x.update(final_dimension_state="TARGETED_DEEPENING_REQUIRED",final_blocker=True,decision_lineage="GENERIC_CONNECTED_TRANSACTION_BREACH_GUARD")
        else: x.update(final_dimension_state="CONFIDENCE_CAP_MONITOR",final_blocker=False,decision_lineage="GENERIC_CONNECTED_TRANSACTION_CONFIDENCE_CAP")
    if x["final_finding"] in {"ACTIVE_SPINOFF_OR_LISTING_EVENT","ACTIVE_STRATEGIC_TRANSACTION"}:
        x.update(final_dimension_state="CONFIDENCE_CAP_MONITOR",final_blocker=False,decision_lineage="GENERIC_OPTIONALITY_CONFIDENCE_CAP")
    return x

def build(root,out,contract_path):
    c=rj(contract_path); sel=c["selection_policy"]; out.mkdir(parents=True,exist_ok=True); fail=[]
    d1=out/"_d1_rebuild"; rebuild_d1(root,d1)
    if rj(d1/"HKCU_P2B_E2_D1_DECISION.json").get("status")!="PASS_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURE": raise SystemExit("UPSTREAM_D1_NOT_PASS")
    led=pd.read_csv(d1/"HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv",dtype={"stock_code_5d":str},keep_default_na=False); led["stock_code_5d"]=led.stock_code_5d.str.zfill(5)
    win=led[pd.to_numeric(led.p2a_overall_rank,errors="coerce").between(int(sel["rank_start"]),int(sel["rank_end"]),inclusive="both") & led.research_dimension.isin(DIMS)].copy()
    win=win.sort_values(["p2a_overall_rank","research_dimension","security_id"]).reset_index(drop=True)
    if len(win)!=sel["expected_dimension_rows"]: fail.append(f"DIMENSION_ROWS:{len(win)}")
    if win.security_id.nunique()!=sel["expected_security_count"]: fail.append("SECURITY_COUNT")
    if win.duplicated(["security_id","research_dimension"]).any(): fail.append("DUPLICATE_SECURITY_DIMENSION")
    if (win.evidence_status=="EVIDENCE_PARTIAL").sum()!=sel["expected_partial_rows"]: fail.append("PARTIAL_ROW_COUNT")
    if (win.evidence_status!="EVIDENCE_PARTIAL").sum()!=sel["expected_non_partial_rows"]: fail.append("NON_PARTIAL_ROW_COUNT")
    if (win.evidence_status=="RESEARCH_REQUIRED").sum()!=sel["expected_research_required_rows"]: fail.append("RESEARCH_REQUIRED_REMAINS")
    synth=d2_rule(root); rows=[]
    for r in win.itertuples(index=False):
        if r.evidence_status=="EVIDENCE_PARTIAL": x=normalize_partial(r,synth(pd.Series(r._asdict())))
        else:
            dr=direction(r.evidence_title,r.evidence_summary); x=dict(final_dimension_state="EVIDENCE_COMPLETE",final_direction=dr,final_materiality="HIGH" if dr in {"POSITIVE","NEGATIVE"} else "LOW",final_blocker=dr=="NEGATIVE",final_finding="PRIMARY_EVIDENCE_COMPLETE",next_required_evidence="Continue routine issuer monitoring.",monitor_trigger="New issuer disclosure or material company-specific event.",decision_lineage="D1_COMPLETE")
            if str(getattr(r,"deepening_finding",None))=="NO_QUALIFYING_ACTIVE_CATALYST": x.update(final_dimension_state="MONITOR_ONLY",final_direction="NEUTRAL",final_materiality="LOW",final_blocker=False,final_finding="NO_QUALIFYING_ACTIVE_CATALYST",next_required_evidence="No action until a new dated, security-specific and falsifiable catalyst appears.",monitor_trigger="New company-specific catalyst disclosure.",decision_lineage="D1_NEGATIVE_CATALYST_CLOSURE")
            elif dr=="NEGATIVE": x.update(final_dimension_state="RETAINED_DIRECT_NEGATIVE_SIGNAL",final_blocker=True,final_finding="DIRECT_NEGATIVE_SIGNAL_IN_COMPLETE_EVIDENCE",next_required_evidence="Current-period evidence showing whether the negative signal persists or reverses.",decision_lineage="GENERIC_DIRECT_NEGATIVE_GUARD")
        rows.append(dict(p2a_overall_rank=int(r.p2a_overall_rank),security_id=r.security_id,stock_code_5d=str(r.stock_code_5d).zfill(5),security_name=r.security_name,research_dimension=r.research_dimension,upstream_evidence_status=r.evidence_status,source_url=r.source_url,evidence_date=r.evidence_date,evidence_title=r.evidence_title,evidence_summary=r.evidence_summary,event_id=f"{r.security_id}|{r.research_dimension}|{r.evidence_date}|{r.evidence_title}",**x,alpha_score=pd.NA,trade_authority=TRADE_AUTHORITY))
    dim=pd.DataFrame(rows)
    ov=pd.read_csv(root/c["authoritative_inputs"]["targeted_resolution_overrides"],dtype={"stock_code_5d":str},keep_default_na=False); ov["stock_code_5d"]=ov.stock_code_5d.str.zfill(5)
    if len(ov)!=sel["expected_targeted_override_rows"]: fail.append(f"TARGETED_OVERRIDE_COUNT:{len(ov)}")
    if ov.duplicated(["security_id","research_dimension"]).any(): fail.append("DUPLICATE_OVERRIDE")
    if not set(zip(ov.security_id,ov.research_dimension)).issubset(set(zip(dim.security_id,dim.research_dimension))): fail.append("OVERRIDE_OUTSIDE_WINDOW")
    dates=pd.to_datetime(ov.evidence_date,errors="coerce")
    if dates.isna().any() or (dates>pd.Timestamp(sel["as_of_date"])).any(): fail.append("OVERRIDE_DATE")
    if not ov.source_url.str.startswith("https://www1.hkexnews.hk/").all(): fail.append("OVERRIDE_NON_HKEX_PRIMARY_SOURCE")
    om={(r.security_id,r.research_dimension):r for r in ov.itertuples(index=False)}
    for i,r in dim.iterrows():
        k=(r.security_id,r.research_dimension)
        if k not in om: continue
        x=om[k]
        for col in ["source_url","evidence_date","evidence_title","evidence_summary","event_id","final_dimension_state","final_direction","final_materiality","final_finding","next_required_evidence","monitor_trigger"]: dim.at[i,col]=getattr(x,col)
        dim.at[i,"final_blocker"]=bv(x.final_blocker); dim.at[i,"decision_lineage"]="S2_TARGETED_PRIMARY_OVERRIDE"
    dim=dim.sort_values(["p2a_overall_rank","research_dimension","security_id"]).reset_index(drop=True); dim.insert(0,"decision_dimension_row_id",range(1,len(dim)+1))
    if not set(dim.final_dimension_state).issubset(set(c["synthesis_policy"]["dimension_states"])): fail.append("DIMENSION_STATE_VOCABULARY")
    if dim.alpha_score.notna().any(): fail.append("ALPHA_SCORE_PRESENT")
    secrows=[]
    for sid,g in dim.groupby("security_id",sort=False):
        b=g[g.final_blocker.astype(bool)]; events=b.event_id.astype(str).replace("",pd.NA).dropna().nunique(); blocked=len(b)>0
        req=[x for x in g.loc[g.final_dimension_state.isin(["CONFIDENCE_CAP_MONITOR","LIMITED_CONFIDENCE","TARGETED_DEEPENING_REQUIRED","RETAINED_INVESTMENT_BLOCKER","RETAINED_DIRECT_NEGATIVE_SIGNAL"]),"next_required_evidence"].astype(str).tolist() if x]
        secrows.append(dict(p2a_overall_rank=int(g.p2a_overall_rank.iloc[0]),security_id=sid,stock_code_5d=str(g.stock_code_5d.iloc[0]).zfill(5),security_name=g.security_name.iloc[0],complete_dimension_count=int((g.upstream_evidence_status=="EVIDENCE_COMPLETE").sum()),partial_dimension_count=int((g.upstream_evidence_status=="EVIDENCE_PARTIAL").sum()),confidence_cap_dimension_count=int(g.final_dimension_state.isin(["CONFIDENCE_CAP_MONITOR","LIMITED_CONFIDENCE","TARGETED_DEEPENING_REQUIRED"]).sum()),retained_blocker_dimension_count=len(b),retained_blocker_event_count=int(events),positive_signal_count=int((g.final_direction=="POSITIVE").sum()),negative_signal_count=int((g.final_direction=="NEGATIVE").sum()),decision_state="HOLD_RETAINED_INVESTMENT_BLOCKER" if blocked else "ADVANCE_TO_P2B_CROSS_SECTIONAL_SYNTHESIS_WITH_CONFIDENCE_CAP",confidence_cap="BLOCKED_UNTIL_TRIGGER" if blocked else "MEDIUM",retained_blocker_summary=" | ".join(dict.fromkeys(b.final_finding.astype(str).tolist())),next_required_evidence=" | ".join(dict.fromkeys(req)),monitor_triggers=" | ".join(dict.fromkeys(g.monitor_trigger.astype(str).tolist())),p2a_rank_preserved=True,formal_candidate_graduation_allowed=False,alpha_score=pd.NA,trade_authority=TRADE_AUTHORITY))
    sec=pd.DataFrame(secrows).sort_values("p2a_overall_rank").reset_index(drop=True); blocked=sec[sec.decision_state=="HOLD_RETAINED_INVESTMENT_BLOCKER"].copy(); advance=sec[sec.decision_state!="HOLD_RETAINED_INVESTMENT_BLOCKER"].copy(); exp=c["expected_result"]
    if len(advance)!=exp["advance_security_count"]: fail.append(f"ADVANCE_SECURITY_COUNT:{len(advance)}")
    if len(blocked)!=exp["blocked_security_count"]: fail.append(f"BLOCKED_SECURITY_COUNT:{len(blocked)}")
    if set(blocked.security_id)!=set(exp["retained_blocker_security_ids"]): fail.append("RETAINED_BLOCKER_SECURITY_SET")
    if int(blocked.retained_blocker_event_count.sum())!=exp["retained_blocker_event_count"]: fail.append("RETAINED_BLOCKER_EVENT_COUNT")
    p=c["output_prefix"]; paths={k:out/f"{p}_{k}" for k in ["DIMENSION_DECISION_SURFACE.csv","SECURITY_DECISION_SYNTHESIS.csv","RETAINED_INVESTMENT_BLOCKERS.csv","DECISION.json","QUALITY_REPORT.json","DECISION_SYNTHESIS.md"]}
    dim.to_csv(paths["DIMENSION_DECISION_SURFACE.csv"],index=False); sec.to_csv(paths["SECURITY_DECISION_SYNTHESIS.csv"],index=False); blocked.to_csv(paths["RETAINED_INVESTMENT_BLOCKERS.csv"],index=False)
    status=c["pass_status"] if not fail else c["blocked_status"]
    dec=dict(program_id=c["program_id"],phase=c["phase"],status=status,rank_start=sel["rank_start"],rank_end=sel["rank_end"],security_count=len(sec),dimension_rows=len(dim),advance_security_count=len(advance),blocked_security_count=len(blocked),blocked_security_ids=blocked.security_id.tolist(),retained_blocker_event_count=int(blocked.retained_blocker_event_count.sum()) if len(blocked) else 0,targeted_override_count=len(ov),score_non_null_count=0,formal_candidate_graduation_allowed=False,candidate_pool_mutations=0,simulation_mutations=0,real_account_mutations=0,orders_created=0,next_gate=c["next_gate"],trade_authority=TRADE_AUTHORITY)
    qual=dict(program_id=c["program_id"],status="PASS" if not fail else "FAIL",hard_failures=sorted(set(fail)),p2a_rank_preserved_not_rescored=True,missing_consensus_is_not_bearish=True,ordinary_connected_transaction_is_not_automatic_blocker=True,cross_dimension_event_deduplication_enabled=True,fresh_primary_override_guard=True,formal_candidate_graduation_allowed=False,trade_authority=TRADE_AUTHORITY)
    wj(paths["DECISION.json"],dec); wj(paths["QUALITY_REPORT.json"],qual)
    lines=[f"# {c['report_title']}","",f"Status: **{status}**","",f"- Securities: {len(sec)}",f"- Advance with confidence cap: {len(advance)}",f"- Retained investment blockers: {len(blocked)}",f"- Retained blocker events after deduplication: {dec['retained_blocker_event_count']}","- Alpha scores: 0","- Formal Candidate graduation: not allowed","","| Rank | Code | Security | Decision state | Blocker events |","|---:|---|---|---|---:|"]
    for r in sec.itertuples(index=False): lines.append(f"| {r.p2a_overall_rank} | {r.stock_code_5d} | {r.security_name} | {r.decision_state} | {r.retained_blocker_event_count} |")
    paths["DECISION_SYNTHESIS.md"].write_text("\n".join(lines)+"\n",encoding="utf-8")
    man={"program_id":c["program_id"],"as_of_date":sel["as_of_date"],"files":{},"trade_authority":TRADE_AUTHORITY}
    for x in paths.values(): man["files"][x.name]={"sha256":sha(x),"bytes":x.stat().st_size}
    wj(out/f"{p}_MANIFEST.json",man)
    if fail: raise SystemExit(c["program_id"]+"_BUILD_FAILED:"+"|".join(sorted(set(fail))))
    print(json.dumps(dec,ensure_ascii=False,indent=2,sort_keys=True))

def main():
    a=argparse.ArgumentParser(); a.add_argument("--repo-root",default="."); a.add_argument("--contract",required=True); a.add_argument("--output",required=True); z=a.parse_args(); root=Path(z.repo_root).resolve(); cp=Path(z.contract); cp=cp if cp.is_absolute() else root/cp; build(root,Path(z.output).resolve(),cp)
if __name__=="__main__": main()
