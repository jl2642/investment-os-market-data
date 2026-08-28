from __future__ import annotations

import argparse
import importlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from automation.forward_validation.registered_evidence import (
    MAIN_FAMILIES,
    build_global_packet,
    canonical,
    d2_events_from_receipts,
    d2_semantic_identity,
    event_sort_key,
    main_family_baseline,
    main_family_events,
    parse_ts,
    sha256,
)

TRADE_AUTHORITY="NONE"
OLD_V1_CUTOFF="2026-08-27T13:42:29Z"


def load_json(path: Path | None,default: Any=None) -> Any:
    if path is None or not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path | None) -> list[dict[str,Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]


def write_json(path: Path,payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def write_jsonl(path: Path,rows: list[dict[str,Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in rows),encoding="utf-8")


def load_frozen_r2(runtime_root: Path):
    root=runtime_root.resolve()
    if not (root/"strategy_kernel_v2"/"phase3b_r2_contract.py").exists():
        raise RuntimeError("P45_FROZEN_R2_RUNTIME_MISSING")
    sys.path.insert(0,str(root))
    importlib.invalidate_caches()
    extractor=importlib.import_module("strategy_kernel_v2.historical_feature_extractor")
    r2=importlib.import_module("strategy_kernel_v2.phase3b_r2_contract")
    contract=r2.load_contract()
    errors=r2.validate_contract(contract)
    if errors:
        raise RuntimeError("P45_R2_CONTRACT_INVALID:"+";".join(errors))
    if len(contract.get("transform_catalog",[]))!=20:
        raise RuntimeError("P45_R2_TRANSFORM_COUNT_DRIFT")
    return extractor,r2,contract


def run_parallel(
    packet: Mapping[str,Any],
    data_by_id: Mapping[str,Any],
    *,
    runtime_root: Path,
) -> dict[str,Any]:
    extractor,r2,contract=load_frozen_r2(runtime_root)

    def loader(record: Mapping[str,Any]) -> Any:
        eid=str(record["evidence_id"])
        if eid not in data_by_id:
            raise RuntimeError("P45_MODEL_SPECIFIC_OR_OUTSIDE_PACKET_FETCH:"+eid)
        return deepcopy(data_by_id[eid])

    features=extractor.extract_model_neutral_features(packet,source_loader=loader)
    profiles=[]
    legacy=[]
    for sid,row in sorted(features.get("feature_rows",{}).items()):
        legacy.append({
            "security_id":sid,
            "security_name":row.get("security_name",sid),
            "legacy_disposition":row.get("legacy_disposition"),
            "legacy_reason_codes":list(row.get("legacy_reason_codes",[])),
            "provenance_evidence_ids":list(row.get("provenance_evidence_ids",[])),
            "ordinalized":False,
        })
        profiles.append(r2.transform_model_neutral_row(row,contract))
    comparison=r2.compare_r2_profiles(profiles,contract)
    return {
        "shared_packet_sha256":packet["packet_sha256"],
        "model_neutral_feature_row_count":len(features.get("feature_rows",{})),
        "unsupported_selected_evidence_ids":list(features.get("unsupported_selected_evidence_ids",[])),
        "subjective_feature_fill_count":features.get("subjective_feature_fill_count",0),
        "retrospective_probability_backfill_count":features.get("retrospective_probability_backfill_count",0),
        "retrospective_scenario_backfill_count":features.get("retrospective_scenario_backfill_count",0),
        "legacy":{
            "model_form":"LEGACY_POLICY_BASELINE",
            "rows":legacy,
            "ordinalization_count":0,
        },
        "r2":{
            "model_form":"EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2",
            "model_version":"R2.0.1_RESEARCH",
            "transform_rule_count":20,
            "profile_count":len(profiles),
            "profiles":profiles,
            "comparison":comparison,
            "transform_failure_count":sum(len(x.get("transform_failures",[])) for x in profiles),
        },
        "model_specific_evidence_fetch_count":0,
        "later_evidence_backfill_count":0,
    }


def add_checkpoint_edges(checkpoint_id: str,parallel: dict[str,Any]) -> list[dict[str,Any]]:
    edges=[]
    for group in parallel["r2"]["comparison"].get("groups",[]):
        if group.get("status")!="COMPARABLE_EXACT_SIGNATURE":
            continue
        sig=str(group["comparison_signature_sha256"])
        for dominated,dominators in sorted((group.get("dominated_by") or {}).items()):
            for dominator in sorted(dominators):
                edges.append({
                    "checkpoint_id":checkpoint_id,
                    "comparison_signature_sha256":sig,
                    "dominator_security_id":str(dominator),
                    "dominated_security_id":str(dominated),
                    "edge_id":sha256({
                        "checkpoint_id":checkpoint_id,
                        "signature":sig,
                        "dominator":str(dominator),
                        "dominated":str(dominated),
                    }),
                })
    return edges


def regime_id(packet: Mapping[str,Any],parallel: Mapping[str,Any]) -> str:
    signatures=sorted({
        str(p.get("comparison_signature_sha256"))
        for p in parallel["r2"].get("profiles",[])
        if p.get("comparison_signature_sha256")
    })
    missingness=sorted(
        (
            str(p.get("security_id")),
            tuple(sorted(p.get("missing_rule_ids",[]))),
            bool(p.get("comparison_contract_evaluable")),
        )
        for p in parallel["r2"].get("profiles",[])
    )
    return sha256({
        "families":packet["contributing_registered_family_ids"],
        "r2_signatures":signatures,
        "missingness_pattern":missingness,
    })


def audit_context(
    event_at: str,
    *,
    recommendation: Mapping[str,Any],
    recommendation_domain: Mapping[str,Any],
    trigger: Mapping[str,Any],
    shadow: Mapping[str,Any],
) -> dict[str,Any]:
    event_ts=parse_ts(event_at)
    rec_pub=str(recommendation_domain.get("published_at_utc") or "")
    rec_available=bool(rec_pub) and parse_ts(rec_pub)<=event_ts
    trig_time=str(trigger.get("generated_at_utc") or "")
    trig_available=bool(trig_time) and parse_ts(trig_time)<=event_ts
    return {
        "recommendation":{
            "status":"AVAILABLE_BY_EVENT_TIME" if rec_available else "NOT_AVAILABLE_BY_EVENT_TIME",
            "fingerprint":recommendation.get("recommendation_fingerprint") if rec_available else None,
            "published_at_utc":rec_pub if rec_available else None,
            "may_select_or_drop_checkpoint":False,
            "r2_feature_input":False,
        },
        "trigger_shadow":{
            "status":"AVAILABLE_BY_EVENT_TIME" if trig_available else "NOT_AVAILABLE_BY_EVENT_TIME",
            "source_fingerprint":trigger.get("source_fingerprint") if trig_available else None,
            "shadow_source_fingerprint":shadow.get("source_fingerprint") if trig_available else None,
            "may_select_or_drop_checkpoint":False,
            "r2_feature_input":False,
        },
    }


def baseline_candidate(
    *,
    repo_root: Path,
    main_source_commit: str,
    d2_source_commit: str,
    recommendation: Mapping[str,Any],
    recommendation_domain: Mapping[str,Any],
    trigger: Mapping[str,Any],
    shadow: Mapping[str,Any],
    operating_index: Mapping[str,Any],
    now: datetime,
) -> dict[str,Any]:
    main_sources=main_family_baseline(repo_root,main_source_commit)
    d2_source=d2_semantic_identity(repo_root,d2_source_commit)
    registered_baselines={
        **main_sources,
        "RESEARCH_D2":{
            k:v for k,v in d2_source.items() if k not in {"d2_state","artifacts"}
        },
    }
    return {
        "schema_version":"1.1.0",
        "surface_id":"P4_5_FORWARD_BASELINE_CANDIDATE",
        "status":"BASELINE_CANDIDATE_PENDING_OPERATING_PUBLICATION",
        "generated_at_utc":now.replace(microsecond=0).isoformat(),
        "eligibility_cutoff_utc":None,
        "old_v1_cutoff_utc":OLD_V1_CUTOFF,
        "old_v1_cutoff_effective":False,
        "protected_main_sha_at_candidate":main_source_commit,
        "registered_family_baselines":registered_baselines,
        "operating_context":{
            "recommendation_fingerprint":recommendation.get("recommendation_fingerprint"),
            "recommendation_published_at_utc":recommendation_domain.get("published_at_utc"),
            "trigger_source_fingerprint":trigger.get("source_fingerprint"),
            "shadow_source_fingerprint":shadow.get("source_fingerprint"),
        },
        "operating_domain_health":{
            str(x.get("domain_id")):{
                "health":x.get("health"),
                "watermark":(x.get("current") or {}).get("data_watermark"),
                "source_commit_sha":(x.get("current") or {}).get("source_commit_sha"),
            }
            for x in operating_index.get("domains",[])
        },
        "baseline_ineligibility":{
            "pre_cutoff_registered_sources_may_supply_model_features":False,
            "pre_cutoff_recommendation_events_ineligible":True,
            "pre_cutoff_shadow_events_ineligible":True,
            "stale_or_missing_domain_state_does_not_create_forward_evidence":True,
        },
        "phase4_forward_observation_count":0,
        "phase4_realized_outcome_read_count":0,
        "phase5_migration_allowed":False,
        "controls":{
            "candidate_membership_mutations":0,"real_account_mutations":0,
            "simulation_mutations":0,"target_portfolio_writebacks":0,
            "user_decisions_generated":0,"orders":0,"trade_authority":TRADE_AUTHORITY,
        },
    }


def discover_all_events(
    *,
    repo_root: Path,
    baseline: Mapping[str,Any],
    current_main_commit: str,
    d2_receipts_dir: Path,
) -> list[dict[str,Any]]:
    cutoff=str(baseline["eligibility_cutoff_utc"])
    baseline_main=str(baseline["protected_main_sha_at_acceptance"])
    events=main_family_events(
        repo_root,baseline_commit=baseline_main,current_commit=current_main_commit,cutoff_utc=cutoff
    )
    d2_base=str(baseline["registered_family_baselines"]["RESEARCH_D2"]["semantic_identity"])
    events.extend(d2_events_from_receipts(
        repo_root,receipts_dir=d2_receipts_dir,cutoff_utc=cutoff,
        baseline_semantic_identity=d2_base,
    ))
    return sorted(events,key=event_sort_key)


def build(
    *,
    mode: str,
    repo_root: Path,
    main_source_commit: str,
    d2_source_commit: str,
    recommendation_path: Path,
    recommendation_domain_path: Path,
    trigger_path: Path,
    shadow_path: Path,
    operating_index_path: Path,
    d2_receipts_dir: Path | None=None,
    baseline_path: Path | None=None,
    forward_current_path: Path | None=None,
    observation_ledger_path: Path | None=None,
    r2_runtime_root: Path | None=None,
    now: datetime | None=None,
) -> tuple[dict[str,Any] | None,dict[str,Any],list[dict[str,Any]],list[dict[str,Any]],dict[str,Any]]:
    now=now or datetime.now(timezone.utc)
    recommendation=load_json(recommendation_path)
    recommendation_domain=load_json(recommendation_domain_path)
    trigger=load_json(trigger_path)
    shadow=load_json(shadow_path)
    operating_index=load_json(operating_index_path)
    ledger=load_jsonl(observation_ledger_path)

    if mode=="baseline":
        if baseline_path and baseline_path.exists():
            raise RuntimeError("P45_BASELINE_ALREADY_EXISTS")
        baseline=baseline_candidate(
            repo_root=repo_root,main_source_commit=main_source_commit,
            d2_source_commit=d2_source_commit,recommendation=recommendation,
            recommendation_domain=recommendation_domain,trigger=trigger,shadow=shadow,
            operating_index=operating_index,now=now,
        )
        current={
            "schema_version":"1.1.0","surface_id":"P4_5_FORWARD_VALIDATION_CURRENT",
            "status":"BASELINE_PENDING_PUBLICATION","generated_at_utc":now.replace(microsecond=0).isoformat(),
            "eligibility_cutoff_utc":None,"accepted_checkpoint_count":0,
            "economically_mature_checkpoint_count":0,"phase4_forward_observation_count":0,
            "phase4_realized_outcome_read_count":0,
            "completion_outcome":"CONTINUE_P4_5_FORWARD_ACCUMULATION",
            "phase5_migration_allowed":False,"controls":deepcopy(baseline["controls"]),
        }
        receipt={
            "mode":"BASELINE","cycle_action":"FREEZE_CLEAN_BASELINE",
            "new_checkpoint_count":0,"observation_increment":0,"outcome_read_increment":0,
            "orders":0,"trade_authority":TRADE_AUTHORITY,
        }
        return baseline,current,ledger,[],receipt

    if mode!="collect":
        raise RuntimeError("P45_MODE_INVALID")
    baseline=load_json(baseline_path)
    if not baseline or not baseline.get("eligibility_cutoff_utc"):
        raise RuntimeError("P45_ACCEPTED_BASELINE_REQUIRED")
    if r2_runtime_root is None:
        raise RuntimeError("P45_FROZEN_R2_RUNTIME_REQUIRED")
    if d2_receipts_dir is None:
        raise RuntimeError("P45_D2_RECEIPTS_DIR_REQUIRED")

    prior_global={str(x.get("global_forward_evidence_state_fingerprint")) for x in ledger}
    events=discover_all_events(
        repo_root=repo_root,baseline=baseline,current_main_commit=main_source_commit,
        d2_receipts_dir=d2_receipts_dir,
    )
    active={}
    new_checkpoints=[]
    # Rebuild active post-cutoff evidence state deterministically from the full event census.
    for event in events:
        active[str(event["family_id"])]=event
        packet,data_by_id=build_global_packet(repo_root,event=event,active_versions=active)
        global_fp=str(packet["global_forward_evidence_state_fingerprint"])
        if global_fp in prior_global:
            continue
        parallel=run_parallel(packet,data_by_id,runtime_root=r2_runtime_root)
        checkpoint_id=str(packet["decision_point_id"])
        parallel["r2"]["dominance_edges"]=add_checkpoint_edges(checkpoint_id,parallel)
        regime=regime_id(packet,parallel)
        checkpoint={
            "schema_version":"1.1.0","checkpoint_id":checkpoint_id,
            "checkpoint_available_at_utc":event["available_at_utc"],
            "trigger_event":{
                "family_id":event["family_id"],
                "semantic_identity":event["semantic_identity"],
                "source_commit":event["source_commit"],
                "path":event["path"],
                "blob_sha":event["blob_sha"],
            },
            "global_forward_evidence_state_fingerprint":global_fp,
            "evidence_regime_id":regime,
            "shared_packet":packet,"parallel_outputs":parallel,
            "audit_context":audit_context(
                event["available_at_utc"],recommendation=recommendation,
                recommendation_domain=recommendation_domain,trigger=trigger,shadow=shadow,
            ),
            "entry_binding_complete":False,
            "outcome_schedule_status":"ENTRY_BINDING_REQUIRED_BEFORE_PUBLICATION",
            "outcomes":{},"economically_mature":False,
            "evaluation_eligibility":"POST_CLEAN_CUTOFF_FORWARD_EVIDENCE",
            "controls":{
                "result_based_selection":0,"model_specific_evidence_fetches":0,
                "later_evidence_backfills":0,"outcome_reads_at_checkpoint_creation":0,
                "orders":0,"trade_authority":TRADE_AUTHORITY,
            },
        }
        checkpoint["checkpoint_sha256"]=sha256({
            k:v for k,v in checkpoint.items() if k!="checkpoint_sha256"
        })
        new_checkpoints.append(checkpoint)
        ledger.append({
            "checkpoint_id":checkpoint_id,"checkpoint_sha256":checkpoint["checkpoint_sha256"],
            "available_at_utc":event["available_at_utc"],
            "trigger_family_id":event["family_id"],
            "trigger_semantic_identity":event["semantic_identity"],
            "global_forward_evidence_state_fingerprint":global_fp,
            "evidence_regime_id":regime,
            "contributing_registered_family_ids":packet["contributing_registered_family_ids"],
            "r2_profile_count":parallel["r2"]["profile_count"],
            "dominance_edge_count":len(parallel["r2"]["dominance_edges"]),
            "distinct_signature_count":len({
                str(p["comparison_signature_sha256"]) for p in parallel["r2"]["profiles"]
                if p.get("comparison_contract_evaluable")
            }),
            "economically_mature":False,
            "evaluation_eligibility":"POST_CLEAN_CUTOFF_FORWARD_EVIDENCE",
        })
        prior_global.add(global_fp)

    prior_current=load_json(forward_current_path,{})
    current={
        "schema_version":"1.1.0","surface_id":"P4_5_FORWARD_VALIDATION_CURRENT",
        "status":"ACTIVE_FORWARD_ACCUMULATION",
        "generated_at_utc":now.replace(microsecond=0).isoformat(),
        "eligibility_cutoff_utc":baseline["eligibility_cutoff_utc"],
        "registered_family_count":len(MAIN_FAMILIES)+1,
        "discovered_post_cutoff_event_count":len(events),
        "accepted_checkpoint_count":len(ledger),
        "economically_mature_checkpoint_count":sum(bool(x.get("economically_mature")) for x in ledger),
        "phase4_forward_observation_count":len(ledger),
        "phase4_realized_outcome_read_count":int(prior_current.get("phase4_realized_outcome_read_count",0)),
        "latest_cycle_new_checkpoint_count":len(new_checkpoints),
        "completion_outcome":"CONTINUE_P4_5_FORWARD_ACCUMULATION",
        "phase5_migration_allowed":False,
        "controls":{
            "candidate_membership_mutations":0,"real_account_mutations":0,
            "simulation_mutations":0,"target_portfolio_writebacks":0,
            "user_decisions_generated":0,"orders":0,"trade_authority":TRADE_AUTHORITY,
        },
    }
    receipt={
        "mode":"COLLECT",
        "cycle_action":"ACCEPT_NEW_FORWARD_CHECKPOINTS" if new_checkpoints else "NO_NEW_ELIGIBLE_CHECKPOINT",
        "new_checkpoint_count":len(new_checkpoints),
        "observation_increment":len(new_checkpoints),"outcome_read_increment":0,
        "orders":0,"trade_authority":TRADE_AUTHORITY,
    }
    return None,current,ledger,new_checkpoints,receipt


def validate_outputs(
    baseline: dict[str,Any] | None,current: dict[str,Any],
    ledger: list[dict[str,Any]],checkpoints: list[dict[str,Any]],receipt: dict[str,Any],
) -> list[str]:
    e=[]
    if current.get("phase5_migration_allowed") is not False: e.append("P45_PHASE5_PREMATURE")
    controls=current.get("controls",{})
    if controls.get("trade_authority")!="NONE": e.append("P45_TRADE")
    for k in ["candidate_membership_mutations","real_account_mutations","simulation_mutations","target_portfolio_writebacks","user_decisions_generated","orders"]:
        if int(controls.get(k,0))!=0: e.append("P45_PROTECTED_"+k)
    if baseline is not None:
        if baseline.get("eligibility_cutoff_utc") is not None: e.append("P45_CUTOFF_PREMATERIALIZED")
        if current.get("phase4_forward_observation_count")!=0: e.append("P45_BASELINE_OBSERVATION")
        if set(baseline.get("registered_family_baselines",{})) != set(MAIN_FAMILIES)|{"RESEARCH_D2"}:
            e.append("P45_BASELINE_FAMILY_SET")
    if current.get("phase4_forward_observation_count")!=len(ledger): e.append("P45_LEDGER_COUNT")
    for cp in checkpoints:
        if cp.get("controls",{}).get("outcome_reads_at_checkpoint_creation")!=0: e.append("P45_OUTCOME_LEAK")
        par=cp.get("parallel_outputs",{})
        if par.get("model_specific_evidence_fetch_count")!=0: e.append("P45_MODEL_FETCH")
        if par.get("later_evidence_backfill_count")!=0: e.append("P45_BACKFILL")
        if par.get("legacy",{}).get("ordinalization_count")!=0: e.append("P45_LEGACY_ORDINAL")
        if par.get("r2",{}).get("model_version")!="R2.0.1_RESEARCH": e.append("P45_R2_VERSION")
        if cp.get("evaluation_eligibility")!="POST_CLEAN_CUTOFF_FORWARD_EVIDENCE": e.append("P45_ELIGIBILITY")
    if receipt.get("outcome_read_increment")!=0: e.append("P45_PREMATURE_OUTCOME_READ")
    if receipt.get("orders")!=0 or receipt.get("trade_authority")!="NONE": e.append("P45_RECEIPT_AUTHORITY")
    return sorted(set(e))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,choices=["baseline","collect"])
    p.add_argument("--repo-root",default=".")
    p.add_argument("--main-source-commit",required=True)
    p.add_argument("--d2-source-commit",required=True)
    p.add_argument("--recommendation-current",required=True)
    p.add_argument("--recommendation-domain",required=True)
    p.add_argument("--trigger-current",required=True)
    p.add_argument("--shadow-current",required=True)
    p.add_argument("--operating-index",required=True)
    p.add_argument("--d2-receipts-dir")
    p.add_argument("--baseline")
    p.add_argument("--forward-current")
    p.add_argument("--observation-ledger")
    p.add_argument("--r2-runtime-root")
    p.add_argument("--output-dir",default=".p4_5_output")
    p.add_argument("--now")
    args=p.parse_args()
    now=datetime.fromisoformat(args.now.replace("Z","+00:00")) if args.now else None
    outputs=build(
        mode=args.mode,repo_root=Path(args.repo_root).resolve(),
        main_source_commit=args.main_source_commit,d2_source_commit=args.d2_source_commit,
        recommendation_path=Path(args.recommendation_current),
        recommendation_domain_path=Path(args.recommendation_domain),
        trigger_path=Path(args.trigger_current),shadow_path=Path(args.shadow_current),
        operating_index_path=Path(args.operating_index),
        d2_receipts_dir=Path(args.d2_receipts_dir) if args.d2_receipts_dir else None,
        baseline_path=Path(args.baseline) if args.baseline else None,
        forward_current_path=Path(args.forward_current) if args.forward_current else None,
        observation_ledger_path=Path(args.observation_ledger) if args.observation_ledger else None,
        r2_runtime_root=Path(args.r2_runtime_root) if args.r2_runtime_root else None,now=now,
    )
    errors=validate_outputs(*outputs)
    if errors: raise SystemExit(";".join(errors))
    baseline,current,ledger,checkpoints,receipt=outputs
    out=Path(args.output_dir)
    if baseline is not None: write_json(out/"FORWARD_BASELINE_CANDIDATE.json",baseline)
    write_json(out/"FORWARD_VALIDATION_CURRENT.json",current)
    write_jsonl(out/"FORWARD_OBSERVATION_LEDGER.jsonl",ledger)
    cdir=out/"checkpoint_candidates"; cdir.mkdir(parents=True,exist_ok=True)
    for cp in checkpoints: write_json(cdir/f"{cp['checkpoint_id']}.json",cp)
    write_json(out/"cycle_receipt.json",receipt)
    print(json.dumps({
        "mode":args.mode,"status":current["status"],
        "new_checkpoints":len(checkpoints),"observations":current["phase4_forward_observation_count"],
        "outcome_reads":current["phase4_realized_outcome_read_count"],
        "phase5":False,"orders":0,"trade_authority":"NONE",
    },ensure_ascii=False))

if __name__=="__main__":
    main()
