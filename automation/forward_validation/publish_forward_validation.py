from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from automation.operating_current.publish_operating_current import (
    ROOT_DIR,
    build_index,
    can_advance,
    checkout_operating_branch,
    pointer_payload,
    receipt_payload,
    remote_branch_sha,
    run,
    utc_now,
)

DOMAIN="FORWARD_VALIDATION"
TRADE_AUTHORITY="NONE"
TARGET=Path(ROOT_DIR)/"forward_validation"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str,Any]:
    return json.loads(load_text(path))


def verify_source(branch: str, commit: str) -> None:
    remote=remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("P45_SOURCE_BRANCH_NOT_REMOTE")
    if remote!=commit:
        raise RuntimeError(f"P45_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def materialize_baseline(
    baseline_candidate: dict[str,Any],
    current_candidate: dict[str,Any],
    *,
    published_at: str,
    source_commit: str,
) -> tuple[dict[str,Any],dict[str,Any]]:
    if baseline_candidate.get("eligibility_cutoff_utc") is not None:
        raise RuntimeError("P45_BASELINE_CANDIDATE_ALREADY_HAS_CUTOFF")
    if current_candidate.get("phase4_forward_observation_count")!=0:
        raise RuntimeError("P45_BASELINE_OBSERVATION_NONZERO")
    if current_candidate.get("phase4_realized_outcome_read_count")!=0:
        raise RuntimeError("P45_BASELINE_OUTCOME_NONZERO")
    baseline=deepcopy(baseline_candidate)
    current=deepcopy(current_candidate)
    baseline["status"]="CLEAN_BASELINE_ACCEPTED"
    baseline["eligibility_cutoff_utc"]=published_at
    baseline["accepted_at_utc"]=published_at
    baseline["cutoff_authority"]="FORWARD_VALIDATION_OPERATING_CURRENT_BASELINE_RECEIPT_PUBLISHED_AT_UTC"
    baseline["protected_main_sha_at_acceptance"]=source_commit
    baseline["phase4_effective_forward_observation_start_allowed"]=True
    current["status"]="ACTIVE_FORWARD_ACCUMULATION"
    current["eligibility_cutoff_utc"]=published_at
    current["clean_baseline_accepted"]=True
    current["phase4_effective_forward_observation_start_allowed"]=True
    current["completion_outcome"]="CONTINUE_P4_5_FORWARD_ACCUMULATION"
    current["phase5_migration_allowed"]=False
    return baseline,current


def make_receipt_args(
    *,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    status: str,
    advance: bool,
    note: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        domain=DOMAIN,
        status=status,
        source_workflow=source_workflow,
        source_run_id=str(source_run_id),
        source_run_attempt=int(source_run_attempt),
        source_branch=source_branch,
        source_commit=source_commit,
        watermark=watermark,
        watermark_sort_key=watermark,
        qc_status=(
            "PASS_P4_5_CLEAN_BASELINE_ACCEPTED"
            if status=="PASS" and "baseline" in note.lower()
            else "PASS_P4_5_FORWARD_CHECKPOINT_ACCEPTED"
            if status=="PASS"
            else "NO_OP_NO_NEW_ELIGIBLE_FORWARD_CHECKPOINT"
        ),
        advance_current=advance,
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=note,
    )


def write_domain_receipt(args: SimpleNamespace, published_at: str) -> tuple[bool,str]:
    receipt=receipt_payload(args,published_at)
    run_dir=Path(ROOT_DIR)/"runs"/DOMAIN
    run_dir.mkdir(parents=True,exist_ok=True)
    filename=f"{args.source_run_id}-a{args.source_run_attempt}-{args.status.lower()}.json"
    (run_dir/filename).write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    pointer_path=Path(ROOT_DIR)/"domains"/f"{DOMAIN}.json"
    pointer_path.parent.mkdir(parents=True,exist_ok=True)
    prior=json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
    advance,reason=can_advance(prior,receipt)
    if args.advance_current and not advance:
        raise RuntimeError(f"P45_DOMAIN_POINTER_NOT_ADVANCED:{reason}")
    if not args.advance_current and advance:
        raise RuntimeError("P45_NO_OP_UNEXPECTED_POINTER_ADVANCE")
    if advance:
        pointer_path.write_text(
            json.dumps(pointer_payload(receipt),ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
    return advance,reason


def checkpoint_immutable_projection(cp: dict[str,Any]) -> dict[str,Any]:
    keys=[
        "schema_version","checkpoint_id","checkpoint_available_at_utc","trigger_event",
        "global_forward_evidence_state_fingerprint","evidence_regime_id","shared_packet",
        "parallel_outputs","audit_context","evaluation_eligibility","controls",
    ]
    return {k:cp.get(k) for k in keys}


def write_transaction(
    *,
    baseline_candidate_text: str | None,
    current_text: str,
    ledger_text: str,
    checkpoint_texts: list[str],
    cycle_text: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
) -> dict[str,Any]:
    current_candidate=json.loads(current_text)
    cycle=json.loads(cycle_text)
    mode=str(cycle.get("mode"))
    cycle_action=str(cycle.get("cycle_action"))
    published_at=utc_now()
    TARGET.mkdir(parents=True,exist_ok=True)
    (TARGET/"checkpoints").mkdir(parents=True,exist_ok=True)
    baseline_path=TARGET/"FORWARD_BASELINE_CURRENT.json"
    current_path=TARGET/"FORWARD_VALIDATION_CURRENT.json"
    ledger_path=TARGET/"FORWARD_OBSERVATION_LEDGER.jsonl"

    if mode=="BASELINE":
        if baseline_path.exists():
            raise RuntimeError("P45_BASELINE_ALREADY_PUBLISHED")
        if baseline_candidate_text is None:
            raise RuntimeError("P45_BASELINE_CANDIDATE_REQUIRED")
        baseline_candidate=json.loads(baseline_candidate_text)
        baseline,current=materialize_baseline(
            baseline_candidate,current_candidate,published_at=published_at,source_commit=source_commit
        )
        if published_at <= "2026-08-27T13:42:29Z":
            raise RuntimeError("P45_CUTOFF_NOT_AFTER_SUPERSEDED_V1")
        baseline_path.write_text(
            json.dumps(baseline,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        current_path.write_text(
            json.dumps(current,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        ledger_path.write_text(ledger_text,encoding="utf-8")
        cycle_record={
            **cycle,
            "accepted_at_utc":published_at,
            "eligibility_cutoff_utc":published_at,
            "status":"CLEAN_BASELINE_ACCEPTED",
        }
        cycle_id="baseline-"+published_at.replace(":","").replace("-","")
        (TARGET/"checkpoints"/f"{cycle_id}.json").write_text(
            json.dumps(cycle_record,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        receipt_args=make_receipt_args(
            source_workflow=source_workflow,
            source_run_id=source_run_id,
            source_run_attempt=source_run_attempt,
            source_branch=source_branch,
            source_commit=source_commit,
            watermark=published_at,
            status="PASS",
            advance=True,
            note=f"P4-5 clean baseline cutoff={published_at}; observations=0 outcomes=0 phase5=false",
        )
        advanced,reason=write_domain_receipt(receipt_args,published_at)
        return {
            "status":"BASELINE_PUBLISHED",
            "eligibility_cutoff_utc":published_at,
            "advanced":advanced,
            "reason":reason,
            "observation_count":0,
            "outcome_read_count":0,
        }

    if mode!="COLLECT":
        raise RuntimeError("P45_UNKNOWN_MODE")
    if not baseline_path.exists():
        raise RuntimeError("P45_COLLECT_WITHOUT_BASELINE")
    baseline=json.loads(baseline_path.read_text(encoding="utf-8"))
    if current_candidate.get("eligibility_cutoff_utc")!=baseline.get("eligibility_cutoff_utc"):
        raise RuntimeError("P45_COLLECT_CUTOFF_MISMATCH")

    if cycle_action=="NO_NEW_ELIGIBLE_CHECKPOINT":
        receipt_args=make_receipt_args(
            source_workflow=source_workflow,
            source_run_id=source_run_id,
            source_run_attempt=source_run_attempt,
            source_branch=source_branch,
            source_commit=source_commit,
            watermark=str(baseline["eligibility_cutoff_utc"]),
            status="NO_OP",
            advance=False,
            note="P4-5 no new registered-evidence checkpoint and no newly matured outcome; Current preserved",
        )
        advanced,reason=write_domain_receipt(receipt_args,published_at)
        return {
            "status":"NO_OP",
            "advanced":advanced,
            "reason":reason,
            "eligibility_cutoff_utc":baseline["eligibility_cutoff_utc"],
        }

    if cycle_action!="ADVANCE_FORWARD_STATE":
        raise RuntimeError("P45_UNKNOWN_CYCLE_ACTION")
    checkpoint_ids=[]
    watermarks=[]
    for checkpoint_text in checkpoint_texts:
        checkpoint=json.loads(checkpoint_text)
        checkpoint_id=str(checkpoint["checkpoint_id"])
        checkpoint_path=TARGET/"checkpoints"/f"{checkpoint_id}.json"
        if checkpoint_path.exists():
            prior=json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if checkpoint_immutable_projection(prior)!=checkpoint_immutable_projection(checkpoint):
                raise RuntimeError("P45_IMMUTABLE_CHECKPOINT_DRIFT:"+checkpoint_id)
        checkpoint_path.write_text(
            json.dumps(checkpoint,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        checkpoint_ids.append(checkpoint_id)
        watermarks.append(str(checkpoint["checkpoint_available_at_utc"]))
    current_path.write_text(current_text,encoding="utf-8")
    ledger_path.write_text(ledger_text,encoding="utf-8")
    watermark=max(
        [str(baseline["eligibility_cutoff_utc"])]
        + watermarks
        + [published_at]
    )
    new_count=int(cycle.get("new_checkpoint_count",0))
    outcome_increment=int(cycle.get("outcome_read_increment",0))
    receipt_args=make_receipt_args(
        source_workflow=source_workflow,
        source_run_id=source_run_id,
        source_run_attempt=source_run_attempt,
        source_branch=source_branch,
        source_commit=source_commit,
        watermark=watermark,
        status="PASS",
        advance=True,
        note=(
            f"P4-5 forward state advanced new_checkpoints={new_count} "
            f"new_outcome_reads={outcome_increment}; phase5_execution=false"
        ),
    )
    advanced,reason=write_domain_receipt(receipt_args,published_at)
    return {
        "status":"FORWARD_STATE_PUBLISHED",
        "checkpoint_ids":checkpoint_ids,
        "new_checkpoint_count":new_count,
        "outcome_read_increment":outcome_increment,
        "advanced":advanced,
        "reason":reason,
        "observation_count":current_candidate["phase4_forward_observation_count"],
        "outcome_read_count":current_candidate["phase4_realized_outcome_read_count"],
        "completion_outcome":current_candidate.get("completion_outcome"),
        "phase5_migration_allowed":False,
    }


def publish(args: argparse.Namespace) -> dict[str,Any]:
    current=load_json(Path(args.current))
    cycle=load_json(Path(args.cycle_receipt))
    controls=current.get("controls",{})
    if controls.get("trade_authority")!=TRADE_AUTHORITY:
        raise RuntimeError("P45_TRADE_AUTHORITY_NOT_NONE")
    for key in [
        "candidate_membership_mutations","real_account_mutations","simulation_mutations",
        "target_portfolio_writebacks","user_decisions_generated","orders",
    ]:
        if int(controls.get(key,0))!=0:
            raise RuntimeError(f"P45_PROTECTED_NONZERO:{key}")
    if current.get("phase5_migration_allowed") is not False:
        raise RuntimeError("P45_PHASE5_PREMATURE")

    verify_source(args.source_branch,args.source_commit)
    baseline_text=load_text(Path(args.baseline_candidate)) if args.baseline_candidate else None
    current_text=load_text(Path(args.current))
    ledger_text=load_text(Path(args.observation_ledger))
    checkpoint_texts=[]
    if args.checkpoints_dir:
        checkpoint_texts=[
            load_text(path)
            for path in sorted(Path(args.checkpoints_dir).glob("*.json"))
        ]
    cycle_text=load_text(Path(args.cycle_receipt))

    run("git","reset","--hard","HEAD",check=False)
    run("git","clean","-fd",check=False)
    run("git","config","user.name","github-actions[bot]")
    run("git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com")

    last_error=""
    for attempt in range(1,5):
        try:
            checkout_operating_branch()
            result=write_transaction(
                baseline_candidate_text=baseline_text,
                current_text=current_text,
                ledger_text=ledger_text,
                checkpoint_texts=checkpoint_texts,
                cycle_text=cycle_text,
                source_workflow=args.source_workflow,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
                source_branch=args.source_branch,
                source_commit=args.source_commit,
            )
            index=build_index(Path(ROOT_DIR))
            (Path(ROOT_DIR)/"OPERATING_CURRENT_INDEX.json").write_text(
                json.dumps(index,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                encoding="utf-8",
            )
            run("git","add","--",ROOT_DIR)
            if run("git","diff","--cached","--quiet",check=False).returncode==0:
                return {**result,"publish":"NO_CHANGE"}
            run("git","commit","-m",f"operating-current: P4-5 {result['status'].lower()}")
            pushed=run("git","push","origin","HEAD:refs/heads/operating-current",check=False)
            if pushed.returncode==0:
                return {
                    **result,
                    "publish":"PUBLISHED",
                    "operating_commit":run("git","rev-parse","HEAD").stdout.strip(),
                    "source_commit":args.source_commit,
                }
            last_error=pushed.stderr.strip()
            run("git","reset","--hard","HEAD",check=False)
            time.sleep(attempt)
        except Exception as exc:
            last_error=str(exc)
            time.sleep(attempt)
    raise RuntimeError("P45_PUBLISH_FAILED:"+last_error)


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser()
    p.add_argument("--baseline-candidate")
    p.add_argument("--current",required=True)
    p.add_argument("--observation-ledger",required=True)
    p.add_argument("--checkpoints-dir")
    p.add_argument("--cycle-receipt",required=True)
    p.add_argument("--source-workflow",required=True)
    p.add_argument("--source-run-id",required=True)
    p.add_argument("--source-run-attempt",required=True,type=int)
    p.add_argument("--source-branch",required=True)
    p.add_argument("--source-commit",required=True)
    return p


def main():
    args=parser().parse_args()
    print(json.dumps(publish(args),ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
