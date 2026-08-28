from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPERATING_BRANCH = "operating-current"
ROOT_DIR = "operating_current"
VALID_STATUS = {"PASS", "FAIL", "BLOCKED", "NO_OP"}
DOMAIN_RE = re.compile(r"^[A-Z0-9_]+$")
DOMAIN_STALE_DAYS = {
    "A_SHARE_FULL_MARKET": 5,
    "PORTFOLIO_MARKS": 5,
    "CANDIDATE_WEEKLY_OBSERVATION": 10,
    "RESEARCH_D2": 10,
    "CROSS_MARKET_LIMITED": 5,
}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_args(args: argparse.Namespace) -> None:
    if args.status not in VALID_STATUS:
        raise ValueError("INVALID_STATUS")
    if not DOMAIN_RE.fullmatch(args.domain):
        raise ValueError("INVALID_DOMAIN")
    if args.advance_current and args.status != "PASS":
        raise ValueError("ONLY_PASS_MAY_ADVANCE_CURRENT")
    if args.status == "PASS" and not args.watermark_sort_key:
        raise ValueError("PASS_REQUIRES_WATERMARK_SORT_KEY")
    for value in (
        args.real_account_mutations,
        args.simulation_mutations,
        args.candidate_membership_mutations,
        args.orders,
    ):
        if value != 0:
            raise ValueError("PROTECTED_MUTATION_NONZERO")
    if args.trade_authority != "NONE":
        raise ValueError("TRADE_AUTHORITY_NOT_NONE")


def receipt_payload(args: argparse.Namespace, published_at: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "domain_id": args.domain,
        "status": args.status,
        "source_workflow": args.source_workflow,
        "source_run_id": str(args.source_run_id),
        "source_run_attempt": int(args.source_run_attempt),
        "source_branch": args.source_branch,
        "source_commit_sha": args.source_commit,
        "published_at_utc": published_at,
        "data_watermark": args.watermark,
        "watermark_sort_key": args.watermark_sort_key,
        "qc_status": args.qc_status,
        "fail_closed": True,
        "advance_current_requested": bool(args.advance_current),
        "protected_mutations": {
            "real_account": int(args.real_account_mutations),
            "simulation": int(args.simulation_mutations),
            "candidate_membership": int(args.candidate_membership_mutations),
        },
        "orders": int(args.orders),
        "trade_authority": args.trade_authority,
        "note": args.note or None,
    }


def pointer_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "schema_version","domain_id","status","source_workflow","source_run_id",
        "source_run_attempt","source_branch","source_commit_sha","published_at_utc",
        "data_watermark","watermark_sort_key","qc_status","fail_closed",
        "protected_mutations","orders","trade_authority"
    ]
    return {key: receipt[key] for key in keys}


def can_advance(current: dict[str, Any] | None, new_receipt: dict[str, Any]) -> tuple[bool, str]:
    if new_receipt["status"] != "PASS":
        return False, "NON_PASS_DOES_NOT_ADVANCE"
    if not new_receipt["advance_current_requested"]:
        return False, "ADVANCE_NOT_REQUESTED"
    if current is None:
        return True, "FIRST_CURRENT"
    old_key = str(current.get("watermark_sort_key") or "")
    new_key = str(new_receipt.get("watermark_sort_key") or "")
    if not new_key:
        return False, "MISSING_SORT_KEY"
    if old_key and new_key < old_key:
        return False, "WATERMARK_REGRESSION"
    return True, "PASS_NONREGRESSING"


def latest_receipt_for_domain(receipt_paths: list[Path]) -> dict[str, Any] | None:
    rows=[]
    for path in receipt_paths:
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not rows:
        return None
    return max(rows, key=lambda row: (str(row.get("published_at_utc","")), str(row.get("source_run_id","")), int(row.get("source_run_attempt",0))))


def _watermark_age_days(value: str, now: datetime) -> int | None:
    if not value:
        return None
    try:
        normalized=value.replace("Z","+00:00")
        if len(normalized) == 10:
            dt=datetime.fromisoformat(normalized).replace(tzinfo=timezone.utc)
        else:
            dt=datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=timezone.utc)
            dt=dt.astimezone(timezone.utc)
        return max(0, (now.date()-dt.date()).days)
    except Exception:
        return None


def build_index(root: Path) -> dict[str, Any]:
    domains_dir = root / "domains"
    runs_dir = root / "runs"
    entries=[]
    domain_ids=set(DOMAIN_STALE_DAYS)
    if domains_dir.exists():
        domain_ids.update(path.stem for path in domains_dir.glob("*.json"))
    if runs_dir.exists():
        domain_ids.update(path.name for path in runs_dir.iterdir() if path.is_dir())
    now=datetime.now(timezone.utc)
    for domain in sorted(domain_ids):
        pointer_path=domains_dir / f"{domain}.json"
        current=json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
        receipt_paths=list((runs_dir/domain).glob("*.json")) if (runs_dir/domain).exists() else []
        latest=latest_receipt_for_domain(receipt_paths)
        age=_watermark_age_days(str(current.get("watermark_sort_key","")),now) if current else None
        threshold=DOMAIN_STALE_DAYS.get(domain)
        if current is None:
            health="MISSING_CURRENT"
        elif latest and latest.get("status") in {"FAIL","BLOCKED"}:
            health="LATEST_ATTEMPT_FAILED_CURRENT_PRESERVED"
        elif age is not None and threshold is not None and age > threshold:
            health="STALE_BY_CALENDAR_HEURISTIC"
        else:
            health="CURRENT"
        entries.append({
            "domain_id": domain,
            "current": current,
            "latest_attempt": latest,
            "watermark_age_calendar_days": age,
            "stale_threshold_calendar_days": threshold,
            "health": health,
        })
    return {
        "schema_version":"1.0.0",
        "generated_at_utc":utc_now(),
        "authority":"OPERATING_CURRENT_BRANCH_POINTER_SURFACE",
        "staleness_basis":"CALENDAR_DAY_HEURISTIC_NOT_EXCHANGE_SESSION_TRUTH",
        "domains":entries,
        "orders":0,
        "trade_authority":"NONE",
    }


def remote_branch_sha(branch: str) -> str | None:
    cp=run("git","ls-remote","--heads","origin",f"refs/heads/{branch}",check=False)
    if cp.returncode != 0 or not cp.stdout.strip():
        return None
    return cp.stdout.split()[0]


def verify_source_remote(args: argparse.Namespace) -> None:
    if not args.advance_current:
        return
    remote_sha=remote_branch_sha(args.source_branch)
    if remote_sha is None:
        raise RuntimeError("SOURCE_BRANCH_NOT_REMOTE")
    if remote_sha != args.source_commit:
        raise RuntimeError(f"SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote_sha}:{args.source_commit}")


def checkout_operating_branch() -> tuple[str | None, str]:
    run("git","fetch","origin","main","--no-tags")
    remote_op=remote_branch_sha(OPERATING_BRANCH)
    if remote_op:
        run("git","fetch","origin",f"{OPERATING_BRANCH}:refs/remotes/origin/{OPERATING_BRANCH}","--no-tags")
        run("git","checkout","-B",OPERATING_BRANCH,f"refs/remotes/origin/{OPERATING_BRANCH}")
        reb=run("git","rebase","origin/main",check=False)
        if reb.returncode != 0:
            run("git","rebase","--abort",check=False)
            raise RuntimeError("OPERATING_CURRENT_REBASE_FAILED")
    else:
        run("git","checkout","-B",OPERATING_BRANCH,"origin/main")
    return remote_op, run("git","rev-parse","HEAD").stdout.strip()


def write_attempt(args: argparse.Namespace) -> tuple[dict[str, Any], bool, str]:
    published_at=utc_now()
    receipt=receipt_payload(args,published_at)
    root=Path(ROOT_DIR)
    domain_dir=root/"runs"/args.domain
    domain_dir.mkdir(parents=True,exist_ok=True)
    receipt_name=f"{args.source_run_id}-a{args.source_run_attempt}-{args.status.lower()}.json"
    (domain_dir/receipt_name).write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    pointer_path=root/"domains"/f"{args.domain}.json"
    pointer_path.parent.mkdir(parents=True,exist_ok=True)
    current=json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
    advance,reason=can_advance(current,receipt)
    if args.advance_current and args.status=="PASS" and reason=="WATERMARK_REGRESSION":
        raise RuntimeError("WATERMARK_REGRESSION")
    if advance:
        pointer_path.write_text(json.dumps(pointer_payload(receipt),ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    index=build_index(root)
    (root/"OPERATING_CURRENT_INDEX.json").write_text(json.dumps(index,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return receipt,advance,reason


def publish(args: argparse.Namespace) -> dict[str, Any]:
    validate_args(args)
    verify_source_remote(args)
    # Metadata has already been captured in args. Discard unrelated generated
    # worktree changes before switching to the rebuildable operating branch.
    run("git","reset","--hard","HEAD",check=False)
    run("git","clean","-fd",check=False)
    run("git","config","user.name","github-actions[bot]")
    run("git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com")

    last_error=None
    for attempt in range(1,5):
        try:
            remote_before,_=checkout_operating_branch()
            receipt,advanced,reason=write_attempt(args)
            run("git","add","--",ROOT_DIR)
            if run("git","diff","--cached","--quiet",check=False).returncode == 0:
                return {"status":"NO_CHANGE","advanced":advanced,"reason":reason}
            run("git","commit","-m",f"operating-current: {args.domain} {args.status} run {args.source_run_id}")
            push=run("git","push","origin",f"HEAD:refs/heads/{OPERATING_BRANCH}",check=False)
            if push.returncode == 0:
                return {
                    "status":"PUBLISHED",
                    "advanced":advanced,
                    "reason":reason,
                    "operating_commit":run("git","rev-parse","HEAD").stdout.strip(),
                    "source_commit":args.source_commit,
                }
            last_error=push.stderr.strip()
            run("git","reset","--hard","HEAD",check=False)
            time.sleep(attempt)
        except Exception as exc:
            last_error=str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"OPERATING_CURRENT_PUBLISH_FAILED:{last_error}")


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser()
    p.add_argument("--domain",required=True)
    p.add_argument("--status",required=True,choices=sorted(VALID_STATUS))
    p.add_argument("--source-workflow",required=True)
    p.add_argument("--source-run-id",required=True)
    p.add_argument("--source-run-attempt",required=True,type=int)
    p.add_argument("--source-branch",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--watermark",default="")
    p.add_argument("--watermark-sort-key",default="")
    p.add_argument("--qc-status",default="UNKNOWN")
    p.add_argument("--advance-current",action="store_true")
    p.add_argument("--real-account-mutations",type=int,default=0)
    p.add_argument("--simulation-mutations",type=int,default=0)
    p.add_argument("--candidate-membership-mutations",type=int,default=0)
    p.add_argument("--orders",type=int,default=0)
    p.add_argument("--trade-authority",default="NONE")
    p.add_argument("--note",default="")
    return p


def main() -> None:
    args=parser().parse_args()
    result=publish(args)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
