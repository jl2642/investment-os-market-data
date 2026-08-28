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

TRADE_AUTHORITY = "NONE"
DOMAIN = "OPPORTUNITY_FUNNEL"
TARGET_ROOT = Path(ROOT_DIR) / "opportunity_funnel"
ADVANCE_ACTION = "ADVANCE_NEW_SOURCE_FINGERPRINT"
NO_OP_ACTION = "NO_OP_SAME_SOURCE_FINGERPRINT"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def verify_source_branch(branch: str, commit: str) -> None:
    remote = remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("P42_SOURCE_BRANCH_NOT_REMOTE")
    if remote != commit:
        raise RuntimeError(f"P42_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def make_receipt_args(
    *,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    cycle_fingerprint: str,
    cycle_action: str,
) -> SimpleNamespace:
    if cycle_action == ADVANCE_ACTION:
        status = "PASS"
        advance_current = True
    elif cycle_action == NO_OP_ACTION:
        status = "NO_OP"
        advance_current = False
    else:
        raise RuntimeError(f"P42_UNKNOWN_CYCLE_ACTION:{cycle_action}")
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
        qc_status="PASS_P4_2_FUNNEL_VALIDATED" if status == "PASS" else "NO_OP_SAME_SOURCE_FINGERPRINT",
        advance_current=advance_current,
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"P4-2 cycle_fingerprint={cycle_fingerprint}; cycle_action={cycle_action}",
    )


def write_operating_transaction(
    *,
    current_text: str,
    near_miss_text: str,
    work_queue_text: str,
    cycle_text: str,
    receipt_args: SimpleNamespace,
) -> tuple[bool, str]:
    current = json.loads(current_text)
    cycle = json.loads(cycle_text)
    fingerprint = str(current["cycle_fingerprint"])
    cycle_action = str(current["cycle_action"])
    if cycle.get("cycle_fingerprint") != fingerprint:
        raise RuntimeError("P42_CYCLE_FINGERPRINT_MISMATCH")
    if cycle.get("cycle_action") != cycle_action:
        raise RuntimeError("P42_CYCLE_ACTION_MISMATCH")

    if cycle_action == ADVANCE_ACTION:
        TARGET_ROOT.mkdir(parents=True, exist_ok=True)
        (TARGET_ROOT / "cycles").mkdir(parents=True, exist_ok=True)
        (TARGET_ROOT / "OPPORTUNITY_FUNNEL_CURRENT.json").write_text(current_text, encoding="utf-8")
        (TARGET_ROOT / "OPPORTUNITY_NEAR_MISS_CURRENT.json").write_text(near_miss_text, encoding="utf-8")
        (TARGET_ROOT / "D1_WORK_QUEUE_CURRENT.json").write_text(work_queue_text, encoding="utf-8")
        (TARGET_ROOT / "cycles" / f"{fingerprint}.json").write_text(cycle_text, encoding="utf-8")
    elif cycle_action == NO_OP_ACTION:
        existing = TARGET_ROOT / "OPPORTUNITY_FUNNEL_CURRENT.json"
        if not existing.exists():
            raise RuntimeError("P42_NO_OP_WITHOUT_EXISTING_CURRENT")
        existing_payload = json.loads(existing.read_text(encoding="utf-8"))
        if existing_payload.get("cycle_fingerprint") != fingerprint:
            raise RuntimeError("P42_NO_OP_FINGERPRINT_NOT_CURRENT")
    else:
        raise RuntimeError(f"P42_UNKNOWN_CYCLE_ACTION:{cycle_action}")

    published_at = utc_now()
    operating_receipt = receipt_payload(receipt_args, published_at)
    domain_dir = Path(ROOT_DIR) / "runs" / DOMAIN
    domain_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = (
        f"{receipt_args.source_run_id}-a{receipt_args.source_run_attempt}-"
        f"{receipt_args.status.lower()}.json"
    )
    (domain_dir / receipt_name).write_text(
        json.dumps(operating_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    pointer_path = Path(ROOT_DIR) / "domains" / f"{DOMAIN}.json"
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    prior = json.loads(pointer_path.read_text(encoding="utf-8")) if pointer_path.exists() else None
    advance, reason = can_advance(prior, operating_receipt)

    if cycle_action == ADVANCE_ACTION and not advance:
        raise RuntimeError(f"P42_OPERATING_POINTER_NOT_ADVANCED:{reason}")
    if cycle_action == NO_OP_ACTION and advance:
        raise RuntimeError("P42_NO_OP_UNEXPECTEDLY_ADVANCED")

    if advance:
        pointer_path.write_text(
            json.dumps(pointer_payload(operating_receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    index = build_index(Path(ROOT_DIR))
    (Path(ROOT_DIR) / "OPERATING_CURRENT_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return advance, reason


def publish(args: argparse.Namespace) -> dict[str, Any]:
    current_path = Path(args.current)
    near_miss_path = Path(args.near_miss)
    work_queue_path = Path(args.work_queue)
    cycle_path = Path(args.cycle_receipt)
    current = load_json(current_path)
    cycle_fingerprint = str(current.get("cycle_fingerprint") or "")
    cycle_action = str(current.get("cycle_action") or "")
    if not cycle_fingerprint:
        raise RuntimeError("P42_MISSING_CYCLE_FINGERPRINT")
    if cycle_action not in {ADVANCE_ACTION, NO_OP_ACTION}:
        raise RuntimeError("P42_INVALID_CYCLE_ACTION")
    if current.get("controls", {}).get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("P42_TRADE_AUTHORITY_NOT_NONE")
    if any(int(current.get("controls", {}).get(key, 0)) != 0 for key in (
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "orders",
    )):
        raise RuntimeError("P42_PROTECTED_MUTATION_NONZERO")

    source_commit = args.source_commit
    verify_source_branch(args.source_branch, source_commit)

    current_text = load_text(current_path)
    near_miss_text = load_text(near_miss_path)
    work_queue_text = load_text(work_queue_path)
    cycle_text = load_text(cycle_path)
    watermark = str(current.get("generated_at_utc") or utc_now())

    receipt_args = make_receipt_args(
        source_workflow=args.source_workflow,
        source_run_id=args.source_run_id,
        source_run_attempt=args.source_run_attempt,
        source_branch=args.source_branch,
        source_commit=source_commit,
        watermark=watermark,
        cycle_fingerprint=cycle_fingerprint,
        cycle_action=cycle_action,
    )

    # Generated payloads are held in memory before switching branches.
    run("git", "reset", "--hard", "HEAD", check=False)
    run("git", "clean", "-fd", check=False)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    last_error = ""
    for attempt in range(1, 5):
        try:
            checkout_operating_branch()
            advance, reason = write_operating_transaction(
                current_text=current_text,
                near_miss_text=near_miss_text,
                work_queue_text=work_queue_text,
                cycle_text=cycle_text,
                receipt_args=receipt_args,
            )
            run("git", "add", "--", ROOT_DIR)
            if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
                return {
                    "status": "NO_CHANGE",
                    "advanced": advance,
                    "reason": reason,
                    "cycle_action": cycle_action,
                    "cycle_fingerprint": cycle_fingerprint,
                }
            run(
                "git",
                "commit",
                "-m",
                f"operating-current: P4-2 {receipt_args.status.lower()} {cycle_fingerprint[:12]}",
            )
            pushed = run("git", "push", "origin", "HEAD:refs/heads/operating-current", check=False)
            if pushed.returncode == 0:
                return {
                    "status": "PUBLISHED",
                    "advanced": advance,
                    "reason": reason,
                    "cycle_action": cycle_action,
                    "cycle_fingerprint": cycle_fingerprint,
                    "operating_commit": run("git", "rev-parse", "HEAD").stdout.strip(),
                    "source_commit": source_commit,
                }
            last_error = pushed.stderr.strip()
            run("git", "reset", "--hard", "HEAD", check=False)
            time.sleep(attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"P42_FUNNEL_PUBLISH_FAILED:{last_error}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True)
    p.add_argument("--near-miss", required=True)
    p.add_argument("--work-queue", required=True)
    p.add_argument("--cycle-receipt", required=True)
    p.add_argument("--source-workflow", required=True)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--source-run-attempt", required=True, type=int)
    p.add_argument("--source-branch", required=True)
    p.add_argument("--source-commit", required=True)
    return p


def main() -> None:
    args = parser().parse_args()
    print(json.dumps(publish(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
