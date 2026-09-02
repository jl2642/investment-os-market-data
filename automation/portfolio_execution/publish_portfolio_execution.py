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

DOMAIN = "PORTFOLIO_EXECUTION_SIMULATION"
TRADE_AUTHORITY = "NONE"
TARGET_ROOT = Path(ROOT_DIR) / "portfolio_execution"
AI_ROOT = Path(ROOT_DIR) / "ai_autonomous"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def verify_source_branch(branch: str, commit: str) -> None:
    remote = remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("PHASE3_SOURCE_BRANCH_NOT_REMOTE")
    if remote != commit:
        raise RuntimeError(f"PHASE3_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def make_receipt(
    *,
    status: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    phase3_id: str,
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
            "PASS_PORTFOLIO_EXECUTION_AND_AI_SIMULATION"
            if status == "PASS"
            else "NO_OP_SAME_PHASE3_ID"
        ),
        advance_current=status == "PASS",
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"phase3_id={phase3_id}; ai_book=AI_AUTONOMOUS_1M",
    )


def write_current(
    *,
    phase3_text: str,
    ai_text: str,
    brief_text: str,
    phase3_id: str,
    receipt: SimpleNamespace,
) -> tuple[bool, str]:
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    AI_ROOT.mkdir(parents=True, exist_ok=True)

    current_path = TARGET_ROOT / "PORTFOLIO_EXECUTION_CURRENT.json"
    existing_id = None
    if current_path.exists():
        try:
            existing_id = json.loads(current_path.read_text(encoding="utf-8")).get("phase3_id")
        except Exception:
            existing_id = None

    if receipt.status == "PASS":
        current_path.write_text(phase3_text, encoding="utf-8")
        (TARGET_ROOT / "PORTFOLIO_EXECUTION_BRIEF_CURRENT.md").write_text(
            brief_text, encoding="utf-8"
        )
        (AI_ROOT / "AI_AUTONOMOUS_1M_CURRENT.json").write_text(
            ai_text, encoding="utf-8"
        )
    elif existing_id != phase3_id:
        raise RuntimeError("PHASE3_NO_OP_ID_MISMATCH")

    published_at = utc_now()
    op_receipt = receipt_payload(receipt, published_at)
    domain_dir = Path(ROOT_DIR) / "runs" / DOMAIN
    domain_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = (
        f"{receipt.source_run_id}-a{receipt.source_run_attempt}-"
        f"{receipt.status.lower()}.json"
    )
    (domain_dir / receipt_name).write_text(
        json.dumps(op_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    pointer_path = Path(ROOT_DIR) / "domains" / f"{DOMAIN}.json"
    prior = (
        json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer_path.exists()
        else None
    )
    advance, reason = can_advance(prior, op_receipt)
    if receipt.status == "PASS" and not advance:
        raise RuntimeError(f"PHASE3_POINTER_NOT_ADVANCED:{reason}")
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
    phase3 = load_json(Path(args.phase3_json))
    ai_state = load_json(Path(args.ai_state_json))
    if phase3.get("status") != "PASS_PORTFOLIO_EXECUTION_AND_AI_SIMULATION":
        raise RuntimeError("PHASE3_NOT_PASS")
    if phase3.get("orders") != 0 or phase3.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("PHASE3_AUTHORITY_VIOLATION")
    if ai_state.get("book_id") != "AI_AUTONOMOUS_1M":
        raise RuntimeError("PHASE3_AI_BOOK_ID_INVALID")
    if ai_state.get("orders") != 0 or ai_state.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("PHASE3_AI_AUTHORITY_VIOLATION")

    phase3_id = str(phase3["phase3_id"])
    watermark = str(phase3["as_of_date"])
    phase3_text = load_text(Path(args.phase3_json))
    ai_text = load_text(Path(args.ai_state_json))
    brief_text = load_text(Path(args.brief))

    run("git", "reset", "--hard", "HEAD", check=False)
    run("git", "clean", "-fd", check=False)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    last_error = ""
    for attempt in range(1, 5):
        try:
            checkout_operating_branch()
            existing = TARGET_ROOT / "PORTFOLIO_EXECUTION_CURRENT.json"
            existing_id = None
            if existing.exists():
                try:
                    existing_id = json.loads(existing.read_text(encoding="utf-8")).get("phase3_id")
                except Exception:
                    existing_id = None
            status = "NO_OP" if existing_id == phase3_id else "PASS"
            receipt = make_receipt(
                status=status,
                source_workflow=args.source_workflow,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
                source_branch=args.source_branch,
                source_commit=args.source_commit,
                watermark=watermark,
                phase3_id=phase3_id,
            )
            advance, reason = write_current(
                phase3_text=phase3_text,
                ai_text=ai_text,
                brief_text=brief_text,
                phase3_id=phase3_id,
                receipt=receipt,
            )
            run("git", "add", "--", ROOT_DIR)
            if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
                return {"status": "NO_CHANGE", "advanced": advance, "reason": reason, "phase3_id": phase3_id}
            run("git", "commit", "-m", f"operating-current: Phase 3 portfolio execution {status.lower()} {phase3_id[-16:]}")
            pushed = run("git", "push", "origin", "HEAD:refs/heads/operating-current", check=False)
            if pushed.returncode == 0:
                return {
                    "status": "PUBLISHED",
                    "advanced": advance,
                    "reason": reason,
                    "phase3_id": phase3_id,
                    "operating_commit": run("git", "rev-parse", "HEAD").stdout.strip(),
                }
            last_error = pushed.stderr.strip()
            time.sleep(attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"PHASE3_PUBLISH_FAILED:{last_error}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase3-json", required=True)
    p.add_argument("--ai-state-json", required=True)
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
