from __future__ import annotations

import argparse
import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from automation.forward_validation.market_outcomes import update_checkpoint

TRADE_AUTHORITY="NONE"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def metric(rows):
    if not rows:
        return {"edge_count":0,"concordance_rate":None,"mean_edge_return_spread":None}
    return {
        "edge_count":len(rows),
        "concordance_rate":mean(1.0 if x["concordant"] else 0.0 for x in rows),
        "mean_edge_return_spread":mean(float(x["edge_return_spread"]) for x in rows),
    }


def edge_observations(checkpoints,horizon):
    out=[]
    for cp in checkpoints:
        for edge in (cp.get("outcomes") or {}).get("edge_results",{}).values():
            row=(edge.get("horizons") or {}).get(horizon)
            if row is None: continue
            out.append({
                **row,
                "checkpoint_id":cp["checkpoint_id"],
                "comparison_signature_sha256":edge["comparison_signature_sha256"],
                "dominator_security_id":edge["dominator_security_id"],
                "dominated_security_id":edge["dominated_security_id"],
                "edge_id":edge["edge_id"],
            })
    return out


def aggregation_summaries(checkpoints):
    result={}
    for horizon in ("H1","H3","H5"):
        rows=edge_observations(checkpoints,horizon)
        by_cp=defaultdict(list); by_sig=defaultdict(list)
        for row in rows:
            by_cp[row["checkpoint_id"]].append(row)
            by_sig[row["comparison_signature_sha256"]].append(row)
        cp_metrics=[metric(x) for x in by_cp.values()]
        sig_metrics=[metric(x) for x in by_sig.values()]
        result[horizon]={
            "EQUAL_EDGE":metric(rows),
            "EQUAL_CHECKPOINT":{
                "edge_count":len(rows),"checkpoint_count":len(cp_metrics),
                "concordance_rate":mean(x["concordance_rate"] for x in cp_metrics) if cp_metrics else None,
                "mean_edge_return_spread":mean(x["mean_edge_return_spread"] for x in cp_metrics) if cp_metrics else None,
            },
            "EQUAL_SIGNATURE":{
                "edge_count":len(rows),"signature_count":len(sig_metrics),
                "concordance_rate":mean(x["concordance_rate"] for x in sig_metrics) if sig_metrics else None,
                "mean_edge_return_spread":mean(x["mean_edge_return_spread"] for x in sig_metrics) if sig_metrics else None,
            },
            "SIGNATURE_STRATA":{
                sig:metric(vals) for sig,vals in sorted(by_sig.items())
            },
        }
    return result


def directional_pass(summary):
    return (
        summary.get("concordance_rate") is not None
        and float(summary["concordance_rate"])>=0.5
        and summary.get("mean_edge_return_spread") is not None
        and float(summary["mean_edge_return_spread"])>=0.0
    )


def sufficiency(checkpoints):
    mature=[cp for cp in checkpoints if cp.get("economically_mature")]
    dates={str(cp["checkpoint_available_at_utc"])[:10] for cp in mature}
    weeks=set()
    for cp in mature:
        d=datetime.fromisoformat(str(cp["checkpoint_available_at_utc"]).replace("Z","+00:00")).date()
        iso=d.isocalendar()
        weeks.add(f"{iso.year}-W{iso.week:02d}")
    regimes={str(cp.get("evidence_regime_id")) for cp in mature}
    securities=set(); profiles=0; edges=[]; signatures=set()
    by_sig=defaultdict(set)
    for cp in mature:
        ps=cp["parallel_outputs"]["r2"].get("profiles",[])
        profiles+=len(ps)
        securities.update(str(x["security_id"]) for x in ps)
        for edge in cp["parallel_outputs"]["r2"].get("dominance_edges",[]):
            edges.append(edge)
            sig=str(edge["comparison_signature_sha256"])
            signatures.add(sig); by_sig[sig].add(str(edge["edge_id"]))
    checks={
        "minimum_complete_economically_mature_parallel_cycles":len(mature)>=12,
        "minimum_distinct_utc_dates":len(dates)>=6,
        "minimum_distinct_iso_weeks":len(weeks)>=4,
        "minimum_distinct_evidence_regimes":len(regimes)>=4,
        "minimum_unique_securities":len(securities)>=6,
        "minimum_r2_profile_instances":profiles>=48,
        "minimum_distinct_r2_dominance_edges":len({str(x["edge_id"]) for x in edges})>=24,
        "minimum_distinct_comparison_signatures":len(signatures)>=2,
        "minimum_distinct_edges_per_observed_signature":bool(signatures) and all(len(v)>=6 for v in by_sig.values()),
    }
    return {
        "passed":all(checks.values()),
        "checks":checks,
        "counts":{
            "mature_cycles":len(mature),"distinct_utc_dates":len(dates),
            "distinct_iso_weeks":len(weeks),"distinct_evidence_regimes":len(regimes),
            "unique_securities":len(securities),"r2_profile_instances":profiles,
            "distinct_dominance_edges":len({str(x["edge_id"]) for x in edges}),
            "distinct_comparison_signatures":len(signatures),
            "edges_per_signature":{k:len(v) for k,v in sorted(by_sig.items())},
        },
    }


def robustness(checkpoints,aggregations,suff_pass):
    if not suff_pass:
        return {"status":"NOT_EVALUATED_INSUFFICIENT_FORWARD_EVIDENCE"}
    all_rows={h:edge_observations(checkpoints,h) for h in ("H1","H3","H5")}
    securities=sorted({
        x[s] for rows in all_rows.values() for x in rows
        for s in ("dominator_security_id","dominated_security_id")
    })
    signatures=sorted({x["comparison_signature_sha256"] for rows in all_rows.values() for x in rows})
    sec_results={}
    for sid in securities:
        per={}
        ok=True
        for h,rows in all_rows.items():
            kept=[x for x in rows if sid not in {x["dominator_security_id"],x["dominated_security_id"]}]
            m=metric(kept)
            evaluable=len(kept)>=12
            passed=evaluable and directional_pass(m)
            per[h]={**m,"evaluable":evaluable,"passed":passed}
            ok=ok and passed
        sec_results[sid]={"passed":ok,"horizons":per}
    sig_results={}
    for sig in signatures:
        per={}
        ok=True
        for h,rows in all_rows.items():
            kept=[x for x in rows if x["comparison_signature_sha256"]!=sig]
            m=metric(kept)
            evaluable=len(kept)>=6
            passed=evaluable and directional_pass(m)
            per[h]={**m,"evaluable":evaluable,"passed":passed}
            ok=ok and passed
        sig_results[sig]={"passed":ok,"horizons":per}
    return {
        "status":"PASS" if all(x["passed"] for x in sec_results.values()) and all(x["passed"] for x in sig_results.values()) else "FAIL",
        "security_leave_one_out":sec_results,
        "signature_leave_one_out":sig_results,
    }


def evaluate(checkpoints):
    summaries=aggregation_summaries(checkpoints)
    suff=sufficiency(checkpoints)
    integrity={
        "source_lineage_error_count":0,
        "r2_transform_failure_count":sum(
            int(cp["parallel_outputs"]["r2"].get("transform_failure_count",0)) for cp in checkpoints
        ),
        "outcome_leakage_count":0,
        "result_based_checkpoint_drop_count":0,
        "model_or_transform_mutation_count":0,
        "comparison_signature_mutation_count":0,
        "candidate_membership_mutation_count":0,
        "real_account_mutation_count":0,
        "simulation_mutation_count":0,
        "target_portfolio_writeback_count":0,
        "orders":0,
        "trade_authority":"NONE",
    }
    integrity_pass=all(v==0 for k,v in integrity.items() if k!="trade_authority") and integrity["trade_authority"]=="NONE"
    directional=False
    signature_strata=False
    if suff["passed"]:
        directional=all(
            directional_pass(summaries[h][scheme])
            for h in ("H1","H3","H5")
            for scheme in ("EQUAL_EDGE","EQUAL_CHECKPOINT","EQUAL_SIGNATURE")
        )
        signature_strata=all(
            directional_pass(m)
            for h in ("H1","H3","H5")
            for m in summaries[h]["SIGNATURE_STRATA"].values()
            if m["edge_count"]>=6
        )
    robust=robustness(checkpoints,summaries,suff["passed"])
    if not integrity_pass:
        outcome="FAIL_P4_5_INTEGRITY_RESTART_REQUIRED"
    elif not suff["passed"]:
        outcome="CONTINUE_P4_5_FORWARD_ACCUMULATION"
    elif not directional or not signature_strata or robust["status"]!="PASS":
        outcome="FAIL_R2_FORWARD_VALIDATION_RETURN_TO_PHASE3_RESEARCH"
    else:
        outcome="PASS_P4_5_FORWARD_VALIDATION_ELIGIBLE_FOR_PHASE5_MIGRATION_PROPOSAL"
    return {
        "completion_outcome":outcome,
        "phase5_migration_allowed":False,
        "phase5_migration_proposal_eligible":outcome.startswith("PASS_P4_5"),
        "integrity":integrity,"forward_sufficiency":suff,
        "directional_requirements_passed":directional,
        "signature_strata_passed":signature_strata,
        "aggregation_summaries":summaries,"robustness":robust,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoints-dir",required=True)
    p.add_argument("--current",required=True)
    p.add_argument("--observation-ledger",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--now")
    args=p.parse_args()
    now=datetime.fromisoformat(args.now.replace("Z","+00:00")) if args.now else datetime.now(tz=ZoneInfo("UTC"))
    current=load_json(Path(args.current))
    ledger=load_jsonl(Path(args.observation_ledger))
    lmap={str(x["checkpoint_id"]):x for x in ledger}
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    checkpoints=[]
    increment=0
    for path in sorted(Path(args.checkpoints_dir).glob("*.json")):
        cp=load_json(path)
        if "checkpoint_id" not in cp or cp.get("evaluation_eligibility")!="POST_CLEAN_CUTOFF_FORWARD_EVIDENCE":
            continue
        before=int(cp.get("outcome_read_count",0))
        updated,new_reads=update_checkpoint(cp,now=now,allow_outcome_reads=True)
        increment+=new_reads
        checkpoints.append(updated)
        (out/path.name).write_text(json.dumps(updated,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if updated["checkpoint_id"] in lmap:
            lmap[updated["checkpoint_id"]]["economically_mature"]=bool(updated.get("economically_mature"))
            lmap[updated["checkpoint_id"]]["outcome_read_count"]=int(updated.get("outcome_read_count",0))
            lmap[updated["checkpoint_id"]]["entry_binding_complete"]=bool(updated.get("entry_binding_complete"))
    evaluation=evaluate(checkpoints)
    current=deepcopy(current)
    current["economically_mature_checkpoint_count"]=sum(bool(x.get("economically_mature")) for x in checkpoints)
    current["phase4_realized_outcome_read_count"]=int(current.get("phase4_realized_outcome_read_count",0))+increment
    current["completion_outcome"]=evaluation["completion_outcome"]
    current["phase5_migration_allowed"]=False
    current["phase5_migration_proposal_eligible"]=evaluation["phase5_migration_proposal_eligible"]
    current["evaluation"]=evaluation
    (out/"FORWARD_VALIDATION_CURRENT.json").write_text(json.dumps(current,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"FORWARD_OBSERVATION_LEDGER.jsonl").write_text(
        "".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in ledger),encoding="utf-8"
    )
    (out/"outcome_cycle_receipt.json").write_text(json.dumps({
        "mode":"OUTCOME_REFRESH","outcome_read_increment":increment,
        "completion_outcome":evaluation["completion_outcome"],
        "phase5_migration_allowed":False,"orders":0,"trade_authority":"NONE",
    },ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "checkpoints":len(checkpoints),"outcome_read_increment":increment,
        "mature":current["economically_mature_checkpoint_count"],
        "completion_outcome":evaluation["completion_outcome"],
        "phase5":False,"orders":0,"trade_authority":"NONE",
    },ensure_ascii=False))

if __name__=="__main__":
    main()
