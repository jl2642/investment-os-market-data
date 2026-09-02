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

TRADE_AUTHORITY = "NONE"
TARGET_ROOT = Path(ROOT_DIR) / "investment_pipeline"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def verify_source_branch(branch: str, commit: str) -> None:
    remote = remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("S2_SOURCE_BRANCH_NOT_REMOTE")
    if remote != commit:
        raise RuntimeError(
            f"S2_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}"
        )


def decision_grade_count(comparison: dict[str, Any]) -> int:
    coverage = comparison.get("coverage")
    if not isinstance(coverage, dict):
        return 0
    value = coverage.get("decision_grade_underwriting_count", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def should_preserve_existing_decision(
    incoming_comparison: dict[str, Any],
    existing_comparison: dict[str, Any] | None,
) -> bool:
    if decision_grade_count(incoming_comparison) > 0:
        return False
    if not isinstance(existing_comparison, dict):
        return False
    return decision_grade_count(existing_comparison) > 0


def stage_spec(
    args: argparse.Namespace,
) -> tuple[str, list[tuple[str, Path]], str, str]:
    if args.stage == "opportunity":
        files = [
            ("OPPORTUNITY_CURRENT.json", Path(args.opportunity)),
            ("D1_CURRENT.json", Path(args.d1)),
        ]
        payload = load_json(Path(args.d1))
        return (
            "OPPORTUNITY_RESEARCH",
            files,
            str(payload["state_id"]),
            str(payload["as_of"]),
        )
    if args.stage == "decision":
        files = [
            ("CAPITAL_COMPARISON_CURRENT.json", Path(args.comparison)),
            ("RECOMMENDATION_CURRENT.json", Path(args.recommendation)),
        ]
        payload = load_json(Path(args.recommendation))
        return (
            "INVESTMENT_PIPELINE",
            files,
            str(payload["state_id"]),
            str(payload["generated_at_utc"]),
        )
    raise RuntimeError(f"S2_UNKNOWN_STAGE:{args.stage}")


def receipt_args(
    *,
    domain: str,
    status: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    fingerprint: str,
) -> SimpleNamespace:
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
        qc_status=(
            "PASS_S2_SIMPLIFIED_PIPELINE"
            if status == "PASS"
            else "NO_OP_SAME_STATE_ID"
        ),
        advance_current=status == "PASS",
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"S2 state_id={fingerprint}; stage={domain}",
    )


def write_stage(
    *,
    domain: str,
    files: list[tuple[str, str]],
    fingerprint: str,
    receipt: SimpleNamespace,
) -> tuple[bool, str]:
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    primary_name = (
        "D1_CURRENT.json"
        if domain == "OPPORTUNITY_RESEARCH"
        else "RECOMMENDATION_CURRENT.json"
    )
    existing = TARGET_ROOT / primary_name
    existing_state = None
    if existing.exists():
        try:
            existing_state = json.loads(
                existing.read_text(encoding="utf-8")
            ).get("state_id")
        except Exception:
            existing_state = None

    if receipt.status == "PASS":
        for name, text_value in files:
            (TARGET_ROOT / name).write_text(text_value, encoding="utf-8")
    elif existing_state != fingerprint:
        raise RuntimeError("S2_NO_OP_STATE_NOT_CURRENT")

    published_at = utc_now()
    operating_receipt = receipt_payload(receipt, published_at)
    domain_dir = Path(ROOT_DIR) / "runs" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = (
        f"{receipt.source_run_id}-a{receipt.source_run_attempt}-"
        f"{receipt.status.lower()}.json"
    )
    (domain_dir / receipt_name).write_text(
        json.dumps(
            operating_receipt,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    pointer_path = Path(ROOT_DIR) / "domains" / f"{domain}.json"
    prior = (
        json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer_path.exists()
        else None
    )
    advance, reason = can_advance(prior, operating_receipt)

    if receipt.status == "PASS" and not advance:
        raise RuntimeError(f"S2_POINTER_NOT_ADVANCED:{domain}:{reason}")
    if receipt.status == "NO_OP" and advance:
        raise RuntimeError(f"S2_NO_OP_UNEXPECTED_ADVANCE:{domain}")

    if advance:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(
            json.dumps(
                pointer_payload(operating_receipt),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    index = build_index(Path(ROOT_DIR))
    (Path(ROOT_DIR) / "OPERATING_CURRENT_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return advance, reason


def publish(args: argparse.Namespace) -> dict[str, Any]:
    domain, source_files, fingerprint, watermark = stage_spec(args)
    verify_source_branch(args.source_branch, args.source_commit)
    file_texts = [(name, load_text(path)) for name, path in source_files]

    run("git", "reset", "--hard", "HEAD", check=False)
    run("git", "clean", "-fd", check=False)
    run("git", "config", "user.name", "github-actions[bot]")
    run(
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )

    last_error = ""
    for attempt in range(1, 5):
        try:
            checkout_operating_branch()
            primary_name = (
                "D1_CURRENT.json"
                if domain == "OPPORTUNITY_RESEARCH"
                else "RECOMMENDATION_CURRENT.json"
            )
            existing = TARGET_ROOT / primary_name
            existing_state = None
            if existing.exists():
                existing_state = json.loads(
                    existing.read_text(encoding="utf-8")
                ).get("state_id")

            if domain == "INVESTMENT_PIPELINE":
                incoming_comparison = load_json(Path(args.comparison))
                existing_comparison_path = (
                    TARGET_ROOT / "CAPITAL_COMPARISON_CURRENT.json"
                )
                existing_comparison = (
                    load_json(existing_comparison_path)
                    if existing_comparison_path.exists()
                    else None
                )
                if should_preserve_existing_decision(
                    incoming_comparison, existing_comparison
                ):
                    return {
                        "status": "PRESERVED_DECISION_CURRENT",
                        "domain": domain,
                        "advanced": False,
                        "reason": "NO_NEW_DECISION_GRADE_UNDERWRITING",
                        "state_id": existing_state,
                        "incoming_state_id": fingerprint,
                    }

            status = "NO_OP" if existing_state == fingerprint else "PASS"
            receipt = receipt_args(
                domain=domain,
                status=status,
                source_workflow=args.source_workflow,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
                source_branch=args.source_branch,
                source_commit=args.source_commit,
                watermark=watermark,
                fingerprint=fingerprint,
            )
            advance, reason = write_stage(
                domain=domain,
                files=file_texts,
                fingerprint=fingerprint,
                receipt=receipt,
            )

            run("git", "add", "--", ROOT_DIR)
            if (
                run(
                    "git", "diff", "--cached", "--quiet", check=False
                ).returncode
                == 0
            ):
                return {
                    "status": "NO_CHANGE",
                    "domain": domain,
                    "advanced": advance,
                    "reason": reason,
                    "state_id": fingerprint,
                }

            run(
                "git",
                "commit",
                "-m",
                (
                    f"operating-current: S2 {domain.lower()} "
                    f"{status.lower()} {fingerprint[-16:]}"
                ),
            )
            pushed = run(
                "git",
                "push",
                "origin",
                "HEAD:refs/heads/operating-current",
                check=False,
            )
            if pushed.returncode == 0:
                return {
                    "status": "PUBLISHED",
                    "domain": domain,
                    "advanced": advance,
                    "reason": reason,
                    "state_id": fingerprint,
                    "operating_commit": run(
                        "git", "rev-parse", "HEAD"
                    ).stdout.strip(),
                }
            last_error = pushed.stderr.strip()
            time.sleep(attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(attempt)

    raise RuntimeError(f"S2_PUBLISH_FAILED:{domain}:{last_error}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--stage", choices=["opportunity", "decision"], required=True
    )
    p.add_argument("--opportunity")
    p.add_argument("--d1")
    p.add_argument("--comparison")
    p.add_argument("--recommendation")
    p.add_argument("--source-workflow", required=True)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--source-run-attempt", required=True, type=int)
    p.add_argument("--source-branch", required=True)
    p.add_argument("--source-commit", required=True)
    return p


def main() -> None:
    args = parser().parse_args()
    if args.stage == "opportunity" and not (
        args.opportunity and args.d1
    ):
        raise SystemExit("--opportunity and --d1 are required")
    if args.stage == "decision" and not (
        args.comparison and args.recommendation
    ):
        raise SystemExit("--comparison and --recommendation are required")
    print(
        json.dumps(
            publish(args),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
