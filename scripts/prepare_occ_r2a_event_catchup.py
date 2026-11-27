"""One bounded actual event catch-up on accepted inputs; never publishes Current.

Use existing CNINFO/statement/comparability/share-capital adapters and frozen
acceptance rules. Capture affected securities, not a full financial rebuild.
A title scan is screening evidence, not proof of complete economic events.
"""
from __future__ import annotations
import argparse
import io
import json
import re
import time
from pathlib import Path
import pandas as pd
import requests
import akshare as ak
from scripts import fmdl3b_core as facts
from scripts import fmdl3b_semantic_overrides as semantic
from scripts import fmdl3b2_validation_hardening as hardening
from scripts import fmdl3b3_core as comparable
from scripts import fmdl3cb_core as factors
from scripts import fmdl3db_core as shares
from scripts import run_fmdl3b2_canary as canary
from scripts import run_fmdl3b_pilot as pilot
from scripts import run_fmdl3b2_shard as shard
from scripts import scan_occ_r2b_financial_backlog as notice
from scripts.run_occ_r2a_exact_continuation import read_blob, read_json, manifest_map, parquet, csv, ROOT

FINANCIAL_BASIS = re.compile(r"会计政策|会计准则|会计差错|前期差错|会计估计|财务报表重述")
SHARE_TITLE = re.compile(r"股本|注册资本|股份变动|股份变更|股份注销|股票注销|注销股份|注销股票|转股|转增|送股|送红股|配股|股份发行|股票发行|发行股份|发行股票|股份登记|限售股|限售股份|解除限售|解禁|上市流通|股权激励|限制性股票|股票期权|股份回购|回购股份|回购.*注销|权益分派|吸收合并|股份合并|拆股|合股")
# Limit the one-time live test. Overflow is recorded, never silently truncated.
MAX_ALL_NOTICE_ROWS = 12000
MAX_SHARE_FETCHES = 96

def save_frame(frame, path):
    frame.to_parquet(path, index=False, compression="zstd")

def main():
    p=argparse.ArgumentParser()
    for key in ("market","exact","financial","audit"):
        p.add_argument("--"+key+"-commit",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    root=args.output
    root.mkdir(parents=True,exist_ok=True)
    M,V,F,A=args.market_commit,args.exact_commit,args.financial_commit,args.audit_commit
    mr=read_json(M,"outputs/current/CURRENT_RELEASE.json")
    fc=read_json(F,"outputs/occ_r2/financial/current/FINANCIAL_CONTEXT_RELEASE.json")
    vc=read_json(V,"outputs/occ_r2/valuation/current/FINANCIAL_VALUATION_CONTEXT_RELEASE.json")
    ap="outputs/occ_r2/financial_backlog_audit/"
    audit=read_json(A,ap+"FINANCIAL_FILING_BACKLOG_DECISION.json")
    e=pd.read_csv(io.BytesIO(read_blob(A,ap+"FINANCIAL_FILING_BACKLOG.csv")))
    scan=pd.read_csv(io.BytesIO(read_blob(A,ap+"NOTICE_SCAN_ATTEMPTS.csv")))
    cutoff=mr["as_of_date"]
    assert audit["status"]=="PASS" and audit["notice_source_success_ratio"]==1
    assert audit["start_date"]==fc["market_as_of_date"] and audit["end_date"]==cutoff
    assert len(e)==audit["financial_event_count"] and len(scan)==audit["notice_attempt_count"]
    assert vc["source_lineage"]["financial_source_commit"]==F
    u=csv(M,mr["current_files"]["a_share_universe"]["path"],mr["current_files"]["a_share_universe"]["sha256"])
    snap=csv(M,mr["current_files"]["daily_market_snapshot"]["path"],mr["current_files"]["daily_market_snapshot"]["sha256"])
    universe=set(u.symbol)
    assert set(snap.symbol)==universe and not u.symbol.duplicated().any()
    e["catchup_route"]="GOVERNANCE_OR_OTHER_REVIEW"
    e.loc[e.title.str.contains(FINANCIAL_BASIS,na=False),"catchup_route"]="ACCOUNTING_BASIS_REVIEW"
    e.loc[e.category.eq("财务报告"),"catchup_route"]="FINANCIAL_REPORT_REFRESH"
    e.to_csv(root/"FINANCIAL_EVENT_ROUTES.csv",index=False,encoding="utf-8-sig")
    affected=e.loc[e.catchup_route.isin(["FINANCIAL_REPORT_REFRESH","ACCOUNTING_BASIS_REVIEW"])]
    assert len(affected.symbol.unique())<=8, "FINANCIAL_SCOPE_EXCEEDS_BOUNDED_BATCH"
    cfg=json.loads((ROOT/"config/fmdl3b2_matrix.json").read_text())
    pcfg=json.loads((ROOT/"config/fmdl3b_statement_store.json").read_text())
    fcfg=json.loads((ROOT/"config/fmdl3cb_engine.json").read_text())
    index,payload=facts.load_registry(ROOT/"config/fmdl3b_field_registry.json")
    index,payload=semantic.apply_overrides(index,payload)
    days=pilot.fetch_calendar()
    outcomes=[]
    for symbol,group in affected.groupby("symbol",sort=True):
        directory=root/"financial"/symbol
        directory.mkdir(parents=True,exist_ok=True)
        outcome={"symbol":symbol,"routes":sorted(set(group.catchup_route)),"status":"BLOCKED","trade_authority":"NONE"}
        try:
            sample=shard.sample_for_symbol(symbol)
            sample["name"]=str(group.iloc[0]["name"])
            raw,revisions,sources,support=canary.extract_selected_facts(sample,shard.shard_runtime_config(cfg),index,days,as_of_cutoff=cutoff)
            save_frame(pd.DataFrame(raw),directory/"RAW_FACTS.parquet")
            save_frame(pd.DataFrame(revisions),directory/"REVISION_LEDGER.parquet")
            save_frame(pd.DataFrame(sources),directory/"SOURCE_INDEX.parquet")
            outcome["support"]=support
            outcome["raw_rows"]=len(raw)
            outcome["revision_rows"]=len(revisions)
            if not raw or not revisions or support["statement_status"]!="SUPPORTED":
                raise ValueError("STRUCTURED_STATEMENT_OR_OFFICIAL_PIT_UNAVAILABLE")
            normalized,conflicts=facts.select_normalized_facts(pd.DataFrame(raw),payload,pcfg["normalization"]["material_conflict_relative_tolerance"],pcfg["normalization"]["material_conflict_absolute_tolerance"])
            checks,flags,_=pilot.validation_checks(normalized,pd.DataFrame([support]),pcfg)
            normalized,checks,flags,controlled=hardening.harden_statement_validation(normalized,checks,flags,balance_relative_tolerance=pcfg["normalization"]["balance_sheet_relative_tolerance"],cash_relative_tolerance=pcfg["normalization"]["cash_flow_relative_tolerance"])
            save_frame(normalized,directory/"NORMALIZED_FACTS.parquet")
            save_frame(conflicts,directory/"CONFLICTS.parquet")
            checks.to_csv(directory/"VALIDATION_CHECKS.csv",index=False)
            flags.to_csv(directory/"QA_FLAGS.csv",index=False)
            good,errors=hardening.controlled_exclusions_are_classified(checks,flags)
            failed=int(checks.result.eq("FAIL").sum()) if len(checks) else 0
            duplicates=facts.duplicate_effective_intervals(normalized)
            outcome.update({"normalized_rows":len(normalized),"performed_failures":failed,"controlled_exclusions_classified":bool(good),"duplicate_intervals":int(duplicates)})
            if failed or not good or duplicates:
                raise ValueError("STATEMENT_QUALITY_GATE")
            _,status=comparable.build_authoritative_revision_lineage(pd.DataFrame(revisions))
            keys=normalized[["symbol","period_end"]].drop_duplicates().rename(columns={"period_end":"report_period_end"})
            status=pd.concat([status[["symbol","report_period_end"]],keys],ignore_index=True).drop_duplicates().merge(status,on=["symbol","report_period_end"],how="left",validate="one_to_one")
            for col in ["canonical_document_count","correction_notice_count"]:
                status[col]=status[col].fillna(0).astype(int)
            missing=status.canonical_document_count.eq(0)
            status.loc[missing,"restatement_status"]="UNRESOLVED_NO_CANONICAL_PERIODIC_DOCUMENT"
            status.loc[missing,"historical_replay_status"]="BLOCKED_NO_CANONICAL_PERIODIC_DOCUMENT"
            status["trade_authority"]="NONE"
            bridge=comparable.build_comparability_bridge(comparable.build_fact_overlay(normalized,status))
            bridge=bridge.loc[bridge.comparison_status.ne("COMPARABLE")]
            derived=factors.build_period_inputs(normalized,status,fcfg["engine"]["flow_inputs"],fcfg["engine"]["balance_inputs"],bridge)
            if derived.empty:
                raise ValueError("NO_DERIVED_INPUTS")
            profile=factors.infer_sector_profile(normalized)
            derived.insert(3,"sector_profile",profile)
            derived.insert(4,"factor_version",fcfg["engine"]["factor_version"])
            derived["authority"]=fcfg["authority"]
            derived["trade_authority"]="NONE"
            save_frame(derived,directory/"DERIVED_INPUTS.parquet")
            outcome["derived_rows"]=len(derived)
            outcome["profile"]=profile
            outcome["status"]="CAPTURED_PENDING_EVENT_TO_FACT_RECONCILIATION"
        except Exception as exc:
            outcome["error"]=f"{type(exc).__name__}:{str(exc)[:240]}"
        outcomes.append(outcome)
        print("TARGET_FINANCIAL",json.dumps(outcome,ensure_ascii=False,default=str),flush=True)
        (root/"FINANCIAL_OUTCOMES.json").write_text(json.dumps(outcomes,ensure_ascii=False,indent=2,default=str))
    # The old financial audit includes only two categories. Independently
    # inventory all notice titles over the share baseline gap, retaining
    # coverage and ambiguous titles; do not classify absence as proof.
    daily=[]
    all_rows=[]
    total=0
    for day in pd.date_range(vc["market_as_of_date"],cutoff):
        d=day.date().isoformat()
        entry={"date":d,"status":"FAILED"}
        try:
            r=requests.get("https://np-anotice-stock.eastmoney.com/api/security/ann",params={"sr":"-1","page_size":"100","page_index":"1","ann_type":"A","client_source":"web","f_node":"0","s_node":"0","begin_time":d,"end_time":d},timeout=20)
            r.raise_for_status()
            raw=r.json()
            assert raw.get("success") in (1,True) and isinstance(raw.get("data"),dict)
            hits=raw["data"]["total_hits"]
            assert type(hits) is int and hits>=0
            entry["total_hits"]=hits
            if total+hits>MAX_ALL_NOTICE_ROWS:
                raise ValueError("BOUNDED_NOTICE_ROW_LIMIT")
            if hits==0:
                assert raw["data"]["list"]==[]
                entry.update(status="PASS",rows=0)
            else:
                frame=ak.stock_notice_report(symbol="全部",date=d.replace("-",""))
                cols=notice.notice_columns(frame)
                assert all(cols[k] for k in ("code","title","url"))
                assert len(frame)==hits, f"NOTICE_COUNT_MISMATCH:{len(frame)}:{hits}"
                rows=[]
                for _,row in frame.iterrows():
                    title=str(row[cols["title"]])
                    rows.append({"date":d,"symbol":notice.bc.symbol_from_code(row[cols["code"]]),"title":title,"source_reference":str(row[cols["url"]]),"share_title_candidate":bool(SHARE_TITLE.search(title))})
                all_rows.extend(rows)
                total+=hits
                entry.update(status="PASS",rows=len(rows))
        except Exception as exc:
            entry["error"]=f"{type(exc).__name__}:{str(exc)[:200]}"
        daily.append(entry)
        print("SHARE_NOTICE_COVERAGE",json.dumps(entry,ensure_ascii=False),flush=True)
        (root/"SHARE_NOTICE_COVERAGE.json").write_text(json.dumps(daily,ensure_ascii=False,indent=2))
        if entry["status"]!="PASS":
            break
    all_frame=pd.DataFrame(all_rows)
    all_frame.to_csv(root/"ALL_SHARE_WINDOW_NOTICE_TITLES.csv",index=False,encoding="utf-8-sig")
    croot="outputs/capitalization/current/"
    cr=read_json(V,croot+"FMDL3DB_RELEASE.json")
    cm=manifest_map(V,croot+"FMDL3DB_MANIFEST.json",cr["release_id"])
    ledger=parquet(V,cr["effective_share_ledger_path"],cm["FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet"])
    known=set(ledger.loc[ledger.source_effective_date.astype(str).gt(vc["market_as_of_date"])&ledger.source_effective_date.astype(str).le(cutoff),"symbol"])
    new=universe-set(ledger.symbol)
    suspected=set(all_frame.loc[all_frame.share_title_candidate,"symbol"].dropna()) if len(all_frame) else set()
    # First cover new/missing share history and known effective events. All
    # notice candidates not fetched under this cap remain explicit backlog.
    queue=sorted(new&universe)+sorted((known&universe)-new)+sorted((suspected&universe)-new-known)
    queue=list(dict.fromkeys(queue))
    pd.DataFrame({"symbol":queue,"rank":range(1,len(queue)+1),"selected_in_bounded_batch":[i<MAX_SHARE_FETCHES for i in range(len(queue))]}).to_csv(root/"SHARE_REFRESH_QUEUE.csv",index=False)
    sec=u.set_index("symbol",drop=False)
    capcfg=json.loads((ROOT/"config/fmdl3db_engine.json").read_text())
    retrieved=[]
    fresh=[]
    # Do not proceed with broad symbol calls on incomplete notice inventory;
    # preserve all discovered evidence and the exact outstanding queue.
    full_notice=len(daily)==len(pd.date_range(vc["market_as_of_date"],cutoff)) and all(x["status"]=="PASS" for x in daily)
    selected=queue[:MAX_SHARE_FETCHES] if full_notice else list(dict.fromkeys(sorted(new&universe)+sorted(known&universe)))[:MAX_SHARE_FETCHES]
    for symbol in selected:
        row={"symbol":symbol,"status":"FAILED"}
        try:
            frame,attempt,err,msg,elapsed=shares.invoke_share_source(symbol,1,[0])
            row.update(attempts=attempt,error=err,elapsed=elapsed)
            if err:
                raise ValueError(str(err)+":"+str(msg))
            normalized,invalid,normerr=shares.normalize_share_history(frame,sec.loc[symbol].to_dict(),cutoff,capcfg,shares.now_iso())
            if normerr or not normalized:
                raise ValueError(normerr or "NO_SHARE_HISTORY")
            fresh.extend(normalized)
            row.update(status="CAPTURED",ledger_rows=len(normalized),invalid_rows=invalid)
        except Exception as exc:
            row["error"]=f"{type(exc).__name__}:{str(exc)[:200]}"
        retrieved.append(row)
        if len(retrieved)%10==0:
            print("SHARE_FETCH_PROGRESS",len(retrieved),len(selected),flush=True)
        if "ratelimit" in str(row.get("error","")).lower() or "429" in str(row.get("error","")):
            break
    save_frame(pd.DataFrame(fresh),root/"FRESH_SHARE_LEDGER.parquet")
    pd.DataFrame(retrieved).to_csv(root/"SHARE_FETCH_OUTCOMES.csv",index=False)
    summary={"status":"CANDIDATE_ONLY_EVENT_RECONCILIATION_PENDING","production_ready":False,
        "market_as_of_date":cutoff,"financial_target_symbols":len(outcomes),"financial_derived_captured":sum(x["status"].startswith("CAPTURED") for x in outcomes),
        "share_notice_days_accepted":sum(x["status"]=="PASS" for x in daily),"share_notice_days_expected":len(pd.date_range(vc["market_as_of_date"],cutoff)),
        "share_notice_titles":total,"share_queue_symbols":len(queue),"share_fetch_attempted":len(retrieved),"share_fetch_captured":sum(x["status"]=="CAPTURED" for x in retrieved),
        "source_commits":{"market":M,"financial":F,"exact":V,"notice":A},"trade_authority":"NONE","orders":0}
    (root/"EVENT_CATCHUP_DECISION.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print("EVENT_CATCHUP",json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
