#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXECUTION = "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
REGISTRY = "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"
START = "investment_os_runtime/00_CONTROL/WP5_START_RECORD_CURRENT.json"
QUEUE = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json"
WORKPLAN = "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_WORKPLAN_CURRENT.json"
INVENTORY = "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/WP5_P0_INTERNAL_EVIDENCE_INVENTORY_CURRENT.json"

R2_CAPABILITY_MERGE_SHA = "33a5484f2ca919e80eef96a6750f801f751f8bdf"
R2_CANONICAL_CLOSURE_MERGE_SHA = "17db72e866bff027e1f786a8fd0c051ddfcd6c3a"
WP5_BRANCH = "agent/wp5-portfolio-decision-start"


def read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def upsert_asset(registry: dict[str, Any], payload: dict[str, Any]) -> None:
    assets = registry.setdefault("assets", [])
    if isinstance(assets, list):
        current = next((item for item in assets if isinstance(item, dict) and item.get("asset_id") == payload["asset_id"]), None)
        if current is None:
            assets.append(payload)
        else:
            current.update(payload)
    elif isinstance(assets, dict):
        assets[payload["asset_id"].lower()] = payload
    else:
        raise TypeError(f"Unsupported registry assets type: {type(assets).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    execution = read_json(root, EXECUTION)
    registry = read_json(root, REGISTRY)
    start = read_json(root, START)
    queue = read_json(root, QUEUE)
    workplan = read_json(root, WORKPLAN)
    inventory = read_json(root, INVENTORY)

    assert execution["current_step"] == "WP5_PORTFOLIO_DECISION_PHASE_STARTED_ANALYSIS_ONLY_ON_BRANCH"
    assert execution["r2"]["merge_sha"] == R2_CAPABILITY_MERGE_SHA
    assert execution["wp5"]["full_position_review_complete"] is True
    assert workplan["status"] == "READY_FOR_CURRENT_EVIDENCE_REFRESH_NOT_RESEARCH_COMPLETE"
    assert inventory["status"] == "INTERNAL_EVIDENCE_INVENTORY_COMPLETE_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_PENDING"
    assert inventory["summary"]["p0_object_count"] == 3
    assert inventory["summary"]["implementation_ready_count"] == 0
    assert inventory["summary"]["orders"] == 0

    execution["github_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    execution["latest_governed_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    execution["r2_capability_merge_sha"] = R2_CAPABILITY_MERGE_SHA
    execution["r2_canonical_closure_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    execution["next_task"] = "WP5_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_AND_FRESH_INPUT_REFRESH"
    execution["overall_status"] = "WP5_FULL_POSITION_REVIEW_COMPLETE_P0_EXTERNAL_RESEARCH_PENDING_NO_ACTION"
    wp5 = execution.setdefault("wp5", {})
    wp5.update({
        "status": "STARTED_ANALYSIS_ONLY_ON_BRANCH",
        "branch": WP5_BRANCH,
        "full_position_review_complete": True,
        "p0_reunderwrite_workplan_path": WORKPLAN,
        "p0_internal_evidence_inventory_path": INVENTORY,
        "p0_internal_evidence_inventory_complete": True,
        "p0_external_primary_source_reunderwrite_complete": False,
        "next_gate": "P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_FRESH_MARKS_EVENT_STATUS_AND_USER_DELTA",
        "ready_for_user_decision_count": 0,
        "position_mutation_allowed": False,
        "order_execution_allowed": False,
        "trade_authority": "NONE",
    })

    registry["github_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    registry["latest_governed_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    registry["r2_capability_merge_sha"] = R2_CAPABILITY_MERGE_SHA
    registry["r2_canonical_closure_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
    registry["registry_status"] = "WP5_START_POSITION_REVIEW_AND_P0_EVIDENCE_ASSETS_REGISTERED_ON_BRANCH_PENDING_MERGE"
    registry["status"] = "GITHUB_CURRENT_R2_ACCEPTED_WP5_START_AND_REVIEW_BRANCH_CANDIDATE_FILE_LIBRARY_PENDING"
    registry["active_branch_candidate"] = WP5_BRANCH

    assets = registry.get("assets", [])
    if isinstance(assets, list):
        runtime = next((item for item in assets if isinstance(item, dict) and item.get("asset_id") == "GITHUB_ACTIVE_RUNTIME"), None)
        if runtime:
            runtime["latest_governed_merge_sha"] = R2_CANONICAL_CLOSURE_MERGE_SHA
            runtime["status"] = "GITHUB_CURRENT_R2_ACCEPTED_WP5_BRANCH_CANDIDATE_PENDING_MERGE"
            runtime["branch_candidate"] = WP5_BRANCH

    upsert_asset(registry, {
        "asset_id": "WP5_P0_REUNDERWRITE_WORKPLAN_CURRENT",
        "authority": "GOVERNED_BRANCH_CANDIDATE",
        "format": "JSON",
        "location": WORKPLAN,
        "role": "WP5 P0 re-underwrite research and decision-gate workplan",
        "status": "CURRENT_BRANCH_CANDIDATE",
        "trade_authority": "NONE",
    })
    upsert_asset(registry, {
        "asset_id": "WP5_P0_INTERNAL_EVIDENCE_INVENTORY_CURRENT",
        "authority": "GOVERNED_BRANCH_CANDIDATE",
        "format": "JSON",
        "location": INVENTORY,
        "role": "WP5 P0 FMDL and Candidate internal evidence inventory",
        "status": "CURRENT_BRANCH_CANDIDATE_EXTERNAL_RESEARCH_PENDING",
        "trade_authority": "NONE",
    })

    start["full_position_review_complete"] = True
    start["p0_internal_evidence_inventory_complete"] = True
    start["p0_external_primary_source_reunderwrite_complete"] = False
    start["p0_reunderwrite_workplan_path"] = WORKPLAN
    start["p0_internal_evidence_inventory_path"] = INVENTORY
    start["next_task"] = "WP5_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_AND_FRESH_INPUT_REFRESH"
    start["implementation_ready"] = False
    start["economic_mutations"] = {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0}
    start["trade_authority"] = "NONE"

    queue["status"] = "P0_INTERNAL_EVIDENCE_INVENTORY_COMPLETE_EXTERNAL_REUNDERWRITE_PENDING_NO_IMPLEMENTATION_READY_ITEMS"
    queue["ready_for_user_decision_count"] = 0
    queue["orders"] = 0
    queue["trade_authority"] = "NONE"
    queue["p0_reunderwrite_workplan_path"] = WORKPLAN
    queue["p0_internal_evidence_inventory_path"] = INVENTORY

    write_json(root, EXECUTION, execution)
    write_json(root, REGISTRY, registry)
    write_json(root, START, start)
    write_json(root, QUEUE, queue)
    print({
        "latest_governed_merge_sha": R2_CANONICAL_CLOSURE_MERGE_SHA,
        "r2_capability_merge_sha": R2_CAPABILITY_MERGE_SHA,
        "wp5_full_position_review_complete": True,
        "p0_internal_evidence_inventory_complete": True,
        "p0_external_primary_source_reunderwrite_complete": False,
        "ready_for_user_decision": 0,
        "orders": 0,
        "trade_authority": "NONE",
    })


if __name__ == "__main__":
    main()
