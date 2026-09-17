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
from automation.product_surface.build_product_surface import render_daily_brief

TRADE_AUTHORITY = "NONE"
DOMAIN = "PORTFOLIO_PRODUCT_SURFACE"
TARGET_ROOT = Path(ROOT_DIR) / "product_surface"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def normalize_display_surface(surface: dict[str, Any]) -> dict[str, Any]:
    """Keep the user-facing S3 surface fresh without changing recommendation authority.

    Portfolio monitoring already binds the exact current Portfolio Marks authority.  S3
    recommendation rows may carry an older S2 price snapshot after a marks-only refresh,
    so existing-position display prices are normalized from monitoring here.  This is a
    read-only display correction: actions, blockers, sizing and economic state are not
    changed.
    """
    fresh_prices: dict[str, float] = {}
    for row in (surface.get("portfolio_monitoring") or {}).get("rows", []) or []:
        sid = str(row.get("security_id") or "").strip()
        price = row.get("current_price")
        if sid and isinstance(price, (int, float)):
            fresh_prices[sid] = float(price)

    refreshed = 0
    for row in surface.get("portfolio_decisions", []) or []:
        sid = str(row.get("security_id") or "").strip()
        if sid not in fresh_prices:
            continue
        price = fresh_prices[sid]
        if row.get("current_price") != price:
            refreshed += 1
        row["current_price"] = price
        row["current_price_source"] = "PORTFOLIO_MARKS_CURRENT"
        row["current_price_as_of"] = surface.get("as_of_date")

    surface["display_semantics"] = {
        "portfolio_current_price_authority": "PORTFOLIO_MARKS_CURRENT",
        "portfolio_price_rows_refreshed": refreshed,
        "recommendation_review_count_is_execution_pending_count": False,
        "execution_pending_authority": "PHASE3_EXECUTION_VALIDATOR_AND_EPISODE_GUARD",
        "note": (
            "S3 ADD/TRIM expresses current recommendation intent. It does not prove that "
            "the recommendation episode remains unexecuted; Phase3 is authoritative for "
            "validated quantities and repeat-action suppression."
        ),
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return surface


def render_published_daily_brief(surface: dict[str, Any]) -> str:
    text = render_daily_brief(surface)
    text = text.replace(
        "- 当前需人工复核的决策项：",
        "- Recommendation 人工复核项（非执行待办）：",
        1,
    )
    boundary = "- ready_for_user_decision 只表示值得人工复核，不表示已授权执行。"
    replacement = (
        "- S3 的 ADD/TRIM 是当前投资意图，不表示该 recommendation episode 尚未执行；"
        "实际待执行数量、已执行识别与重复动作抑制以 Phase3 Execution Validator / episode guard 为准。\n"
        + boundary
    )
    text = text.replace(boundary, replacement, 1)
    return text


def verify_source_branch(branch: str, commit: str) -> None:
    remote = remote_branch_sha(branch)
    if remote is None:
        raise RuntimeError("S3_SOURCE_BRANCH_NOT_REMOTE")
    if remote != commit:
        raise RuntimeError(f"S3_SOURCE_COMMIT_NOT_BRANCH_HEAD:{remote}:{commit}")


def receipt_args(
    *,
    status: str,
    source_workflow: str,
    source_run_id: str,
    source_run_attempt: int,
    source_branch: str,
    source_commit: str,
    watermark: str,
    surface_id: str,
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
            "PASS_S3_PORTFOLIO_PRODUCT_SURFACE"
            if status == "PASS"
            else "NO_OP_SAME_SURFACE_ID"
        ),
        advance_current=status == "PASS",
        real_account_mutations=0,
        simulation_mutations=0,
        candidate_membership_mutations=0,
        orders=0,
        trade_authority=TRADE_AUTHORITY,
        note=f"S3 surface_id={surface_id}",
    )


def write_surface(
    *,
    json_text: str,
    markdown_text: str,
    surface_id: str,
    receipt: SimpleNamespace,
) -> tuple[bool, str]:
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    current_json = TARGET_ROOT / "PORTFOLIO_DECISION_SURFACE_CURRENT.json"
    existing_id = None
    if current_json.exists():
        try:
            existing_id = json.loads(current_json.read_text(encoding="utf-8")).get("surface_id")
        except Exception:
            existing_id = None

    if receipt.status == "PASS":
        current_json.write_text(json_text, encoding="utf-8")
        (TARGET_ROOT / "DAILY_INVESTMENT_BRIEF_CURRENT.md").write_text(
            markdown_text, encoding="utf-8"
        )
    elif existing_id != surface_id:
        raise RuntimeError("S3_NO_OP_SURFACE_NOT_CURRENT")

    published_at = utc_now()
    operating_receipt = receipt_payload(receipt, published_at)
    domain_dir = Path(ROOT_DIR) / "runs" / DOMAIN
    domain_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = (
        f"{receipt.source_run_id}-a{receipt.source_run_attempt}-"
        f"{receipt.status.lower()}.json"
    )
    (domain_dir / receipt_name).write_text(
        json.dumps(operating_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    pointer_path = Path(ROOT_DIR) / "domains" / f"{DOMAIN}.json"
    prior = (
        json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer_path.exists()
        else None
    )
    advance, reason = can_advance(prior, operating_receipt)
    if receipt.status == "PASS" and not advance:
        raise RuntimeError(f"S3_POINTER_NOT_ADVANCED:{reason}")
    if receipt.status == "NO_OP" and advance:
        raise RuntimeError("S3_NO_OP_UNEXPECTED_ADVANCE")
    if advance:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
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
    verify_source_branch(args.source_branch, args.source_commit)
    surface = normalize_display_surface(load_json(Path(args.surface_json)))
    if surface.get("status") != "PASS_S3_PORTFOLIO_PRODUCT_SURFACE":
        raise RuntimeError("S3_SURFACE_NOT_PASS")
    if surface.get("orders") != 0 or surface.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("S3_SURFACE_AUTHORITY_VIOLATION")
    surface_id = str(surface["surface_id"])
    watermark = str(surface["as_of_date"])
    json_text = json.dumps(
        surface,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    markdown_text = render_published_daily_brief(surface)

    run("git", "reset", "--hard", "HEAD", check=False)
    run("git", "clean", "-fd", check=False)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    last_error = ""
    for attempt in range(1, 5):
        try:
            checkout_operating_branch()
            existing = TARGET_ROOT / "PORTFOLIO_DECISION_SURFACE_CURRENT.json"
            existing_id = None
            if existing.exists():
                try:
                    existing_id = json.loads(existing.read_text(encoding="utf-8")).get("surface_id")
                except Exception:
                    existing_id = None
            status = "NO_OP" if existing_id == surface_id else "PASS"
            receipt = receipt_args(
                status=status,
                source_workflow=args.source_workflow,
                source_run_id=args.source_run_id,
                source_run_attempt=args.source_run_attempt,
                source_branch=args.source_branch,
                source_commit=args.source_commit,
                watermark=watermark,
                surface_id=surface_id,
            )
            advance, reason = write_surface(
                json_text=json_text,
                markdown_text=markdown_text,
                surface_id=surface_id,
                receipt=receipt,
            )
            run("git", "add", "--", ROOT_DIR)
            if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
                return {
                    "status": "NO_CHANGE",
                    "domain": DOMAIN,
                    "advanced": advance,
                    "reason": reason,
                    "surface_id": surface_id,
                }
            run(
                "git",
                "commit",
                "-m",
                f"operating-current: S3 portfolio product surface {status.lower()} {surface_id[-16:]}",
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
                    "domain": DOMAIN,
                    "advanced": advance,
                    "reason": reason,
                    "surface_id": surface_id,
                    "operating_commit": run("git", "rev-parse", "HEAD").stdout.strip(),
                }
            last_error = pushed.stderr.strip()
            time.sleep(attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(attempt)
    raise RuntimeError(f"S3_PUBLISH_FAILED:{last_error}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--surface-json", required=True)
    p.add_argument("--daily-brief", required=True)
    p.add_argument("--source-workflow", required=True)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--source-run-attempt", required=True, type=int)
    p.add_argument("--source-branch", required=True)
    p.add_argument("--source-commit", required=True)
    args = p.parse_args()
    print(json.dumps(publish(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
