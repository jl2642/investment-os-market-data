from __future__ import annotations

import argparse
import json
import time
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

TRADE_AUTHORITY="NONE"
TRIGGER_DOMAIN="TRIGGER_MONITOR"
SHADOW_DOMAIN="SHADOW_BOOK"
TRIGGER_ROOT=Path(ROOT_DIR)/"trigger_monitor"
SHADOW_ROOT=Path(ROOT_DIR)/"shadow_book"
ADVANCE="ADVANCE_NEW_SOURCE_FINGERPRINT"
NO_OP="NO_OP_SAME_SOURCE_FINGERPRINT"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str,Any]:
    return json.loads(load_text(path))


def verify_source(branch: str, commit: str) -> None:
    remote=remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("P44_SOURCE_BRANCH_NOT_REMOTE")
    if remote!=commit:
        raise RuntimeError(f"P44_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def receipt_args(
    *,
    domain: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    fingerprint: str,
    cycle_action: str,
) -> SimpleNamespace:
    if cycle_action==ADVANCE:
        status="PASS"
        advance=True
        qc=f"PASS_P4_4_{domain}_VALIDATED"
    elif cycle_action==NO_OP:
        status="NO_OP"
        advance=False
        qc="NO_OP_SAME_SOURCE_FINGERPRINT"
    else:
        raise RuntimeError(f"P44_UNKNOWN_CYCLE_ACTION:{cycle_action}")
    return SimpleNamespace(
        domain=domain,
        status=status,
        source_workflow=source_workflow,
        source_run_id=str(source_run_id),
        source_run_attempt=int(source_run_attempt),
        source_branch=source_branch,
        source_commit=source_commit,
        watermark=watermark,
        watermark_sort_key=watermark,
        qc_status=qc,
        advance_current=advance,
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"P4-4 source_fingerprint={fingerprint}; cycle_action={cycle_action}; pre_baseline=1",
    )


def write_receipt_and_pointer(args: SimpleNamespace) -> tuple[bool,str]:
    published_at=utc_now()
    receipt=receipt_payload(args,published_at)
    domain_dir=Path(ROOT_DIR)/"runs"/args.domain
    domain_dir.mkdir(parents=True,exist_ok=True)
    name=f"{args.source_run_id}-a{args.source_run_attempt}-{args.status.lower()}.json"
    (domain_dir/name).write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    pointer_path=Path(ROOT_DIR)/"domains"/f"{args.domain}.json"
    pointer_path.parent.mkdir(parents=True,exist_ok=True)
    prior=json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
    advance,reason=can_advance(prior,receipt)
    if args.advance_current and not advance:
        raise RuntimeError(f"P44_POINTER_NOT_ADVANCED:{args.domain}:{reason}")
    if not args.advance_current and advance:
        raise RuntimeError(f"P44_NO_OP_UNEXPECTED_ADVANCE:{args.domain}")
    if advance:
        pointer_path.write_text(
            json.dumps(pointer_payload(receipt),ensure_ascii=False,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
    return advance,reason


def write_transaction(
    *,
    registry_text: str,
    trigger_current_text: str,
    trigger_ledger_text: str,
    shadow_current_text: str,
    action_ledger_text: str,
    mark_request_text: str,
    cycle_text: str,
    trigger_receipt: SimpleNamespace,
    shadow_receipt: SimpleNamespace,
) -> tuple[dict[str,Any],dict[str,Any]]:
    trigger_current=json.loads(trigger_current_text)
    shadow_current=json.loads(shadow_current_text)
    cycle=json.loads(cycle_text)
    fingerprint=str(trigger_current["source_fingerprint"])
    cycle_action=str(trigger_current["cycle_action"])
    if shadow_current.get("source_fingerprint")!=fingerprint:
        raise RuntimeError("P44_SHADOW_FINGERPRINT_MISMATCH")
    if cycle.get("source_fingerprint")!=fingerprint:
        raise RuntimeError("P44_CYCLE_FINGERPRINT_MISMATCH")
    if cycle.get("cycle_action")!=cycle_action:
        raise RuntimeError("P44_CYCLE_ACTION_MISMATCH")
    if trigger_current.get("semantic_hash")!=shadow_current.get("semantic_hash"):
        raise RuntimeError("P44_SEMANTIC_HASH_MISMATCH")
    if cycle.get("semantic_hash")!=trigger_current.get("semantic_hash"):
        raise RuntimeError("P44_RECEIPT_SEMANTIC_HASH_MISMATCH")

    if cycle_action==ADVANCE:
        TRIGGER_ROOT.mkdir(parents=True,exist_ok=True)
        SHADOW_ROOT.mkdir(parents=True,exist_ok=True)
        (SHADOW_ROOT/"cycles").mkdir(parents=True,exist_ok=True)
        (TRIGGER_ROOT/"TRIGGER_REGISTRY_CURRENT.json").write_text(registry_text,encoding="utf-8")
        (TRIGGER_ROOT/"TRIGGER_MONITOR_CURRENT.json").write_text(trigger_current_text,encoding="utf-8")
        (TRIGGER_ROOT/"TRIGGER_EVENT_LEDGER.jsonl").write_text(trigger_ledger_text,encoding="utf-8")
        (SHADOW_ROOT/"SHADOW_BOOK_CURRENT.json").write_text(shadow_current_text,encoding="utf-8")
        (SHADOW_ROOT/"SHADOW_ACTION_LEDGER.jsonl").write_text(action_ledger_text,encoding="utf-8")
        (SHADOW_ROOT/"MARK_REQUEST_CURRENT.json").write_text(mark_request_text,encoding="utf-8")
        (SHADOW_ROOT/"cycles"/f"{fingerprint}.json").write_text(cycle_text,encoding="utf-8")
    elif cycle_action==NO_OP:
        for path in (
            TRIGGER_ROOT/"TRIGGER_MONITOR_CURRENT.json",
            SHADOW_ROOT/"SHADOW_BOOK_CURRENT.json",
        ):
            if not path.exists():
                raise RuntimeError(f"P44_NO_OP_WITHOUT_CURRENT:{path}")
        existing=json.loads((TRIGGER_ROOT/"TRIGGER_MONITOR_CURRENT.json").read_text(encoding="utf-8"))
        if existing.get("source_fingerprint")!=fingerprint:
            raise RuntimeError("P44_NO_OP_FINGERPRINT_NOT_CURRENT")
    else:
        raise RuntimeError(f"P44_UNKNOWN_CYCLE_ACTION:{cycle_action}")

    tadv,treason=write_receipt_and_pointer(trigger_receipt)
    sadv,sreason=write_receipt_and_pointer(shadow_receipt)
    index=build_index(Path(ROOT_DIR))
    (Path(ROOT_DIR)/"OPERATING_CURRENT_INDEX.json").write_text(
        json.dumps(index,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    return (
        {"advanced":tadv,"reason":treason},
        {"advanced":sadv,"reason":sreason},
    )


def publish(args: argparse.Namespace) -> dict[str,Any]:
    trigger_current=load_json(Path(args.trigger_current))
    shadow_current=load_json(Path(args.shadow_current))
    fingerprint=str(trigger_current.get("source_fingerprint") or "")
    cycle_action=str(trigger_current.get("cycle_action") or "")
    if not fingerprint:
        raise RuntimeError("P44_MISSING_FINGERPRINT")
    if cycle_action not in {ADVANCE,NO_OP}:
        raise RuntimeError("P44_INVALID_CYCLE_ACTION")
    if shadow_current.get("source_fingerprint")!=fingerprint:
        raise RuntimeError("P44_SHADOW_SOURCE_MISMATCH")
    for controls in (
        trigger_current.get("controls",{}),
        shadow_current.get("controls",{}),
    ):
        if controls.get("trade_authority")!=TRADE_AUTHORITY:
            raise RuntimeError("P44_TRADE_AUTHORITY_NOT_NONE")
        for key in (
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "phase4_forward_observation_increment",
            "phase4_realized_outcome_increment",
            "orders",
        ):
            if key in controls and int(controls.get(key,0))!=0:
                raise RuntimeError(f"P44_PROTECTED_NONZERO:{key}")

    verify_source(args.source_branch,args.source_commit)
    files={
        "registry":load_text(Path(args.registry)),
        "trigger_current":load_text(Path(args.trigger_current)),
        "trigger_ledger":load_text(Path(args.trigger_ledger)),
        "shadow_current":load_text(Path(args.shadow_current)),
        "action_ledger":load_text(Path(args.action_ledger)),
        "mark_request":load_text(Path(args.mark_request)),
        "cycle":load_text(Path(args.cycle_receipt)),
    }
    watermark=str(trigger_current.get("generated_at_utc") or utc_now())
    common=dict(
        source_workflow=args.source_workflow,
        source_run_id=args.source_run_id,
        source_run_attempt=args.source_run_attempt,
        source_branch=args.source_branch,
        source_commit=args.source_commit,
        watermark=watermark,
        fingerprint=fingerprint,
        cycle_action=cycle_action,
    )
    tr=receipt_args(domain=TRIGGER_DOMAIN,**common)
    sr=receipt_args(domain=SHADOW_DOMAIN,**common)

    run("git","reset","--hard","HEAD",check=False)
    run("git","clean","-fd",check=False)
    run("git","config","user.name","github-actions[bot]")
    run("git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com")

    last_error=""
    for attempt in range(1,5):
        try:
            checkout_operating_branch()
            trigger_result,shadow_result=write_transaction(
                registry_text=files["registry"],
                trigger_current_text=files["trigger_current"],
                trigger_ledger_text=files["trigger_ledger"],
                shadow_current_text=files["shadow_current"],
                action_ledger_text=files["action_ledger"],
                mark_request_text=files["mark_request"],
                cycle_text=files["cycle"],
                trigger_receipt=tr,
                shadow_receipt=sr,
            )
            run("git","add","--",ROOT_DIR)
            if run("git","diff","--cached","--quiet",check=False).returncode==0:
                return {
                    "status":"NO_CHANGE",
                    "source_fingerprint":fingerprint,
                    "cycle_action":cycle_action,
                    "trigger":trigger_result,
                    "shadow":shadow_result,
                }
            run("git","commit","-m",f"operating-current: P4-4 {tr.status.lower()} {fingerprint[:12]}")
            pushed=run("git","push","origin","HEAD:refs/heads/operating-current",check=False)
            if pushed.returncode==0:
                return {
                    "status":"PUBLISHED",
                    "source_fingerprint":fingerprint,
                    "cycle_action":cycle_action,
                    "trigger":trigger_result,
                    "shadow":shadow_result,
                    "operating_commit":run("git","rev-parse","HEAD").stdout.strip(),
                    "source_commit":args.source_commit,
                }
            last_error=pushed.stderr.strip()
            run("git","reset","--hard","HEAD",check=False)
            time.sleep(attempt)
        except Exception as exc:
            last_error=str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"P44_PUBLISH_FAILED:{last_error}")


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--trigger-current",required=True)
    p.add_argument("--trigger-ledger",required=True)
    p.add_argument("--shadow-current",required=True)
    p.add_argument("--action-ledger",required=True)
    p.add_argument("--mark-request",required=True)
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
