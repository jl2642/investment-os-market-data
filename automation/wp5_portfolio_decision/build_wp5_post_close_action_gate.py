#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
P0_IDS = ("300124.SZ", "300750.SZ", "601138.SH")
P0_MERGE_SHA = "70f651ff042fbf815ad8e0346cabad02693745d9"
P0_PR_NUMBER = 148
HURDLE = 0.15


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def date_ge(left: str | None, right: str | None) -> bool:
    return bool(left and right and left >= right)


def dedupe_queue(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        queue_id = str(item.get("queue_id", "")).strip()
        if queue_id:
            out[queue_id] = item
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=("branch", "post-merge", "operating"), default="branch")
    parser.add_argument("--wp5-e-merge-sha", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    now = datetime.now(CN).isoformat()

    marks_path = root / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json"
    simulation_path = root / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    ledger_path = root / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
    research_path = root / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT.json"
    action_review_path = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json"
    queue_path = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json"
    gate_path = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_POST_CLOSE_ACTION_GATE_CURRENT.json"
    execution_path = root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    registry_path = root / "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"
    p0_acceptance_path = root / "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_ACCEPTANCE_RECORD.json"
    e_acceptance_path = root / "investment_os_runtime/00_CONTROL/WP5_E_POST_CLOSE_ACTION_GATE_ACCEPTANCE_RECORD.json"

    marks = read(marks_path)
    simulation = read(simulation_path)
    ledger = read(ledger_path)
    research = read(research_path)
    action_review = read(action_review_path)
    queue = read(queue_path)
    execution = read(execution_path)
    registry = read(registry_path)
    p0_acceptance = read(p0_acceptance_path)

    mark_map = {row["security_id"]: row for row in marks["marks"]}
    holding_map = {row["security_id"]: row for row in simulation["holdings"]}
    research_objects = research["research_objects"]
    prior_positions = {row["security_id"]: row for row in action_review["positions"]}

    latest_close = marks["data_watermark"]["latest_mark_date"]
    research_close = max(str(prior_positions[sid]["completed_close_date"]) for sid in P0_IDS)
    fresh_close_after_research = latest_close > research_close
    continuity_through = ledger.get("continuity_confirmed_through")
    continuity_confirmed = fresh_close_after_research and date_ge(continuity_through, latest_close)

    total_assets = float(simulation["summary"]["account_total_assets"])
    positions: list[dict[str, Any]] = []
    ready_count = 0

    for security_id in P0_IDS:
        obj = research_objects[security_id]
        holding = holding_map[security_id]
        mark = float(mark_map[security_id]["mark"])
        current_weight = float(holding["market_value"]) / total_assets if total_assets else 0.0
        band = obj["conditional_portfolio_decision"]["proposed_weight_band"]
        band_min, band_max = float(band["min"]), float(band["max"])
        within_band = band_min <= current_weight <= band_max
        base_case = next(row for row in obj["driver_based_scenarios"]["cases"] if row["scenario"] == "BASE")
        base_return = float(base_case["implied_price"]) / mark - 1.0
        hurdle_passed = base_return >= HURDLE

        if not fresh_close_after_research:
            posture = "BLOCKED_PENDING_NEXT_COMPLETED_CLOSE"
            ready = False
        elif not continuity_confirmed:
            posture = "BLOCKED_PENDING_USER_POSITION_CONTINUITY_CONFIRMATION"
            ready = False
        elif current_weight > band_max:
            posture = "TRIM_REVIEW_PENDING_USER_APPROVAL"
            ready = True
        elif current_weight < band_min and hurdle_passed:
            posture = "ADD_REVIEW_PENDING_USER_APPROVAL"
            ready = True
        elif hurdle_passed:
            posture = "ADD_REVIEW_PENDING_USER_APPROVAL"
            ready = True
        else:
            posture = "HOLD_WITHIN_REVISED_BAND_NO_ADD" if within_band else "HOLD_NO_ACTION_HURDLE_NOT_PASSED"
            ready = False

        ready_count += int(ready)
        positions.append(
            {
                "security_id": security_id,
                "security_name": holding["security_name"],
                "completed_close_date": latest_close,
                "completed_close_mark": mark,
                "quantity": holding["quantity"],
                "unit_cost": holding["unit_cost"],
                "cost_basis": holding["cost_basis"],
                "market_value": holding["market_value"],
                "current_weight": round(current_weight, 8),
                "revised_weight_band": {"min": band_min, "max": band_max},
                "within_revised_weight_band": within_band,
                "base_case_implied_price": base_case["implied_price"],
                "base_case_expected_return": round(base_return, 8),
                "base_case_hurdle": HURDLE,
                "base_case_hurdle_passed": hurdle_passed,
                "conditional_action_posture": posture,
                "ready_for_user_decision": ready,
                "implementation_ready": False,
                "position_change_authorized": False,
                "order_authorized": False,
                "trade_authority": "NONE",
            }
        )

    if not fresh_close_after_research:
        status = "BLOCKED_PENDING_NEXT_COMPLETED_CLOSE"
        next_task = "WAIT_FOR_NEXT_COMPLETED_CLOSE_AFTER_2026_07_24"
    elif not continuity_confirmed:
        status = "BLOCKED_PENDING_USER_POSITION_CONTINUITY_CONFIRMATION"
        next_task = f"USER_CONFIRM_POSITION_CONTINUITY_THROUGH_{latest_close.replace('-', '_')}"
    elif ready_count:
        status = "CONDITIONAL_PROPOSALS_READY_PENDING_USER_DECISION_NO_IMPLEMENTATION"
        next_task = "USER_REVIEW_CONDITIONAL_P0_POSITION_PROPOSALS"
    else:
        status = "POST_CLOSE_GATE_COMPLETE_NO_ACTION_READY"
        next_task = "CONTINUE_MONITORING_AND_NON_P0_RESEARCH_TRIAGE"

    gate = {
        "schema_version": "1.0.0",
        "state_id": "WP5_POST_CLOSE_ACTION_GATE_CURRENT",
        "generated_at": now,
        "mode": args.mode,
        "status": status,
        "research_baseline_close_date": research_close,
        "latest_completed_close_date": latest_close,
        "fresh_completed_close_after_research": fresh_close_after_research,
        "user_delta_ledger_path": str(ledger_path.relative_to(root)),
        "user_position_continuity_confirmed_through": continuity_through,
        "user_position_continuity_confirmed_for_latest_close": continuity_confirmed,
        "governed_expected_return_hurdle": HURDLE,
        "positions": positions,
        "ready_for_user_decision_count": ready_count,
        "implementation_ready_count": 0,
        "next_task": next_task,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    write(gate_path, gate)

    queue_items = dedupe_queue(queue.get("items", []))
    queue_items["WP5-Q1"] = {
        "queue_id": "WP5-Q1",
        "subject": "Position continuity confirmation",
        "required_evidence": f"User confirms no Real or Simulation quantity/cost changes through {latest_close}, or supplies transaction deltas",
        "status": "COMPLETE" if continuity_confirmed else "PENDING_USER_CONFIRMATION",
    }
    queue_items["WP5-Q2"] = {
        "queue_id": "WP5-Q2",
        "subject": "Fresh completed-close market marks",
        "required_evidence": f"Completed A-share close after {research_close}",
        "status": "COMPLETE" if fresh_close_after_research else "PENDING_MARKET_CLOSE",
    }
    queue_items["WP5-Q4A"] = {
        "queue_id": "WP5-Q4A",
        "subject": "Simulation P0 re-underwrite",
        "required_evidence": "Three P0 primary-source re-underwrites and nine scenarios",
        "status": "COMPLETE_RESEARCH_ONLY",
    }
    queue_items["WP5-Q6"] = {
        "queue_id": "WP5-Q6",
        "subject": "P0 post-close action gate",
        "required_evidence": "Fresh completed close, position continuity and governed weight/return triggers",
        "status": status,
    }
    queue.update(
        {
            "generated_at": now,
            "items": [queue_items[key] for key in sorted(queue_items)],
            "ready_for_user_decision_count": ready_count,
            "orders": 0,
            "status": status,
            "post_close_action_gate_path": str(gate_path.relative_to(root)),
            "trade_authority": "NONE",
        }
    )
    write(queue_path, queue)

    p0_acceptance.update(
        {
            "accepted_pr": P0_PR_NUMBER,
            "merge_sha": P0_MERGE_SHA,
            "accepted_on_main": True,
            "status": "WP5_P0_EXTERNAL_REUNDERWRITE_ACCEPTED_RESEARCH_ONLY_ON_MAIN",
            "trade_authority": "NONE",
        }
    )
    write(p0_acceptance_path, p0_acceptance)

    wp5_e_merge_sha = args.wp5_e_merge_sha if args.mode == "post-merge" else None
    e_acceptance = {
        "acceptance_id": "WP5_E_POST_CLOSE_ACTION_GATE_ACCEPTANCE_V1",
        "generated_at": now,
        "mode": args.mode,
        "p0_merge_sha": P0_MERGE_SHA,
        "wp5_e_merge_sha": wp5_e_merge_sha,
        "gate_status": status,
        "fresh_completed_close_after_research": fresh_close_after_research,
        "user_position_continuity_confirmed_for_latest_close": continuity_confirmed,
        "ready_for_user_decision_count": ready_count,
        "implementation_ready_count": 0,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "status": (
            "WP5_E_ACCEPTED_ON_MAIN_OPERATING"
            if args.mode == "post-merge"
            else "WP5_E_OPERATING_GATE_REFRESHED"
            if args.mode == "operating"
            else "WP5_E_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
        ),
        "trade_authority": "NONE",
    }
    write(e_acceptance_path, e_acceptance)

    if args.mode in {"branch", "post-merge"}:
        effective_merge = wp5_e_merge_sha or P0_MERGE_SHA
        execution["github_merge_sha"] = effective_merge
        execution["latest_governed_merge_sha"] = effective_merge
        execution["current_step"] = (
            "WP5_E_POST_CLOSE_ACTION_GATE_ACCEPTED_ON_MAIN"
            if args.mode == "post-merge"
            else "WP5_E_POST_CLOSE_ACTION_GATE_INSTALLED_ON_BRANCH"
        )
        execution["overall_status"] = (
            "WP5_E_OPERATING_ON_MAIN_NO_AUTOMATIC_ACTION"
            if args.mode == "post-merge"
            else "WP5_D_ACCEPTED_ON_MAIN_WP5_E_GATE_PENDING_USER_MERGE"
        )
        execution["next_task"] = next_task if args.mode == "post-merge" else "USER_MERGE_WP5_E_POST_CLOSE_ACTION_GATE_PR"
        execution["wp5"].update(
            {
                "branch": "agent/wp5-e-post-close-action-gate",
                "status": "POST_CLOSE_ACTION_GATE_ACCEPTED_ON_MAIN" if args.mode == "post-merge" else "POST_CLOSE_ACTION_GATE_INSTALLED_ON_BRANCH_PENDING_MERGE",
                "p0_external_reunderwrite_accepted_on_main": True,
                "p0_merge_sha": P0_MERGE_SHA,
                "post_close_action_gate_installed": True,
                "post_close_action_gate_path": str(gate_path.relative_to(root)),
                "post_close_action_gate_status": status,
                "fresh_completed_close_for_action": fresh_close_after_research,
                "user_position_continuity_confirmed": continuity_confirmed,
                "ready_for_user_decision_count": ready_count,
                "position_mutation_allowed": False,
                "order_execution_allowed": False,
                "trade_authority": "NONE",
            }
        )
        write(execution_path, execution)

        current_ids = {
            "WP5_CONTRACT",
            "WP5_START",
            "WP5_DECISION_INPUT_CURRENT",
            "WP5_PORTFOLIO_DECISION_CURRENT",
            "WP5_USER_DECISION_QUEUE_CURRENT",
            "WP5_POSITION_REVIEW_CURRENT",
            "WP5_P0_REUNDERWRITE_WORKPLAN_CURRENT",
            "WP5_P0_INTERNAL_EVIDENCE_INVENTORY_CURRENT",
            "WP5_P0_FRESH_INPUT_STATUS_CURRENT",
            "WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT",
            "WP5_P0_ACTION_REVIEW_CURRENT",
            "WP5_P0_REUNDERWRITE_ACCEPTANCE",
        }
        for asset in registry.get("assets", []):
            if asset.get("asset_id") in current_ids:
                asset["authority"] = "CANONICAL_CURRENT"
                asset["status"] = "CURRENT_RESEARCH_ONLY_NO_ACTION_READY" if "ACTION_REVIEW" in asset["asset_id"] else "CURRENT"
                asset["merge_sha"] = P0_MERGE_SHA
        gate_asset = next((x for x in registry.get("assets", []) if x.get("asset_id") == "WP5_POST_CLOSE_ACTION_GATE_CURRENT"), None)
        if gate_asset is None:
            registry["assets"].append(
                {
                    "asset_id": "WP5_POST_CLOSE_ACTION_GATE_CURRENT",
                    "authority": "CANONICAL_CURRENT" if args.mode == "post-merge" else "GOVERNED_BRANCH_CANDIDATE",
                    "format": "JSON",
                    "location": str(gate_path.relative_to(root)),
                    "role": "WP5 completed-close, continuity, weight-band and expected-return action gate",
                    "status": "CURRENT" if args.mode == "post-merge" else "BRANCH_CANDIDATE_PENDING_MERGE",
                    "trade_authority": "NONE",
                }
            )
        registry["active_branch_candidate"] = None if args.mode == "post-merge" else "agent/wp5-e-post-close-action-gate"
        registry["github_merge_sha"] = effective_merge
        registry["latest_governed_merge_sha"] = effective_merge
        registry["registry_status"] = "WP5_E_ACCEPTED_ON_MAIN" if args.mode == "post-merge" else "WP5_D_ACCEPTED_ON_MAIN_WP5_E_BRANCH_CANDIDATE"
        registry["status"] = "GITHUB_CURRENT_WP5_E_OPERATING_FILE_LIBRARY_PENDING" if args.mode == "post-merge" else "GITHUB_CURRENT_WP5_D_ACCEPTED_WP5_E_PENDING_MERGE_FILE_LIBRARY_PENDING"
        write(registry_path, registry)
    else:
        execution["wp5"]["post_close_action_gate_status"] = status
        execution["wp5"]["fresh_completed_close_for_action"] = fresh_close_after_research
        execution["wp5"]["user_position_continuity_confirmed"] = continuity_confirmed
        execution["wp5"]["ready_for_user_decision_count"] = ready_count
        execution["next_task"] = next_task
        execution["overall_status"] = status
        write(execution_path, execution)

    print(
        json.dumps(
            {
                "mode": args.mode,
                "status": status,
                "latest_completed_close_date": latest_close,
                "continuity_confirmed_through": continuity_through,
                "ready_for_user_decision_count": ready_count,
                "economic_mutations": 0,
                "orders": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
