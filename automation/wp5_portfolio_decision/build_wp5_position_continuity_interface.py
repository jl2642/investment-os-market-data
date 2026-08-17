from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PR149 = 149
PR150 = 150
WP5_E_MERGE_SHA = "c2abeb4c0c0a78db6007f2c5683bb84a70947b29"
RESEARCH_BASELINE_CLOSE = "2026-07-24"
TRADE_AUTHORITY = "NONE"
BRANCH = "agent/wp5-f-continuity-interface"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_if_exists(path: Path) -> dict:
    return read_json(path) if path.exists() else {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upsert_asset(registry: dict, asset: dict) -> None:
    assets = registry.setdefault("assets", [])
    for index, row in enumerate(assets):
        if row.get("asset_id") == asset["asset_id"]:
            assets[index] = {**row, **asset}
            return
    assets.append(asset)


def unchanged_request(existing: dict, latest_close: str, continuity_through: str, status: str) -> bool:
    return (
        existing.get("latest_completed_close_date") == latest_close
        and existing.get("continuity_confirmed_through") == continuity_through
        and existing.get("status") == status
    )


def session_date(value: object) -> str:
    """Normalize a date or ISO timestamp to YYYY-MM-DD for interval semantics."""
    text = str(value or "").strip()
    if len(text) < 10:
        raise ValueError(f"SESSION_DATE_UNRESOLVED:{text!r}")
    candidate = text[:10]
    datetime.strptime(candidate, "%Y-%m-%d")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=("branch", "post-merge", "operating"), default="branch")
    parser.add_argument("--wp5-f-merge-sha", default=None)
    parser.add_argument("--accepted-pr", type=int, default=PR150)
    args = parser.parse_args()

    root = Path(args.repo_root)
    control = root / "investment_os_runtime/00_CONTROL"
    decisions = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS"
    inputs = root / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT"
    marks_path = root / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json"

    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    wp5e_acceptance_path = control / "WP5_E_POST_CLOSE_ACTION_GATE_ACCEPTANCE_RECORD.json"
    ledger_path = inputs / "USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
    gate_path = decisions / "WP5_POST_CLOSE_ACTION_GATE_CURRENT.json"
    queue_path = decisions / "WP5_USER_DECISION_QUEUE_CURRENT.json"
    request_path = inputs / "WP5_POSITION_CONTINUITY_REQUEST_CURRENT.json"
    acceptance_path = control / "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTANCE_RECORD.json"

    execution = read_json(execution_path)
    registry = read_json(registry_path)
    wp5e_acceptance = read_json(wp5e_acceptance_path)
    ledger = read_json(ledger_path)
    marks = read_json(marks_path)
    gate = read_json(gate_path)
    queue = read_json(queue_path)
    existing_request = read_json_if_exists(request_path)
    existing_acceptance = read_json_if_exists(acceptance_path)

    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    latest_close = session_date(marks["data_watermark"]["latest_mark_date"])
    continuity_through = str(ledger["continuity_confirmed_through"])
    continuity_date = session_date(continuity_through)
    fresh_close = latest_close > RESEARCH_BASELINE_CLOSE
    continuity_current = continuity_date >= latest_close

    if not fresh_close:
        request_status = "WAITING_FOR_NEXT_COMPLETED_CLOSE"
        next_task = "WAIT_FOR_NEXT_COMPLETED_CLOSE_AFTER_2026_07_24"
        response_required = False
    elif not continuity_current:
        request_status = "USER_POSITION_CONTINUITY_CONFIRMATION_REQUIRED"
        next_task = f"USER_CONFIRM_ZERO_OR_REPORT_DELTAS_THROUGH_{latest_close.replace('-', '_')}"
        response_required = True
    else:
        request_status = "POSITION_CONTINUITY_CURRENT"
        next_task = "RUN_WP5_E_POST_CLOSE_ACTION_GATE_RECALCULATION"
        response_required = False

    request_generated_at = (
        existing_request.get("generated_at", now)
        if unchanged_request(existing_request, latest_close, continuity_through, request_status)
        else now
    )
    scope_start = continuity_date if continuity_date < latest_close else latest_close
    request = {
        "schema_version": "1.0.0",
        "request_id": "WP5_POSITION_CONTINUITY_REQUEST_CURRENT",
        "generated_at": request_generated_at,
        "status": request_status,
        "latest_completed_close_date": latest_close,
        "research_baseline_close_date": RESEARCH_BASELINE_CLOSE,
        "continuity_confirmed_through": continuity_through,
        "fresh_completed_close_after_research": fresh_close,
        "user_response_required": response_required,
        "requested_scope": {
            "start_exclusive": scope_start,
            "end_inclusive": latest_close,
            "accounts": ["REAL_ACCOUNT", "SIMULATION"],
        },
        "accepted_user_response_modes": [
            {
                "mode": "CONFIRM_ZERO_DELTA",
                "required_statement": "Confirm that no Real-account trades, Simulation trades, security conversions, cancellations affecting holdings, cash transfers affecting broker execution balance, or Candidate membership changes occurred in the requested scope.",
            },
            {
                "mode": "REPORT_DELTAS",
                "required_fields_per_entry": [
                    "account",
                    "trade_date",
                    "security_id_or_cash",
                    "transaction_type",
                    "quantity_change",
                    "cash_change",
                    "fees_and_taxes",
                    "unit_price_if_applicable",
                ],
            },
        ],
        "governance": {
            "continuity_may_not_be_inferred": True,
            "market_marks_never_create_transaction_deltas": True,
            "quantity_and_cost_change_only_from_user_confirmed_delta": True,
            "broker_verification_not_inferred": True,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
        },
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "orders": 0,
        },
        "next_task": next_task,
    }
    write_json(request_path, request)

    wp5e_acceptance.update(
        {
            "accepted_on_main": True,
            "accepted_pr": PR149,
            "merge_sha": WP5_E_MERGE_SHA,
            "wp5_e_merge_sha": WP5_E_MERGE_SHA,
            "status": "WP5_E_ACCEPTED_ON_MAIN",
            "trade_authority": TRADE_AUTHORITY,
        }
    )
    write_json(wp5e_acceptance_path, wp5e_acceptance)

    canonical_interface_merge_sha = (
        args.wp5_f_merge_sha
        if args.mode == "post-merge" and args.wp5_f_merge_sha
        else existing_acceptance.get("wp5_f_merge_sha")
    )
    interface_accepted_on_main = bool(
        existing_acceptance.get("accepted_on_main") and canonical_interface_merge_sha
    ) or bool(args.mode == "post-merge" and args.wp5_f_merge_sha)
    payload_accepted_on_main = bool(args.mode == "post-merge" and args.wp5_f_merge_sha)

    wp5 = execution.setdefault("wp5", {})
    wp5.update(
        {
            "branch": "main" if payload_accepted_on_main else BRANCH,
            "post_close_action_gate_installed": True,
            "post_close_action_gate_accepted_on_main": True,
            "post_close_action_gate_merge_sha": WP5_E_MERGE_SHA,
            "post_close_action_gate_path": str(gate_path.relative_to(root)),
            "post_close_action_gate_status": gate["status"],
            "position_continuity_interface_installed": True,
            "position_continuity_request_path": str(request_path.relative_to(root)),
            "position_continuity_request_status": request_status,
            "user_position_continuity_confirmed": continuity_current,
            "fresh_completed_close_for_action": fresh_close,
            "position_mutation_allowed": False,
            "order_execution_allowed": False,
            "ready_for_user_decision_count": 0,
            "trade_authority": TRADE_AUTHORITY,
        }
    )

    if payload_accepted_on_main:
        execution.update(
            {
                "current_step": "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN",
                "github_merge_sha": canonical_interface_merge_sha,
                "latest_governed_merge_sha": canonical_interface_merge_sha,
                "next_task": next_task,
                "overall_status": "WP5_F_ACCEPTED_ON_MAIN_OPERATING_GATE_ACTIVE",
            }
        )
        wp5["status"] = "POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN"
    elif interface_accepted_on_main:
        execution.update(
            {
                "current_step": "WP5_F_OPERATING_PROPOSAL_PENDING_MERGE",
                "github_merge_sha": canonical_interface_merge_sha,
                "latest_governed_merge_sha": canonical_interface_merge_sha,
                "next_task": "MERGE_GOVERNED_WP5_F_CONTINUITY_PROPOSAL",
                "overall_status": "WP5_F_INTERFACE_ACCEPTED_OPERATING_PROPOSAL_PENDING_MERGE",
            }
        )
        wp5["status"] = "POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN_PROPOSAL_PENDING_MERGE"
    else:
        execution.update(
            {
                "current_step": "WP5_F_POSITION_CONTINUITY_INTERFACE_INSTALLED_ON_BRANCH",
                "github_merge_sha": WP5_E_MERGE_SHA,
                "latest_governed_merge_sha": WP5_E_MERGE_SHA,
                "next_task": "USER_MERGE_WP5_F_POSITION_CONTINUITY_INTERFACE_PR",
                "overall_status": "WP5_E_ACCEPTED_ON_MAIN_WP5_F_PENDING_USER_MERGE",
            }
        )
        wp5["status"] = "POSITION_CONTINUITY_INTERFACE_INSTALLED_ON_BRANCH_PENDING_MERGE"

    execution["trade_authority"] = TRADE_AUTHORITY
    write_json(execution_path, execution)

    registry["active_branch_candidate"] = None if payload_accepted_on_main else BRANCH
    registry["github_merge_sha"] = canonical_interface_merge_sha or WP5_E_MERGE_SHA
    registry["latest_governed_merge_sha"] = canonical_interface_merge_sha or WP5_E_MERGE_SHA
    if args.mode != "operating" or not unchanged_request(existing_request, latest_close, continuity_through, request_status):
        registry["date"] = now[:10]
    upsert_asset(
        registry,
        {
            "asset_id": "WP5_POST_CLOSE_ACTION_GATE_CURRENT",
            "authority": "CANONICAL_CURRENT",
            "format": "JSON",
            "location": str(gate_path.relative_to(root)),
            "merge_sha": WP5_E_MERGE_SHA,
            "role": "WP5 completed-close, continuity, weight-band and expected-return action gate",
            "status": "CURRENT",
            "trade_authority": TRADE_AUTHORITY,
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP5_POSITION_CONTINUITY_CONTRACT",
            "authority": "CANONICAL_CURRENT" if interface_accepted_on_main else "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": "investment_os_runtime/00_CONTROL/WP5_POSITION_CONTINUITY_CONTRACT.json",
            "merge_sha": canonical_interface_merge_sha,
            "role": "User-authoritative zero-delta confirmation and transaction-delta reporting contract",
            "status": "CURRENT" if interface_accepted_on_main else "BRANCH_CANDIDATE_PENDING_MERGE",
            "trade_authority": TRADE_AUTHORITY,
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP5_POSITION_CONTINUITY_REQUEST_CURRENT",
            "authority": "CANONICAL_CURRENT" if payload_accepted_on_main else "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": str(request_path.relative_to(root)),
            "merge_sha": canonical_interface_merge_sha if payload_accepted_on_main else None,
            "role": "Current user confirmation request derived from completed-close and delta-ledger watermarks",
            "status": "CURRENT" if payload_accepted_on_main else "BRANCH_CANDIDATE_PENDING_MERGE",
            "trade_authority": TRADE_AUTHORITY,
        },
    )
    if payload_accepted_on_main:
        registry["registry_status"] = "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN"
        registry["status"] = "GITHUB_CURRENT_WP5_F_ACCEPTED_FILE_LIBRARY_PENDING"
    elif interface_accepted_on_main:
        registry["registry_status"] = "WP5_F_OPERATING_PROPOSAL_PENDING_MERGE"
        registry["status"] = "GITHUB_CURRENT_WP5_F_INTERFACE_ACCEPTED_PROPOSAL_PENDING_MERGE"
    else:
        registry["registry_status"] = "WP5_E_ACCEPTED_ON_MAIN_WP5_F_BRANCH_CANDIDATE"
        registry["status"] = "GITHUB_CURRENT_WP5_E_ACCEPTED_WP5_F_PENDING_MERGE_FILE_LIBRARY_PENDING"
    write_json(registry_path, registry)

    if payload_accepted_on_main or not interface_accepted_on_main:
        acceptance_state = {
            "mode": args.mode,
            "status": "WP5_F_ACCEPTED_ON_MAIN" if payload_accepted_on_main else "WP5_F_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE",
            "accepted_on_main": payload_accepted_on_main,
            "accepted_pr": args.accepted_pr if payload_accepted_on_main else None,
            "wp5_e_merge_sha": WP5_E_MERGE_SHA,
            "wp5_f_merge_sha": canonical_interface_merge_sha if payload_accepted_on_main else None,
            "latest_completed_close_date": latest_close,
            "continuity_confirmed_through": continuity_through,
            "request_status": request_status,
        }
        acceptance_generated_at = (
            existing_acceptance.get("generated_at", now)
            if all(existing_acceptance.get(key) == value for key, value in acceptance_state.items())
            else now
        )
        acceptance = {
            "acceptance_id": "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTANCE_V1",
            "generated_at": acceptance_generated_at,
            **acceptance_state,
            "ready_for_user_decision_count": 0,
            "implementation_ready_count": 0,
            "economic_mutations": {
                "real_account": 0,
                "simulation": 0,
                "candidate_membership": 0,
                "orders": 0,
            },
            "trade_authority": TRADE_AUTHORITY,
        }
        write_json(acceptance_path, acceptance)

    queue["ready_for_user_decision_count"] = 0
    queue["orders"] = 0
    queue["trade_authority"] = TRADE_AUTHORITY
    queue["position_continuity_request_status"] = request_status
    queue["position_continuity_request_path"] = str(request_path.relative_to(root))
    write_json(queue_path, queue)

    print(
        json.dumps(
            {
                "mode": args.mode,
                "latest_completed_close_date": latest_close,
                "continuity_confirmed_through": continuity_through,
                "request_status": request_status,
                "next_task": next_task,
                "interface_accepted_on_main": interface_accepted_on_main,
                "payload_accepted_on_main": payload_accepted_on_main,
                "mutations": 0,
                "orders": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
