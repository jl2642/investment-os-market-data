#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

def rj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def wj(path,payload):
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
def rjl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def wjl(path,rows): Path(path).write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for x in rows),encoding="utf-8")
def stable(payload): return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def fh(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo-root",default="."); ap.add_argument("--output-dir",required=True)
    a=ap.parse_args(); root=Path(a.repo_root).resolve(); out=root/a.output_dir
    candp=out/"WP3_6_CANDIDATE_REBUILD_PROPOSAL.csv"; cand=pd.read_csv(candp,dtype={"security_code":str},encoding="utf-8-sig")
    resp=out/"WP3_5_RESEARCH_OBJECT_PROPOSALS.jsonl"; research=rjl(resp)
    basep=out/"WP3_5_ENTRY_BASELINE_PROPOSALS.jsonl"; bases=rjl(basep)
    valp=out/"WP3_5_VALUATION_SCENARIO_PROPOSALS.jsonl"; vals=rjl(valp)
    thp=out/"WP3_5_THESIS_FALSIFIER_CATALYST_PROPOSALS.jsonl"; theses=rjl(thp)
    statep=out/"WP3_6_CANDIDATE_CURRENT_PROPOSED.json"; state=rj(statep)
    currentp=root/"investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    oldres=rj(root/"investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_OBJECTS_CURRENT.json")
    f4=rjl(root/"outputs/fmdl4b/research/current/FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.jsonl")
    memos={str(x.get("stock_code","")).zfill(6):x for x in oldres.get("legacy_active_memo_records",[]) if x.get("stock_code")}
    prior={str(x.get("symbol","")).split(".")[0].zfill(6):x for x in f4 if x.get("symbol")}
    rmap={x["security_id"]:x for x in research}; bmap={x["security_id"]:x for x in bases}; vmap={x["security_id"]:x for x in vals}; tmap={x["security_id"]:x for x in theses}
    promoted=[]
    allowed_labels={"REAL_PRE_TRADE_MEMO_REQUIRED","REAL_REVIEW_ELIGIBLE"}
    for i,row in cand.iterrows():
        code=str(row["security_code"]).zfill(6); sid=str(row["security_id"]); memo=memos.get(code); pr=prior.get(code)
        eligible=(
            bool(row["historical_core20"])
            and str(row["proposed_candidate_route"]) in {"SHADOW_RESEARCH_GAP","SHADOW_READMISSION_REVIEW"}
            and pr and pr.get("graduation_decision")=="GRADUATED"
            and memo and memo.get("real_account_label") in allowed_labels
            and row["valuation_status"]=="RESEARCH_GRADE"
            and bool(row.get("benchmark"))
            and tmap[sid]["thesis_status"]=="DRAFT_SOURCE_BACKED"
        )
        if not eligible: continue
        val=vmap[sid]; current=val["scenarios"][0]["metrics"]
        base=bmap[sid]
        base.update({"status":"COMPLETE","entry_date":"2026-07-24","entry_price":current["current_price"],"entry_valuation":current,"benchmark":row["benchmark"],"secondary_benchmark":memo.get("secondary_benchmark"),"thesis_id":tmap[sid]["thesis_id"],"missing_requirements":[]})
        base.pop("semantic_hash",None); base["semantic_hash"]=stable(base)
        cand.loc[i,"proposed_candidate_route"]="CANDIDATE_CORE_PROPOSED"
        cand.loc[i,"proposed_lifecycle_state"]="CANDIDATE_CORE"
        cand.loc[i,"entry_baseline_status"]="COMPLETE"
        cand.loc[i,"semantic_hash"]=""
        rec=cand.loc[i].to_dict(); rec={k:(None if pd.isna(v) else v.item() if hasattr(v,"item") else v) for k,v in rec.items()}
        rec.pop("semantic_hash",None); cand.loc[i,"semantic_hash"]=stable(rec)
        rmap[sid]["proposed_candidate_route"]="CANDIDATE_CORE_PROPOSED"; rmap[sid].pop("semantic_hash",None); rmap[sid]["semantic_hash"]=stable(rmap[sid])
        promoted.append(code)
    research=sorted(rmap.values(),key=lambda x:x["security_id"]); bases=sorted(bmap.values(),key=lambda x:x["security_id"])
    wjl(resp,research); wjl(basep,bases); cand.to_csv(candp,index=False,encoding="utf-8-sig")
    rows=[{k:(None if pd.isna(v) else v.item() if hasattr(v,"item") else v) for k,v in x.items()} for x in cand.to_dict(orient="records")]
    core=[x for x in rows if x["proposed_candidate_route"]=="CANDIDATE_CORE_PROPOSED"]
    shadow=[x for x in rows if str(x["proposed_candidate_route"]).startswith("SHADOW_")]
    ready=[x for x in rows if x["proposed_candidate_route"]=="READY_FOR_USER_DECISION_PROPOSED"]
    queue=[x for x in rows if x["proposed_candidate_route"] in {"RESEARCH_QUEUE_STRUCTURED","WATCH_EVIDENCE_FILL","DEFERRED_PRIOR_REJECTION"}]
    state["candidate_core_members"]=core; state["shadow_track_members"]=shadow; state["ready_for_user_decision_members"]=ready; state["research_queue_members"]=queue
    state["counts"].update({"candidate_core":len(core),"shadow_track":len(shadow),"ready_for_user_decision":len(ready),"research_queue":len(queue)})
    state["counts"]["historical_core20_retained_as_core"]=sum(bool(x["historical_core20"]) for x in core)
    state["counts"]["historical_core20_moved_to_shadow"]=sum(bool(x["historical_core20"]) for x in shadow)
    state["qualitative_core_retain_policy"]="PRIOR_GRADUATED_RESEARCH_PLUS_ACTIVE_MEMO_PLUS_COMPLETE_PROSPECTIVE_BASELINE"
    state["qualitative_core_retain_codes"]=promoted
    state.pop("semantic_hash",None); state["semantic_hash"]=stable(state); wj(statep,state)
    current=dict(state); current["proposal_manifest"]=str((out/"WP3_5_6_MANIFEST.json").relative_to(root)); current.pop("semantic_hash",None); current["semantic_hash"]=stable(current); wj(currentp,current)
    manifestp=out/"WP3_5_6_MANIFEST.json"; manifest=rj(manifestp); m=manifest["metrics"]
    m.update({"candidate_core_proposed":len(core),"shadow_track_proposed":len(shadow),"ready_for_user_decision_proposed":len(ready),"research_queue_proposed":len(queue),"complete_entry_baselines":sum(x["status"]=="COMPLETE" for x in bases)})
    manifest["route_counts"]={str(k):int(v) for k,v in cand["proposed_candidate_route"].value_counts().sort_index().items()}
    manifest["qualitative_core_retain_codes"]=promoted
    review=f"""# WP3-5 + WP3-6｜Research Object、Entry Baseline与Candidate重建提案\n\n- 统一研究计划：{m['unified_workplan_rows']}\n- Research Object提案：{m['research_object_proposals']}\n- Candidate Core提案：{len(core)}\n- Shadow Track提案：{len(shadow)}\n- Ready for User Decision：{len(ready)}\n- 完整Entry Baseline：{m['complete_entry_baselines']}\n- 历史Core20迁移记录：{m['historical_core20_review_rows']}\n- 真实账户、模拟盘和订单变更：0 / 0 / 0\n- trade_authority：NONE\n\n本轮拒绝把Longlist直接包装成Candidate。新Longlist只能进入深研、结构化研究或证据补齐队列。历史Core20不享受祖父条款，但既有来源支持研究、Active Memo、当前估值、Benchmark和完整前瞻性Entry Baseline均具备的标的，可以保留为Candidate Core提案。\n\n本轮Core提案为：{', '.join(x['security_name'] for x in core)}。其余历史Core20转入Shadow强制补研，不是自动删除。Ready for User Decision为{len(ready)}，没有生成BUY/ADD/REDUCE/SELL。\n\nCandidate状态差异只有在用户明确合并本PR后生效。\n"""
    (out/"WP3_5_6_EXECUTIVE_REVIEW.md").write_text(review,encoding="utf-8")
    manifest["files"]={p.name:{"sha256":fh(p),"bytes":p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name!="WP3_5_6_MANIFEST.json"}
    wj(manifestp,manifest)
    current=rj(currentp); current.pop("semantic_hash",None); current["semantic_hash"]=stable(current); wj(currentp,current)
    regp=root/"investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"; reg=rj(regp)
    reg["wp3_5_6"].update({"candidate_core_proposed":len(core),"shadow_track_proposed":len(shadow),"ready_for_user_decision_proposed":len(ready),"research_queue_proposed":len(queue),"complete_entry_baselines":m["complete_entry_baselines"],"qualitative_core_retain_codes":promoted})
    wj(regp,reg)
    planp=root/"investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"; plan=planp.read_text(encoding="utf-8")
    plan=plan.replace("1只Core、39只Shadow、0只Ready","2只Core、38只Shadow、0只Ready")
    planp.write_text(plan,encoding="utf-8")
    contractp=root/"investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_OUTCOME_CONTRACT.json"; contract=rj(contractp)
    contract["pending_valid_entry_baseline_count_if_pr_merged"]=m["complete_entry_baselines"]
    contract["pending_status_if_pr_merged"]="BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS"
    contract["current_status_remains_fail_closed_until_merge_and_observation"]=True
    contract["alpha_claim_allowed"]=False; contract["trade_authority"]="NONE"; wj(contractp,contract)
    print(json.dumps({"status":"PASS","qualitative_core_retain_codes":promoted,"candidate_core":len(core),"shadow":len(shadow),"ready":len(ready)},ensure_ascii=False))
if __name__=="__main__": main()
