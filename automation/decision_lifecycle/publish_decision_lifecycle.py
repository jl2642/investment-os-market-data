from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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

DOMAIN = "DECISION_LIFECYCLE"
TRADE_AUTHORITY = "NONE"
TARGET_ROOT = Path(ROOT_DIR) / "decision_lifecycle"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def verify_source_branch(branch: str, commit: str) -> None:
    remote = remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("LIFECYCLE_SOURCE_BRANCH_NOT_REMOTE")
    if remote != commit:
        raise RuntimeError(f"LIFECYCLE_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def receipt_args(
    *,
    status: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    lifecycle_id: str,
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
        qc_status="PASS_DECISION_LIFECYCLE" if status == "PASS" else "NO_OP_SAME_LIFECYCLE",
        advance_current=status == "PASS",
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"decision_lifecycle={lifecycle_id}",
    )


def write_current(
    *,
    lifecycle_text: str,
    queue_text: str,
    brief_text: str,
    lifecycle_id: str,
    receipt: SimpleNamespace,
) -> tuple[bool, str]:
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    current_path = TARGET_ROOT / "DECISION_LIFECYCLE_CURRENT.json"
    existing_id = None
    if current_path.exists():
        try:
            existing_id = json.loads(current_path.read_text(encoding="utf-8")).get("lifecycle_id")
        except Exception:
            existing_id = None

    if receipt.status == "PASS":
        current_path.write_text(lifecycle_text, encoding="utf-8")
        (TARGET_ROOT / "TRIGGER_REVIEW_QUEUE_CURRENT.json").write_text(queue_text, encoding="utf-8")
        (TARGET_ROOT / "DECISION_LIFECYCLE_BRIEF_CURRENT.md").write_text(brief_text, encoding="utf-8")
    elif existing_id != lifecycle_id:
        raise RuntimeError("LIFECYCLE_NO_OP_ID_MISMATCH")

    published_at = utc_now()
    op_receipt = receipt_payload(receipt, published_at)
    domain_dir = Path(ROOT_DIR) / "runs" / DOMAIN
    domain_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = f"{receipt.source_run_id}-a{receipt.source_run_attempt}-{receipt.status.lower()}.json"
    (domain_dir / receipt_name).write_text(
        json.dumps(op_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    pointer_path = Path(ROOT_DIR) / "domains" / f"{DOMAIN}.json"
    prior = json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
    advance, reason = can_advance(prior, op_receipt)
    if receipt.status == "PASS" and not advance:
        raise RuntimeError(f"LIFECYCLE_POINTER_NOT_ADVANCED:{reason}")
    if advance:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(
            json.dumps(pointer_payload(op_receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    (Path(ROOT_DIR) / "OPERATING_CURRENT_INDEX.json").write_text(
        json.dumps(build_index(Path(ROOT_DIR)), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return advance, reason


def publish(args: argparse.Namespace) -> dict[str, Any]:
    verify_source_branch(args.source_branch, args.source_commit)
    lifecycle = load_json(Path(args.lifecycle_json))
    queue = load_json(Path(args.review_queue_json))
    if lifecycle.get("status") != "PASS_DECISION_LIFECYCLE":
        raise RuntimeError("LIFECYCLE_NOT_PASS")
    if lifecycle.get("orders") != 0 or lifecycle.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("LIFECYCLE_AUTHORITY_VIOLATION")
    if queue.get("orders") != 0 or queue.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("LIFECYCLE_QUEUE_AUTHORITY_VIOLATION")
    lifecycle_id = str(lifecycle["lifecycle_id"])
    watermark = str(lifecycle["as_of_date"])
    lifecycle_text = load_text(Path(args.lifecycle_json))
    queue_text = load_text(Path(args.review_queue_json))
    brief_text = load_text(Path(args.brief))

    run("git", "reset", "--hard", "HEAD", check=False)
    run("git", "clean", "-fd", check=False)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    last_error = ""
    for attempt in range(1, 5):
        try:
            checkout_operating_branch()
            existing = TARGET_ROOT / "DECISION_LIFECYCLE_CURRENT.json"
            existing_id = None
            if existing.exists():
                try:
                    existing_id = json.loads(existing.read_text(encoding="utf-8")).get("lifecycle_id")
                except Exception:
                    existing_id = None
            status = "NO_OP" if existing_id == lifecycle_id else "PASS"
            receipt = receipt_args(
                status=status,
                source_workflow=args.source_workflow,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
                source_branch=args.source_branch,
                source_commit=args.source_commit,
                watermark=watermark,
                lifecycle_id=lifecycle_id,
            )
            advance, reason = write_current(
                lifecycle_text=lifecycle_text,
                queue_text=queue_text,
                brief_text=brief_text,
                lifecycle_id=lifecycle_id,
                receipt=receipt,
            )
            run("git", "add", "--", ROOT_DIR)
            if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
                return {"status": "NO_CHANGE", "advanced": advance, "reason": reason, "lifecycle_id": lifecycle_id}
            run("git", "commit", "-m", f"operating-current: decision lifecycle {status.lower()} {lifecycle_id[-16:]}")
            pushed = run("git", "push", "origin", "HEAD:refs/heads/operating-current", check=False)
            if pushed.returncode == 0:
                return {
                    "status": "PUBLISHED",
                    "advanced": advance,
                    "reason": reason,
                    "lifecycle_id": lifecycle_id,
                    "operating_commit": run("git", "rev-parse", "HEAD").stdout.strip(),
                }
            last_error = pushed.stderr.strip()
            time.sleep(attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"LIFECYCLE_PUBLISH_FAILED:{last_error}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lifecycle-json", required=True)
    p.add_argument("--review-queue-json", required=True)
    p.add_argument("--brief", required=True)
    p.add_argument("--source-workflow", required=True)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--source-run-attempt", required=True, type=int)
    p.add_argument("--source-branch", required=True)
    p.add_argument("--source-commit", required=True)
    args = p.parse_args()
    print(json.dumps(publish(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
