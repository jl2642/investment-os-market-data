from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

R2_MERGE_SHA = "fc57e7a08fee6870130871e8491bb2db59b70e54"
SOURCE_PR = 155
SOURCE_BRANCH = "agent/r3-position-action-matrix"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    source_head = str(args.source_head_sha)

    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    execution = read_json(execution_path)
    execution["portfolio_r2"] = {
        "status": "COMPLETED_ON_MAIN",
        "source_pr": 154,
        "merge_sha": R2_MERGE_SHA,
        "real_reference_architectures": 3,
        "simulation_sleeves": 6,
        "r3_started": True,
    }
    wp5 = execution["wp5"]
    wp5["branch"] = SOURCE_BRANCH
    wp5["source_pr"] = SOURCE_PR
    wp5["source_head_sha"] = source_head
    wp5["reason"] = "R3_USER_DECISION_PACK_READY_AWAITING_USER_SELECTION_FRESH_MARKS_AND_POSITION_CONTINUITY"
    wp5["next_gate"] = "USER_REVIEW_THEN_FRESH_MARKS_POSITION_CONTINUITY_AND_GOVERNED_IMPLEMENTATION_PROPOSAL"
    wp5["user_decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    wp5["r3_action_matrix_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_POSITION_ACTION_MATRIX_CURRENT.json"
    wp5["r3_user_decision_pack_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_PACK_CURRENT.md"
    wp5["position_continuity_confirmed_through"] = "2026-07-24"
    wp5["latest_accepted_decision_watermark"] = "2026-07-24_CLOSE"
    wp5["implementation_blocked_pending_post_2026_07_24_delta_confirmation"] = True
    wp5["trade_authority"] = TRADE_AUTHORITY
    write_json(execution_path, execution)

    contract_path = control / "WP5_PORTFOLIO_DECISION_CONTRACT.json"
    contract = read_json(contract_path)
    contract["fixed_workstreams"]["WP5-3"]["status"] = "COMPLETED_ON_MAIN"
    contract["fixed_workstreams"]["WP5-3"]["source_pr"] = 154
    contract["fixed_workstreams"]["WP5-3"]["merge_sha"] = R2_MERGE_SHA
    contract["fixed_workstreams"]["WP5-4"]["source_pr"] = SOURCE_PR
    contract["source_head_sha"] = source_head
    contract["decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    contract["position_action_matrix_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_POSITION_ACTION_MATRIX_CURRENT.json"
    contract["user_decision_pack_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_PACK_CURRENT.md"
    contract["implementation_ready_count"] = 0
    contract["ready_for_user_decision_count"] = 7
    contract["trade_authority"] = TRADE_AUTHORITY
    write_json(contract_path, contract)

    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    registry = read_json(registry_path)
    registry["github_merge_sha"] = R2_MERGE_SHA
    registry["latest_completed_main_merge_sha"] = R2_MERGE_SHA
    registry["latest_completed_main_pr"] = 154
    registry["latest_governed_merge_sha"] = R2_MERGE_SHA
    registry["registry_id"] = "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V12_R3_ACTION_MATRIX"
    registry["release_id"] = "INVESTMENT_OS_R19_20260727_R3_ACTION_MATRIX"
    registry["release_sequence"] = 19
    for row in registry.get("assets", []):
        asset_id = row.get("asset_id")
        if asset_id == "GITHUB_ACTIVE_RUNTIME":
            row["branch_candidate"] = SOURCE_BRANCH
            row["latest_governed_merge_sha"] = R2_MERGE_SHA
            row["role"] = "RULE_STATE_RESEARCH_DECISION_OPERATIONS_AND_CONTROL_RUNTIME"
            row["status"] = "GITHUB_MAIN_PR154_CURRENT_PR155_R3_CANDIDATE"
        if asset_id and asset_id.startswith("R2_PORTFOLIO_CONSTRUCTION_"):
            row["status"] = "COMPLETED_ON_MAIN"
            row["merge_sha"] = R2_MERGE_SHA
        if asset_id in {
            "R3_POSITION_ACTION_MATRIX_CURRENT",
            "R3_USER_DECISION_PACK_CURRENT",
            "R3_USER_DECISION_QUEUE_CURRENT",
            "R3_POSITION_ACTION_MATRIX_ACCEPTANCE",
            "R3_STATUS_CURRENT",
        }:
            row["source_head_sha"] = source_head
    write_json(registry_path, registry)

    acceptance_path = control / "R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json"
    acceptance = read_json(acceptance_path)
    acceptance["source_head_sha"] = source_head
    acceptance["control_metadata_normalized"] = True
    acceptance["r2_registry_status"] = "COMPLETED_ON_MAIN"
    acceptance["decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    write_json(acceptance_path, acceptance)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
