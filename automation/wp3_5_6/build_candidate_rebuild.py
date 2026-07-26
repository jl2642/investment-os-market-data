#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from typing import Any
import pandas as pd

def rj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def wj(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
def rjl(p): return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]
def wjl(p,rows):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for x in rows),encoding="utf-8")
def clean(x):
    if x is None: return None
    try:
        if pd.isna(x): return None
    except (TypeError,ValueError): pass
    if hasattr(x,"item"):
        try: x=x.item()
        except (AttributeError,ValueError): pass
    if isinstance(x,float):
        if not math.isfinite(x): return None
        return round(x,12)
    return x
def rd(row): return {str(k):clean(v) for k,v in row.to_dict().items()}
def sh(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def fh(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()
def sid(code,ex):
    c=str(code).split(".")[0].zfill(6); e=str(ex or "").upper()
    if e in {"BSE","BJ"} or c.startswith(("4","8","92")): return c+".BJ"
    if e in {"SSE","SH","XSHG"} or c.startswith(("5","6")): return c+".SH"
    return c+".SZ"
def bval(x): return isinstance(x,bool) and x or str(x).lower() in {"true","1","yes"}

def gaps(d,prior,memo,bench,is_core):
    g=[]
    if not prior: g += ["SOURCE_BACKED_BUSINESS_MODEL_REQUIRED","OWNER_AND_COMPETITIVE_POSITION_REQUIRED","LATEST_PRIMARY_FILINGS_REQUIRED"]
    else: g += ["CURRENT_SOURCE_REFRESH_REQUIRED"]
    if not d.get("industry_name") or str(d.get("industry_name")) in {"nan","GENERAL_NON_FINANCIAL"}: g+=["INDUSTRY_PEER_REVIEW_REQUIRED"]
    if d.get("strategy_sleeve")=="FINANCIAL_SEPARATE_PROFILE": g+=["FINANCIAL_SECTOR_PACK_REQUIRED"]
    if int(d.get("valuation_valid_metric_count") or 0)<2: g+=["VALUATION_EVIDENCE_INCOMPLETE"]
    if not bench: g+=["BENCHMARK_REQUIRED"]
    if not prior and not memo: g+=["THESIS_FALSIFIER_CATALYST_REQUIRED"]
    if is_core and not memo: g+=["PORTFOLIO_ROLE_ETF_ALTERNATIVE_REQUIRED"]
    if str(d.get("prior_graduation_decision") or "")=="REJECTED": g+=["PRIOR_REJECTION_NEW_EVIDENCE_REQUIRED"]
    return sorted(set(g))

def route(d,is_core,prior,memo,bench,vstatus,g):
    if is_core:
        disp=str(d.get("core20_review_disposition") or "")
        hard={"VALUATION_EVIDENCE_INCOMPLETE","FINANCIAL_SECTOR_PACK_REQUIRED","PRIOR_REJECTION_NEW_EVIDENCE_REQUIRED"}
        if disp=="READMISSION_REVIEW_PRIORITY" and prior and prior.get("graduation_decision")=="GRADUATED" and memo and bench and vstatus=="RESEARCH_GRADE" and not hard.intersection(g):
            return "CANDIDATE_CORE_PROPOSED"
        if disp=="SEPARATE_PROFILE_REVIEW_REQUIRED": return "SHADOW_SEPARATE_PROFILE_REVIEW"
        if disp=="THESIS_REBUILD_REQUIRED_BEFORE_CANDIDATE_DECISION": return "SHADOW_THESIS_REBUILD"
        if disp.startswith("READMISSION_REVIEW"): return "SHADOW_READMISSION_REVIEW"
        return "SHADOW_RESEARCH_GAP"
    if str(d.get("prior_graduation_decision") or "")=="REJECTED": return "DEFERRED_PRIOR_REJECTION"
    return {"A_DEEP_DIVE":"SHADOW_DEEP_DIVE","B_STRUCTURED_RESEARCH":"RESEARCH_QUEUE_STRUCTURED"}.get(str(d.get("research_bucket") or ""),"WATCH_EVIDENCE_FILL")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default="."); ap.add_argument("--config",default="automation/wp3_5_6/config.json")
    ap.add_argument("--output-dir",default="investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_5_6/PROPOSALS/WP3_5_6_CANDIDATE_REBUILD_20260724_V1")
    a=ap.parse_args(); root=Path(a.repo_root).resolve(); cfg=rj(root/a.config); out=root/a.output_dir; out.mkdir(parents=True,exist_ok=True)
    sr=root/cfg["inputs"]["wp3_3_4_root"]
    work=pd.read_csv(sr/cfg["inputs"]["unified_workplan"],dtype={"security_code":str},encoding="utf-8-sig")
    long=pd.read_csv(sr/cfg["inputs"]["industry_longlist"],dtype={"security_code":str},encoding="utf-8-sig")
    core=pd.read_csv(sr/cfg["inputs"]["historical_core20_review"],dtype={"security_code":str},encoding="utf-8-sig")
    oldcand=rj(root/cfg["inputs"]["historical_candidate_state"]); oldres=rj(root/cfg["inputs"]["historical_research_state"])
    f4=rjl(root/cfg["inputs"]["fmdl4b_research_objects"])
    lm={str(x.security_code).zfill(6):rd(x) for _,x in long.iterrows()}; cm={str(x.security_code).zfill(6):rd(x) for _,x in core.iterrows()}
    oc={str(x.get("stock_code","")).zfill(6):x for x in oldcand.get("core_members",[]) if x.get("stock_code")}
    am={str(x.get("stock_code","")).zfill(6):x for x in oldres.get("legacy_active_memo_records",[]) if x.get("stock_code")}
    pr={str(x.get("symbol","")).split(".")[0].zfill(6):x for x in f4 if x.get("symbol")}
    R=[]; T=[]; V=[]; B=[]; C=[]; G=[]; M=[]
    for _,w in work.sort_values(["workplan_priority","security_code"]).iterrows():
        code=str(w.security_code).zfill(6); isc=bval(w.get("historical_core20")); d=cm.get(code,{}) if isc else lm.get(code,{})
        s=sid(code,d.get("exchange")); name=str(w.get("security_name") or d.get("security_name") or oc.get(code,{}).get("stock_name") or "")
        p=pr.get(code); memo=am.get(code); old=oc.get(code); bench=(memo or old or {}).get("primary_benchmark"); secbench=(memo or old or {}).get("secondary_benchmark")
        g=gaps(d,p,memo,bench,isc); vcount=int(d.get("valuation_valid_metric_count") or 0)
        vstatus="MISSING" if vcount<2 else ("RESEARCH_GRADE" if (p or memo or old) else "DRAFT")
        rt=route(d,isc,p,memo,bench,vstatus,g)
        life="DEFERRED" if p and p.get("graduation_decision")=="REJECTED" else ("ACTIVE_RESEARCH" if isc or w.get("workplan_lane")=="A_DEEP_DIVE" else ("TRIAGE" if w.get("workplan_lane")=="B_STRUCTURED_RESEARCH" else "IDEA"))
        thesis=(p or {}).get("variant_perception") or (old or {}).get("core_thesis")
        fals=[{"description":str(x),"status":"UNTESTED"} for x in (p or {}).get("prove_kill_checks",[])]
        if old and old.get("key_risk"): fals.append({"description":str(old["key_risk"]),"status":"CURRENT_REVIEW_REQUIRED"})
        cats=[{"description":str(x),"status":"UNTESTED"} for x in (p or {}).get("catalysts",[])]
        th={"thesis_id":f"WP3-5-TH-{s}","security_id":s,"security_name":name,"thesis_status":"DRAFT_SOURCE_BACKED" if thesis else "MISSING_RESEARCH_REQUIRED","thesis":thesis,"falsifiers":fals,"catalysts":cats,"evidence_ids":list((p or {}).get("evidence_ids",[])),"research_gaps":g,"authority":"RESEARCH_PROPOSAL_ONLY","trade_authority":"NONE"}; th["semantic_hash"]=sh(th)
        metrics={"current_price":clean(d.get("last_price") or d.get("close")),"pe_ttm":clean(d.get("current_pe_ttm")),"pb":clean(d.get("pb")),"fcf_yield_ttm":clean(d.get("current_fcf_yield_ttm")),"shareholder_yield_ttm":clean(d.get("current_shareholder_yield_ttm")),"valuation_context_state":d.get("valuation_context_state"),"price_linked_rebase_only":True,"underlying_financial_period_refreshed":False}
        val={"valuation_id":f"WP3-5-VAL-{s}","security_id":s,"security_name":name,"status":vstatus,"implied_expectations":None,"scenarios":[{"name":"CURRENT_REFERENCE_NOT_TARGET_PRICE","status":"REFERENCE_ONLY","metrics":metrics},{"name":"CONSERVATIVE_CASE","status":"INPUT_REQUIRED","required_inputs":["normalized_earnings","cash_conversion","industry_cycle","multiple"]},{"name":"UPSIDE_CASE","status":"INPUT_REQUIRED","required_inputs":["growth","competitive_position","capital_return","multiple"]},{"name":"DOWNSIDE_FALSIFICATION_CASE","status":"INPUT_REQUIRED","required_inputs":["falsifiers","balance_sheet_stress","earnings_downside","multiple_compression"]}],"downside":None,"decision_grade":False,"target_price_produced":False,"evidence_ids":["WP3-3-4-PRICE-LINKED-VALUATION"],"authority":"VALUATION_RESEARCH_PROPOSAL_ONLY","trade_authority":"NONE"}; val["semantic_hash"]=sh(val)
        complete=rt=="CANDIDATE_CORE_PROPOSED" and bool(bench) and th["thesis_status"]=="DRAFT_SOURCE_BACKED" and vstatus=="RESEARCH_GRADE" and metrics["current_price"] is not None
        base={"baseline_id":f"WP3-5-ENTRY-{s}","security_id":s,"security_name":name,"status":"COMPLETE" if complete else "MISSING","entry_date":cfg["as_of_date"] if complete else None,"entry_price":metrics["current_price"] if complete else None,"entry_valuation":metrics if complete else None,"benchmark":bench if complete else None,"secondary_benchmark":secbench if complete else None,"windows":[20,60,120],"thesis_id":th["thesis_id"] if complete else None,"prospective_only":True,"historical_backfill":False,"missing_requirements":[] if complete else sorted(set(([] if bench else ["BENCHMARK"])+([] if thesis else ["THESIS"])+([] if vstatus=="RESEARCH_GRADE" else ["RESEARCH_GRADE_VALUATION"])+([] if metrics["current_price"] is not None else ["ENTRY_PRICE"])+([] if rt=="CANDIDATE_CORE_PROPOSED" else ["HUMAN_APPROVED_CORE_ROUTE"]))),"authority":"ENTRY_BASELINE_PROPOSAL_ONLY","trade_authority":"NONE"}; base["semantic_hash"]=sh(base)
        res={"research_id":f"WP3-5-RSCH-{s}","security_id":s,"security_name":name,"lifecycle_state":life,"dimensions":{"strategy_sleeve":d.get("strategy_sleeve"),"research_bucket":"CORE20_MANDATORY_REVIEW" if isc else d.get("research_bucket"),"financial_score":clean(d.get("financial_score")),"profitability_returns_score":clean(d.get("profitability_returns_score")),"growth_momentum_score":clean(d.get("growth_momentum_score")),"cash_earnings_quality_score":clean(d.get("cash_earnings_quality_score")),"balance_sheet_efficiency_score":clean(d.get("balance_sheet_efficiency_score")),"research_priority_score":clean(d.get("research_priority_score")),"valuation_context_state":d.get("valuation_context_state")},"evidence_ids":sorted(set(["WP3-3-4-UNIFIED-WORKPLAN","WP3-3-4-MULTIDIMENSIONAL-ASSESSMENT"]+list((p or {}).get("evidence_ids",[])))),"decision_grade":False,"review_date":cfg["as_of_date"],"source_record":{"workplan_lane":w.get("workplan_lane"),"workplan_priority":clean(w.get("workplan_priority")),"historical_core20":isc,"prior_research_id":(p or {}).get("research_id"),"prior_graduation_decision":(p or {}).get("graduation_decision"),"legacy_active_memo":bool(memo),"core20_review_disposition":d.get("core20_review_disposition")},"business_model":(p or {}).get("business_model"),"competitive_position":(p or {}).get("competitive_position"),"owner_quality":(p or {}).get("owner_quality"),"why_now":(p or {}).get("why_now"),"variant_perception":(p or {}).get("variant_perception"),"risks":(p or {}).get("risks",[]) or ([old.get("key_risk")] if old and old.get("key_risk") else []),"research_gaps":g,"proposed_candidate_route":rt,"authority":"RESEARCH_AND_CANDIDATE_PROPOSAL_ONLY","trade_authority":"NONE"}; res["semantic_hash"]=sh(res)
        cand={"security_id":s,"security_code":code,"security_name":name,"historical_core20":isc,"historical_lifecycle_state":(old or {}).get("lifecycle_state","NONE"),"workplan_lane":w.get("workplan_lane"),"strategy_sleeve":d.get("strategy_sleeve"),"core20_review_disposition":d.get("core20_review_disposition"),"proposed_candidate_route":rt,"proposed_lifecycle_state":"CANDIDATE_CORE" if rt=="CANDIDATE_CORE_PROPOSED" else "NONE","research_id":res["research_id"],"research_lifecycle_state":life,"research_decision_grade":False,"thesis_id":th["thesis_id"],"thesis_status":th["thesis_status"],"valuation_id":val["valuation_id"],"valuation_status":vstatus,"entry_baseline_id":base["baseline_id"],"entry_baseline_status":base["status"],"portfolio_role":(old or {}).get("portfolio_role"),"benchmark":bench,"research_gap_count":len(g),"ready_for_user_decision":False,"buy_signal":"NO","real_account_permission":False,"simulation_admission_permission":False,"candidate_state_change_requires_human_merge":True,"trade_authority":"NONE"}; cand["semantic_hash"]=sh(cand)
        for z in g: G.append({"security_id":s,"security_code":code,"security_name":name,"workplan_lane":w.get("workplan_lane"),"gap_id":z,"priority":"P0" if isc or w.get("workplan_lane")=="A_DEEP_DIVE" else "P1","candidate_route_blocked":rt!="CANDIDATE_CORE_PROPOSED","trade_authority":"NONE"})
        if isc: M.append({"security_id":s,"security_code":code,"security_name":name,"historical_state":"CANDIDATE_CORE","core20_review_disposition":d.get("core20_review_disposition"),"proposed_route":rt,"proposed_state":cand["proposed_lifecycle_state"],"automatic_removal":False,"automatic_readmission":False,"user_merge_required":True,"trade_authority":"NONE"})
        R.append(res); T.append(th); V.append(val); B.append(base); C.append(cand)
    for x in (R,T,V,B,C): x.sort(key=lambda y:y["security_id"])
    G.sort(key=lambda y:(y["priority"],y["security_id"],y["gap_id"])); M.sort(key=lambda y:y["security_id"])
    wjl(out/"WP3_5_RESEARCH_OBJECT_PROPOSALS.jsonl",R); wjl(out/"WP3_5_THESIS_FALSIFIER_CATALYST_PROPOSALS.jsonl",T); wjl(out/"WP3_5_VALUATION_SCENARIO_PROPOSALS.jsonl",V); wjl(out/"WP3_5_ENTRY_BASELINE_PROPOSALS.jsonl",B)
    pd.DataFrame(G).to_csv(out/"WP3_5_RESEARCH_EVIDENCE_GAPS.csv",index=False,encoding="utf-8-sig"); pd.DataFrame(C).to_csv(out/"WP3_6_CANDIDATE_REBUILD_PROPOSAL.csv",index=False,encoding="utf-8-sig"); pd.DataFrame(M).to_csv(out/"WP3_6_HISTORICAL_CORE20_MIGRATION.csv",index=False,encoding="utf-8-sig")
    corep=[x for x in C if x["proposed_candidate_route"]=="CANDIDATE_CORE_PROPOSED"]; shadow=[x for x in C if x["proposed_candidate_route"].startswith("SHADOW_")]; ready=[x for x in C if x["proposed_candidate_route"]=="READY_FOR_USER_DECISION_PROPOSED"]; queue=[x for x in C if x["proposed_candidate_route"] in {"RESEARCH_QUEUE_STRUCTURED","WATCH_EVIDENCE_FILL","DEFERRED_PRIOR_REJECTION"}]
    state={"schema_version":"1.0.0","state_id":"CANDIDATE_REBUILD_WP3_6_20260724_V1","as_of":"2026-07-24_CLOSE","status":"ACCEPTED_ON_MAIN_IF_GOVERNED_PR_MERGED","source_state_id":oldcand.get("state_id"),"source_state_as_of":oldcand.get("as_of"),"promotion_evidence":"GIT_HISTORY_AND_USER_MERGE","candidate_state_change_authority":"USER_MERGE_OF_GOVERNED_PR","historical_core20_grandfathering":False,"candidate_core_members":corep,"shadow_track_members":shadow,"ready_for_user_decision_members":ready,"research_queue_members":queue,"historical_core20_migration":M,"historical_core20_archive":oldcand.get("core_members",[]),"counts":{"candidate_core":len(corep),"shadow_track":len(shadow),"ready_for_user_decision":len(ready),"research_queue":len(queue),"historical_core20":len(M),"historical_core20_retained_as_core":sum(x["proposed_state"]=="CANDIDATE_CORE" for x in M),"historical_core20_moved_to_shadow":sum(str(x["proposed_route"]).startswith("SHADOW_") for x in M)},"state_boundaries":{"real_account_mutations":0,"simulation_trade_mutations":0,"orders":0,"automatic_candidate_mutation":False,"human_merge_is_required_authority":True,"trade_authority":"NONE"}}; state["semantic_hash"]=sh(state); wj(out/"WP3_6_CANDIDATE_CURRENT_PROPOSED.json",state)
    metrics={"unified_workplan_rows":len(work),"research_object_proposals":len(R),"thesis_proposals":len(T),"valuation_proposals":len(V),"entry_baseline_proposals":len(B),"complete_entry_baselines":sum(x["status"]=="COMPLETE" for x in B),"research_gap_rows":len(G),"historical_core20_review_rows":len(M),"candidate_core_proposed":len(corep),"shadow_track_proposed":len(shadow),"ready_for_user_decision_proposed":len(ready),"research_queue_proposed":len(queue),"real_account_mutations":0,"simulation_trade_mutations":0,"orders":0}
    review=f"""# WP3-5 + WP3-6｜Research Object、Entry Baseline与Candidate重建提案\n\n- 统一研究计划：{len(work)}\n- Research Object提案：{len(R)}\n- Candidate Core提案：{len(corep)}\n- Shadow Track提案：{len(shadow)}\n- Ready for User Decision：{len(ready)}\n- 完整Entry Baseline：{metrics['complete_entry_baselines']}\n- 历史Core20迁移记录：{len(M)}\n- 真实账户、模拟盘和订单变更：0 / 0 / 0\n- trade_authority：NONE\n\n本轮拒绝把Longlist直接包装成Candidate。缺少来源支持的定性研究、当前披露、Thesis/Falsifier、估值情景或Benchmark的标的，只进入Research Queue或Shadow Track。历史Core20不享受祖父条款；只有既有来源支持研究、Active Memo、当前估值、完整前瞻性Entry Baseline与优先重审结论同时满足，才进入Candidate Core提案。\n\nReady for User Decision为{len(ready)}，没有生成BUY/ADD/REDUCE/SELL。Candidate状态差异只有在用户明确合并本PR后生效。\n"""; (out/"WP3_5_6_EXECUTIVE_REVIEW.md").write_text(review,encoding="utf-8")
    files={p.name:{"sha256":fh(p),"bytes":p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    manifest={"program_id":cfg["program_id"],"contract_version":cfg["contract_version"],"proposal_id":out.name,"as_of_date":cfg["as_of_date"],"status":"CANDIDATE_STATE_CHANGE_PROPOSAL_PENDING_USER_MERGE","method":"SOURCE_BACKED_RESEARCH_OBJECT_AND_ENTRY_BASELINE_GATED_CANDIDATE_REBUILD","metrics":metrics,"route_counts":{str(k):int(v) for k,v in pd.Series([x["proposed_candidate_route"] for x in C]).value_counts().sort_index().items()},"files":files,"authority":cfg["authority"],"candidate_state_change_authority":"USER_MERGE_OF_GOVERNED_PR","trade_authority":"NONE","next_gate":"WP4_DEEP_RESEARCH_AND_PORTFOLIO_DECISION_AFTER_CANDIDATE_REBUILD_ACCEPTANCE"}; wj(out/"WP3_5_6_MANIFEST.json",manifest)
    state["proposal_manifest"]=str((out/"WP3_5_6_MANIFEST.json").relative_to(root)); wj(root/"investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json",state)
    regp=root/"investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"; reg=rj(regp); reg.update({"register_id":"INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V3_6_CANDIDATE_REBUILD","status_date":"2026-07-26","overall_status":"WP3_COMPLETED_IF_CANDIDATE_REBUILD_PR_MERGES","current_step":"WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION","release_id":"INVESTMENT_OS_R13_20260726_WP3_5_6","release_sequence":13,"next_task":"RUN_WP4_DEEP_RESEARCH_AND_PORTFOLIO_DECISION_ON_ACCEPTED_CANDIDATE_STATE","trade_authority":"NONE"}); reg.setdefault("wp3_status",{}).update({"WP3-5":"COMPLETED_RESEARCH_OBJECT_ENTRY_BASELINE_PROPOSALS_ACCEPTED_IF_MERGED","WP3-6":"COMPLETED_CANDIDATE_REBUILD_STATE_ACCEPTED_IF_MERGED"}); reg["wp3_5_6"]={"status":"ACCEPTED_ON_MAIN_IF_THIS_PR_MERGES","proposal_id":out.name,"proposal_path":str(out.relative_to(root)),"as_of_date":cfg["as_of_date"],**metrics,"candidate_state_change_authority":"USER_MERGE_OF_GOVERNED_PR","trade_authority":"NONE","next_gate":manifest["next_gate"]}; reg.setdefault("mutation_proof",{}).update({"candidate_membership_mutations":"EXPLICIT_GOVERNED_DIFF_ONLY_EFFECTIVE_ON_USER_MERGE","research_object_mutations":0,"real_account_mutations":0,"simulation_trade_mutations":0,"automatic_rule_mutations":0,"orders":0,"trade_authority":"NONE"}); wj(regp,reg)
    plan=f"""# 股票投资助手｜Work Package Master Plan CURRENT\n\n- 状态日期：2026-07-26\n- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`\n- 交易权限：`NONE`\n\n## 当前阶段\n\n| Work Package | 状态 | 当前结论 |\n|---|---|---|\n| WP1 | COMPLETED | Canonical、规则、Runtime与Clean-Room验收完成 |\n| WP2 | COMPLETED | 账户、模拟盘、历史Candidate与市场诊断完成 |\n| WP3-1 | COMPLETED | 策略、Candidate治理、Entry Baseline与Research Readiness标准完成 |\n| WP3-2A / 2B | COMPLETED | 5530只Current与5525只研究Eligible Universe已接受 |\n| WP3-3 + WP3-4 | COMPLETED | 53只Longlist、20只历史Core重审和73只统一研究计划已接受 |\n| WP3-5 + WP3-6 | ACCEPTED IF THIS PR MERGES | {len(R)}只Research Object提案、{len(corep)}只Core、{len(shadow)}只Shadow、{len(ready)}只Ready |\n| WP4 | READY AFTER MERGE | 深研、组合适配和决策级估值 |\n| WP5–WP7 | PLANNED | 组合迁移、周期运营、归因复盘和真实试点 |\n\nCandidate状态只在用户明确合并本PR后生效。历史Core20不享受祖父条款，但完整历史快照与逐只迁移记录保留。真实账户、模拟盘、订单和自动规则变更均为0，`trade_authority=NONE`。\n"""; (root/"investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md").write_text(plan,encoding="utf-8")
    print(json.dumps({"status":"PASS","proposal":str(out.relative_to(root)),"metrics":metrics},ensure_ascii=False))
if __name__=="__main__": main()
