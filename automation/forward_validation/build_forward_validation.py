from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

TRADE_AUTHORITY="NONE"
DOMAIN="FORWARD_VALIDATION"
OLD_V1_CUTOFF="2026-08-27T13:42:29Z"
BASELINE_D2_SOURCE="a564a63dfbe7c68862bed6a7e13ec4b9047c2748"
BASELINE_RECOMMENDATION="d74b6d9d799ac2741b82d8764c374a298d57623925b37756d92b23b35e0c0ed7"
BASELINE_TRIGGER_SHADOW="b2b0e235cf47552407b2c938d8cf0d4e0105addc6b7e9e49a85b4f2961563b48"
BASELINE_FUNNEL="888ed5006df10a31f448fc4b0736ec76f6b4087728aae6f0576ba9bc8d44727f"
VOLATILE_D2_KEYS={"as_of","state_id","last_attempt_at","attempt_count","generated_at","generated_at_utc"}


def canonical(value: Any) -> str:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path | None, default: Any=None) -> Any:
    if path is None or not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path | None) -> list[dict[str,Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str,Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n" for row in rows),encoding="utf-8")


def parse_ts(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def git(*args: str, repo_root: Path) -> str:
    cp=subprocess.run(["git",*args],cwd=repo_root,text=True,capture_output=True,check=False)
    if cp.returncode!=0:
        raise RuntimeError(f"GIT_FAILED:{' '.join(args)}:{cp.stderr.strip()}")
    return cp.stdout


def blob_at(repo_root: Path, commit: str, path: str) -> str:
    return git("rev-parse",f"{commit}:{path}",repo_root=repo_root).strip()


def show_json(repo_root: Path, commit: str, path: str) -> dict[str,Any]:
    return json.loads(git("show",f"{commit}:{path}",repo_root=repo_root))


def strip_volatile(value: Any) -> Any:
    if isinstance(value,Mapping):
        return {
            k:strip_volatile(v)
            for k,v in sorted(value.items())
            if k not in VOLATILE_D2_KEYS
        }
    if isinstance(value,list):
        return [strip_volatile(x) for x in value]
    return value


def resolve_d2_artifacts(d2: Mapping[str,Any], source_commit: str, repo_root: Path) -> list[dict[str,Any]]:
    rows=[]
    for queue_row in sorted(d2.get("queue",[]),key=lambda x:str(x.get("security_id",""))):
        path=str(queue_row.get("semantic_artifact") or "")
        if not path:
            raise RuntimeError(f"P45_D2_SEMANTIC_ARTIFACT_MISSING:{queue_row.get('security_id')}")
        blob=blob_at(repo_root,source_commit,path)
        data=show_json(repo_root,source_commit,path)
        sid=str(queue_row["security_id"])
        if str(data.get("security_id"))!=sid:
            raise RuntimeError(f"P45_D2_ARTIFACT_SECURITY_MISMATCH:{sid}:{data.get('security_id')}")
        rows.append({
            "security_id":sid,
            "path":path,
            "blob_sha":blob,
            "input_watermark":queue_row.get("input_watermark"),
            "status":queue_row.get("status"),
            "research_disposition":queue_row.get("research_disposition"),
            "first_rejection_test":queue_row.get("first_rejection_test"),
        })
    return rows


def d2_semantic_fingerprint(d2: Mapping[str,Any], artifacts: list[dict[str,Any]]) -> str:
    return sha256({
        "d2":strip_volatile(d2),
        "artifact_identities":[
            {
                "security_id":x["security_id"],
                "path":x["path"],
                "blob_sha":x["blob_sha"],
            }
            for x in artifacts
        ],
    })


def domain_snapshot(index: Mapping[str,Any]) -> dict[str,Any]:
    out={}
    for row in index.get("domains",[]):
        cur=row.get("current") or {}
        out[str(row.get("domain_id"))]={
            "health":row.get("health"),
            "status":cur.get("status"),
            "watermark":cur.get("data_watermark"),
            "source_commit_sha":cur.get("source_commit_sha"),
            "source_run_id":cur.get("source_run_id"),
        }
    return out


def load_frozen_r2(runtime_root: Path):
    parent=runtime_root.resolve()
    if not (parent/"strategy_kernel_v2"/"phase3b_r2_contract.py").exists():
        raise RuntimeError("P45_FROZEN_R2_RUNTIME_MISSING")
    sys.path.insert(0,str(parent))
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


def build_shared_packet(
    *,
    d2: Mapping[str,Any],
    source_commit: str,
    artifacts: list[dict[str,Any]],
    repo_root: Path,
) -> tuple[dict[str,Any],dict[str,dict[str,Any]]]:
    selected=[]
    data_by_id={}
    for row in artifacts:
        evidence_id="P45_D2_"+sha256({
            "source_commit":source_commit,
            "path":row["path"],
            "blob_sha":row["blob_sha"],
        })[:24]
        selected.append({
            "evidence_id":evidence_id,
            "evidence_key":"RESEARCH_D2_"+row["security_id"].replace(".","_"),
            "evidence_class":["RESEARCH_D2","PRIMARY_DISCLOSURE_SYNTHESIS"],
            "security_ids":[row["security_id"]],
            "available_at":d2.get("as_of"),
            "source":{
                "commit_sha":source_commit,
                "path":row["path"],
                "blob_sha":row["blob_sha"],
                "provenance_status":"GOVERNED_D2_SOURCE",
            },
        })
        data_by_id[evidence_id]=show_json(repo_root,source_commit,row["path"])
    selected.sort(key=lambda x:x["evidence_id"])
    packet={
        "decision_point_id":"P45_"+sha256({
            "d2_source_commit":source_commit,
            "d2_semantic_state":d2_semantic_fingerprint(d2,artifacts),
        })[:20],
        "at":d2.get("as_of"),
        "canonical_commit_sha":source_commit,
        "opportunity_security_ids":sorted(str(x["security_id"]) for x in d2.get("queue",[])),
        "selected_evidence_ids":[x["evidence_id"] for x in selected],
        "selected_evidence":selected,
    }
    packet["packet_sha256"]=sha256(packet)
    return packet,data_by_id


def run_parallel(
    *,
    packet: Mapping[str,Any],
    data_by_id: Mapping[str,dict[str,Any]],
    runtime_root: Path,
) -> dict[str,Any]:
    extractor,r2,r2_contract=load_frozen_r2(runtime_root)

    def loader(record: Mapping[str,Any]) -> Any:
        evidence_id=str(record["evidence_id"])
        if evidence_id not in data_by_id:
            raise RuntimeError("P45_EVIDENCE_OUTSIDE_PACKET:"+evidence_id)
        return deepcopy(data_by_id[evidence_id])

    features=extractor.extract_model_neutral_features(packet,source_loader=loader)
    profiles=[]
    legacy=[]
    transform_failures=0
    for sid,row in sorted(features.get("feature_rows",{}).items()):
        legacy.append({
            "security_id":sid,
            "security_name":row.get("security_name",sid),
            "legacy_disposition":row.get("legacy_disposition"),
            "legacy_reason_codes":list(row.get("legacy_reason_codes",[])),
            "provenance_evidence_ids":list(row.get("provenance_evidence_ids",[])),
            "ordinalized":False,
        })
        profile=r2.transform_model_neutral_row(row,r2_contract)
        transform_failures+=len(profile.get("transform_failures",[]))
        profiles.append(profile)
    comparison=r2.compare_r2_profiles(profiles,r2_contract)
    edges=[]
    for group in comparison.get("groups",[]):
        if group.get("status")!="COMPARABLE_EXACT_SIGNATURE":
            continue
        sig=group["comparison_signature_sha256"]
        for dominated,dominators in sorted((group.get("dominated_by") or {}).items()):
            for dominator in sorted(dominators):
                edges.append({
                    "comparison_signature_sha256":sig,
                    "dominator_security_id":dominator,
                    "dominated_security_id":dominated,
                    "edge_id":sha256({
                        "signature":sig,
                        "dominator":dominator,
                        "dominated":dominated,
                    }),
                })
    return {
        "shared_packet_sha256":packet["packet_sha256"],
        "legacy":{
            "model_form":"LEGACY_POLICY_BASELINE",
            "rows":legacy,
            "ordinalization_count":0,
        },
        "r2":{
            "model_form":"EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2",
            "model_version":"R2.0.1_RESEARCH",
            "profile_count":len(profiles),
            "profiles":profiles,
            "comparison":comparison,
            "dominance_edges":edges,
            "transform_failure_count":transform_failures,
        },
        "model_specific_evidence_fetch_count":0,
        "later_evidence_backfill_count":0,
    }


def baseline_candidate(
    *,
    d2: Mapping[str,Any],
    d2_domain: Mapping[str,Any],
    recommendation: Mapping[str,Any],
    recommendation_domain: Mapping[str,Any],
    trigger: Mapping[str,Any],
    shadow: Mapping[str,Any],
    index: Mapping[str,Any],
    d2_source_commit: str,
    artifacts: list[dict[str,Any]],
    now: datetime,
) -> dict[str,Any]:
    semantic=d2_semantic_fingerprint(d2,artifacts)
    return {
        "schema_version":"1.0.0",
        "surface_id":"P4_5_FORWARD_BASELINE_CANDIDATE",
        "status":"BASELINE_CANDIDATE_PENDING_OPERATING_PUBLICATION",
        "generated_at_utc":now.replace(microsecond=0).isoformat(),
        "eligibility_cutoff_utc":None,
        "old_v1_cutoff_utc":OLD_V1_CUTOFF,
        "old_v1_cutoff_effective":False,
        "protected_main_sha_at_entry":"cd9b354410a60dc6d54267c1a58b06a1e6ba8e28",
        "operating_snapshot":{
            "d2_source_commit":d2_source_commit,
            "d2_semantic_fingerprint":semantic,
            "d2_domain_published_at_utc":d2_domain.get("published_at_utc"),
            "d2_domain_status":d2_domain.get("status"),
            "recommendation_fingerprint":recommendation.get("recommendation_fingerprint"),
            "recommendation_domain_published_at_utc":recommendation_domain.get("published_at_utc"),
            "trigger_shadow_source_fingerprint":trigger.get("source_fingerprint"),
            "shadow_source_fingerprint":shadow.get("source_fingerprint"),
            "opportunity_funnel_fingerprint":(
                recommendation.get("source_snapshot",{}).get("opportunity_funnel",{}).get("identity")
                or BASELINE_FUNNEL
            ),
            "d2_artifact_identities":artifacts,
            "domain_health":domain_snapshot(index),
        },
        "baseline_ineligibility":{
            "all_pre_cutoff_recommendation_events_ineligible":True,
            "all_pre_cutoff_shadow_events_ineligible":True,
            "stale_or_missing_domain_state_does_not_create_forward_evidence":True,
        },
        "phase4_forward_observation_count":0,
        "phase4_realized_outcome_read_count":0,
        "phase5_migration_allowed":False,
        "controls":{
            "candidate_membership_mutations":0,
            "real_account_mutations":0,
            "simulation_mutations":0,
            "target_portfolio_writebacks":0,
            "user_decisions_generated":0,
            "orders":0,
            "trade_authority":TRADE_AUTHORITY,
        },
    }


def build(
    *,
    mode: str,
    d2_path: Path,
    d2_domain_path: Path,
    recommendation_path: Path,
    recommendation_domain_path: Path,
    trigger_path: Path,
    shadow_path: Path,
    index_path: Path,
    d2_source_commit: str,
    repo_root: Path,
    baseline_path: Path | None=None,
    forward_current_path: Path | None=None,
    observation_ledger_path: Path | None=None,
    r2_runtime_root: Path | None=None,
    now: datetime | None=None,
) -> tuple[dict[str,Any] | None,dict[str,Any],list[dict[str,Any]],dict[str,Any] | None,dict[str,Any]]:
    now=now or datetime.now(timezone.utc)
    d2=load_json(d2_path)
    d2_domain=load_json(d2_domain_path)
    recommendation=load_json(recommendation_path)
    recommendation_domain=load_json(recommendation_domain_path)
    trigger=load_json(trigger_path)
    shadow=load_json(shadow_path)
    index=load_json(index_path)
    artifacts=resolve_d2_artifacts(d2,d2_source_commit,repo_root)
    semantic=d2_semantic_fingerprint(d2,artifacts)
    prior_current=load_json(forward_current_path,{})
    ledger=load_jsonl(observation_ledger_path)

    if mode=="baseline":
        if baseline_path and baseline_path.exists():
            raise RuntimeError("P45_BASELINE_ALREADY_EXISTS")
        baseline=baseline_candidate(
            d2=d2,d2_domain=d2_domain,recommendation=recommendation,
            recommendation_domain=recommendation_domain,trigger=trigger,shadow=shadow,index=index,
            d2_source_commit=d2_source_commit,artifacts=artifacts,now=now,
        )
        current={
            "schema_version":"1.0.0",
            "surface_id":"P4_5_FORWARD_VALIDATION_CURRENT",
            "status":"BASELINE_PENDING_PUBLICATION",
            "generated_at_utc":now.replace(microsecond=0).isoformat(),
            "eligibility_cutoff_utc":None,
            "baseline_d2_source_commit":d2_source_commit,
            "baseline_d2_semantic_fingerprint":semantic,
            "accepted_checkpoint_count":0,
            "economically_mature_checkpoint_count":0,
            "phase4_forward_observation_count":0,
            "phase4_realized_outcome_read_count":0,
            "completion_outcome":"CONTINUE_P4_5_FORWARD_ACCUMULATION",
            "phase5_migration_allowed":False,
            "controls":deepcopy(baseline["controls"]),
        }
        receipt={
            "mode":"BASELINE",
            "cycle_action":"FREEZE_CLEAN_BASELINE",
            "d2_semantic_fingerprint":semantic,
            "observation_increment":0,
            "outcome_read_increment":0,
            "orders":0,
            "trade_authority":TRADE_AUTHORITY,
        }
        return baseline,current,ledger,None,receipt

    if mode!="collect":
        raise ValueError("P45_MODE_INVALID")
    baseline=load_json(baseline_path)
    if not baseline or not baseline.get("eligibility_cutoff_utc"):
        raise RuntimeError("P45_ACCEPTED_BASELINE_REQUIRED")
    cutoff=parse_ts(str(baseline["eligibility_cutoff_utc"]))
    d2_published=parse_ts(str(d2_domain.get("published_at_utc")))
    baseline_semantic=str(baseline["operating_snapshot"]["d2_semantic_fingerprint"])
    prior_fingerprints={str(x["d2_semantic_fingerprint"]) for x in ledger}
    eligible=True
    reasons=[]
    if d2_domain.get("status")!="PASS":
        eligible=False; reasons.append("RESEARCH_D2_DOMAIN_NOT_PASS")
    if d2_published<=cutoff:
        eligible=False; reasons.append("D2_PUBLICATION_NOT_STRICTLY_POST_CUTOFF")
    if d2_source_commit==baseline["operating_snapshot"]["d2_source_commit"]:
        eligible=False; reasons.append("D2_SOURCE_COMMIT_EQUALS_BASELINE")
    if semantic==baseline_semantic or semantic in prior_fingerprints:
        eligible=False; reasons.append("D2_SEMANTIC_STATE_ALREADY_BASELINED_OR_COUNTED")

    checkpoint=None
    if eligible:
        if r2_runtime_root is None:
            raise RuntimeError("P45_R2_RUNTIME_REQUIRED_FOR_ELIGIBLE_CHECKPOINT")
        packet,data_by_id=build_shared_packet(
            d2=d2,source_commit=d2_source_commit,artifacts=artifacts,repo_root=repo_root
        )
        parallel=run_parallel(packet=packet,data_by_id=data_by_id,runtime_root=r2_runtime_root)
        checkpoint_id=packet["decision_point_id"]
        checkpoint={
            "schema_version":"1.0.0",
            "checkpoint_id":checkpoint_id,
            "checkpoint_available_at_utc":d2_domain["published_at_utc"],
            "d2_source_commit":d2_source_commit,
            "d2_semantic_fingerprint":semantic,
            "d2_artifact_identities":artifacts,
            "shared_packet":packet,
            "parallel_outputs":parallel,
            "recommendation_context":{
                "fingerprint":recommendation.get("recommendation_fingerprint"),
                "published_at_utc":recommendation_domain.get("published_at_utc"),
                "may_select_checkpoint":False,
                "r2_feature_input":False,
            },
            "trigger_shadow_context":{
                "source_fingerprint":trigger.get("source_fingerprint"),
                "shadow_source_fingerprint":shadow.get("source_fingerprint"),
                "may_select_checkpoint":False,
                "r2_feature_input":False,
            },
            "outcome_schedule_status":"PENDING_FUTURE_SESSION_CALENDAR_AND_MATURITY",
            "outcomes":{},
            "economically_mature":False,
            "evaluation_eligibility":"POST_CLEAN_CUTOFF_FORWARD_EVIDENCE",
            "controls":{
                "result_based_selection":0,
                "model_specific_evidence_fetches":0,
                "later_evidence_backfills":0,
                "outcome_reads_at_checkpoint_creation":0,
                "orders":0,
                "trade_authority":TRADE_AUTHORITY,
            },
        }
        checkpoint["checkpoint_sha256"]=sha256({
            k:v for k,v in checkpoint.items() if k!="checkpoint_sha256"
        })
        ledger.append({
            "checkpoint_id":checkpoint_id,
            "checkpoint_sha256":checkpoint["checkpoint_sha256"],
            "available_at_utc":d2_domain["published_at_utc"],
            "d2_source_commit":d2_source_commit,
            "d2_semantic_fingerprint":semantic,
            "r2_profile_count":parallel["r2"]["profile_count"],
            "dominance_edge_count":len(parallel["r2"]["dominance_edges"]),
            "distinct_signature_count":len({
                x["comparison_signature_sha256"] for x in parallel["r2"]["dominance_edges"]
            }),
            "economically_mature":False,
            "evaluation_eligibility":"POST_CLEAN_CUTOFF_FORWARD_EVIDENCE",
        })

    current={
        "schema_version":"1.0.0",
        "surface_id":"P4_5_FORWARD_VALIDATION_CURRENT",
        "status":"ACTIVE_FORWARD_ACCUMULATION",
        "generated_at_utc":now.replace(microsecond=0).isoformat(),
        "eligibility_cutoff_utc":baseline["eligibility_cutoff_utc"],
        "baseline_d2_source_commit":baseline["operating_snapshot"]["d2_source_commit"],
        "baseline_d2_semantic_fingerprint":baseline_semantic,
        "latest_seen_d2_source_commit":d2_source_commit,
        "latest_seen_d2_semantic_fingerprint":semantic,
        "latest_selector_eligible":eligible,
        "latest_selector_reason_codes":reasons,
        "accepted_checkpoint_count":len(ledger),
        "economically_mature_checkpoint_count":sum(bool(x.get("economically_mature")) for x in ledger),
        "phase4_forward_observation_count":len(ledger),
        "phase4_realized_outcome_read_count":int(prior_current.get("phase4_realized_outcome_read_count",0)),
        "completion_outcome":"CONTINUE_P4_5_FORWARD_ACCUMULATION",
        "phase5_migration_allowed":False,
        "controls":{
            "candidate_membership_mutations":0,
            "real_account_mutations":0,
            "simulation_mutations":0,
            "target_portfolio_writebacks":0,
            "user_decisions_generated":0,
            "orders":0,
            "trade_authority":TRADE_AUTHORITY,
        },
    }
    receipt={
        "mode":"COLLECT",
        "cycle_action":"ACCEPT_NEW_FORWARD_CHECKPOINT" if eligible else "NO_NEW_ELIGIBLE_CHECKPOINT",
        "d2_semantic_fingerprint":semantic,
        "observation_increment":1 if eligible else 0,
        "outcome_read_increment":0,
        "orders":0,
        "trade_authority":TRADE_AUTHORITY,
    }
    return None,current,ledger,checkpoint,receipt


def validate_outputs(
    baseline: dict[str,Any] | None,
    current: dict[str,Any],
    ledger: list[dict[str,Any]],
    checkpoint: dict[str,Any] | None,
    receipt: dict[str,Any],
) -> list[str]:
    e=[]
    if current.get("phase5_migration_allowed") is not False:
        e.append("P45_PHASE5_PREMATURE")
    if current.get("controls",{}).get("trade_authority")!="NONE":
        e.append("P45_TRADE_AUTHORITY")
    for k in [
        "candidate_membership_mutations","real_account_mutations","simulation_mutations",
        "target_portfolio_writebacks","user_decisions_generated","orders",
    ]:
        if int(current.get("controls",{}).get(k,0))!=0:
            e.append("P45_PROTECTED_"+k)
    if baseline is not None:
        if baseline.get("eligibility_cutoff_utc") is not None:
            e.append("P45_BASELINE_CANDIDATE_CUTOFF_PREMATERIALIZED")
        if current.get("phase4_forward_observation_count")!=0:
            e.append("P45_BASELINE_OBSERVATION_NONZERO")
        if current.get("phase4_realized_outcome_read_count")!=0:
            e.append("P45_BASELINE_OUTCOME_NONZERO")
    if current.get("phase4_forward_observation_count")!=len(ledger):
        e.append("P45_OBSERVATION_LEDGER_COUNT_DRIFT")
    if checkpoint:
        if checkpoint.get("controls",{}).get("outcome_reads_at_checkpoint_creation")!=0:
            e.append("P45_CHECKPOINT_OUTCOME_LEAK")
        parallel=checkpoint.get("parallel_outputs",{})
        if parallel.get("model_specific_evidence_fetch_count")!=0:
            e.append("P45_MODEL_SPECIFIC_FETCH")
        if parallel.get("later_evidence_backfill_count")!=0:
            e.append("P45_LATER_BACKFILL")
        if parallel.get("legacy",{}).get("ordinalization_count")!=0:
            e.append("P45_LEGACY_ORDINALIZATION")
        if parallel.get("r2",{}).get("model_version")!="R2.0.1_RESEARCH":
            e.append("P45_R2_VERSION")
    if receipt.get("orders")!=0 or receipt.get("trade_authority")!="NONE":
        e.append("P45_RECEIPT_AUTHORITY")
    return sorted(set(e))


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,choices=["baseline","collect"])
    p.add_argument("--d2-current",required=True)
    p.add_argument("--d2-domain",required=True)
    p.add_argument("--recommendation-current",required=True)
    p.add_argument("--recommendation-domain",required=True)
    p.add_argument("--trigger-current",required=True)
    p.add_argument("--shadow-current",required=True)
    p.add_argument("--operating-index",required=True)
    p.add_argument("--d2-source-commit",required=True)
    p.add_argument("--repo-root",default=".")
    p.add_argument("--baseline")
    p.add_argument("--forward-current")
    p.add_argument("--observation-ledger")
    p.add_argument("--r2-runtime-root")
    p.add_argument("--output-dir",default=".p4_5_output")
    p.add_argument("--now")
    args=p.parse_args()
    now=datetime.fromisoformat(args.now.replace("Z","+00:00")) if args.now else None
    outputs=build(
        mode=args.mode,
        d2_path=Path(args.d2_current),
        d2_domain_path=Path(args.d2_domain),
        recommendation_path=Path(args.recommendation_current),
        recommendation_domain_path=Path(args.recommendation_domain),
        trigger_path=Path(args.trigger_current),
        shadow_path=Path(args.shadow_current),
        index_path=Path(args.operating_index),
        d2_source_commit=args.d2_source_commit,
        repo_root=Path(args.repo_root).resolve(),
        baseline_path=Path(args.baseline) if args.baseline else None,
        forward_current_path=Path(args.forward_current) if args.forward_current else None,
        observation_ledger_path=Path(args.observation_ledger) if args.observation_ledger else None,
        r2_runtime_root=Path(args.r2_runtime_root) if args.r2_runtime_root else None,
        now=now,
    )
    errors=validate_outputs(*outputs)
    if errors:
        raise SystemExit(";".join(errors))
    baseline,current,ledger,checkpoint,receipt=outputs
    out=Path(args.output_dir)
    if baseline is not None:
        write_json(out/"FORWARD_BASELINE_CANDIDATE.json",baseline)
    write_json(out/"FORWARD_VALIDATION_CURRENT.json",current)
    write_jsonl(out/"FORWARD_OBSERVATION_LEDGER.jsonl",ledger)
    if checkpoint is not None:
        write_json(out/"checkpoint_candidate.json",checkpoint)
    write_json(out/"cycle_receipt.json",receipt)
    print(json.dumps({
        "mode":args.mode,
        "status":current["status"],
        "accepted_checkpoints":current["accepted_checkpoint_count"],
        "observations":current["phase4_forward_observation_count"],
        "outcome_reads":current["phase4_realized_outcome_read_count"],
        "phase5":current["phase5_migration_allowed"],
        "orders":0,
        "trade_authority":"NONE",
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
