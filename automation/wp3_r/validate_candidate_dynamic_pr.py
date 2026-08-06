#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PROTECTED = (
    "candidate_core_members",
    "shadow_track_members",
    "ready_for_user_decision_members",
)
ROUTES = (*PROTECTED, "research_queue_members")
ALLOWED_TOP_LEVEL_CHANGES = {
    "research_queue_members",
    "counts",
    "continuous_candidate_engine_complete",
    "current_operating_stage",
    "dynamic_candidate_loop",
    "dynamic_research_queue_archive",
    "semantic_hash",
}
COUNT_KEYS = {
    "candidate_core",
    "shadow_track",
    "research_queue",
    "ready_for_user_decision",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ordered_ids(rows: list[dict[str, Any]], route: str) -> list[str]:
    result = [str(row["security_id"]) for row in rows]
    if len(result) != len(set(result)):
        raise SystemExit(f"DUPLICATE_SECURITY_ID_WITHIN_ROUTE:{route}")
    return result


def route_ids(candidate: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    flattened: list[str] = []
    for route in ROUTES:
        rows = candidate.get(route, [])
        if not isinstance(rows, list):
            raise SystemExit(f"CANDIDATE_ROUTE_NOT_LIST:{route}")
        result[route] = ordered_ids(rows, route)
        flattened.extend(result[route])
    if len(flattened) != len(set(flattened)):
        raise SystemExit("CROSS_ROUTE_CANDIDATE_DUPLICATION")
    return result


def validate(base: dict[str, Any], head: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    for key in sorted((set(base) | set(head)) - ALLOWED_TOP_LEVEL_CHANGES):
        if base.get(key) != head.get(key):
            raise SystemExit(f"FORBIDDEN_CANDIDATE_TOP_LEVEL_MUTATION:{key}")

    for field in PROTECTED:
        if base.get(field) != head.get(field):
            raise SystemExit(f"FORBIDDEN_DYNAMIC_CANDIDATE_ROUTE_MUTATION:{field}")

    base_routes = route_ids(base)
    head_routes = route_ids(head)
    base_queue = base.get("research_queue_members", [])
    head_queue = head.get("research_queue_members", [])
    base_ids = set(base_routes["research_queue_members"])
    head_ids = set(head_routes["research_queue_members"])
    added = head_ids - base_ids
    removed = base_ids - head_ids
    capacity = policy["capacity"]
    if len(added) > int(capacity["maximum_weekly_admissions"]):
        raise SystemExit("DYNAMIC_ADMISSION_CAP_EXCEEDED")
    if len(removed) > int(capacity["maximum_weekly_dynamic_exits"]):
        raise SystemExit("DYNAMIC_EXIT_CAP_EXCEEDED")
    if len(head_queue) > int(capacity["maximum_research_queue_size"]):
        raise SystemExit("RESEARCH_QUEUE_MAXIMUM_EXCEEDED")
    if len(head_queue) < int(capacity["minimum_research_queue_size"]):
        raise SystemExit("RESEARCH_QUEUE_MINIMUM_BREACHED")

    base_map = {row["security_id"]: row for row in base_queue}
    head_map = {row["security_id"]: row for row in head_queue}
    for security_id in sorted(base_ids & head_ids):
        if base_map[security_id] != head_map[security_id]:
            raise SystemExit(f"EXISTING_RESEARCH_QUEUE_ROW_MUTATION_FORBIDDEN:{security_id}")

    for security_id in sorted(added):
        row = head_map[security_id]
        required = {
            "dynamic_candidate_source": "FULL_MARKET_SCREEN",
            "candidate_state_change_requires_human_merge": True,
            "ready_for_user_decision": False,
            "real_account_permission": False,
            "simulation_admission_permission": False,
            "research_decision_grade": False,
            "buy_signal": "NO",
            "trade_authority": "NONE",
        }
        for key, value in required.items():
            if row.get(key) != value:
                raise SystemExit(f"INVALID_DYNAMIC_ADMISSION_CONTROL:{security_id}:{key}")
        row_hash_input = deepcopy(row)
        row_hash = row_hash_input.pop("semantic_hash", None)
        if row_hash != canonical_hash(row_hash_input):
            raise SystemExit(f"DYNAMIC_ADMISSION_SEMANTIC_HASH_MISMATCH:{security_id}")

    for security_id in sorted(removed):
        if base_map[security_id].get("dynamic_candidate_source") != "FULL_MARKET_SCREEN":
            raise SystemExit(f"LEGACY_RESEARCH_QUEUE_AUTOMATIC_EXIT_FORBIDDEN:{security_id}")

    base_archive = base.get("dynamic_research_queue_archive", [])
    head_archive = head.get("dynamic_research_queue_archive", [])
    if not isinstance(base_archive, list) or not isinstance(head_archive, list):
        raise SystemExit("DYNAMIC_ARCHIVE_NOT_LIST")
    if head_archive[: len(base_archive)] != base_archive:
        raise SystemExit("DYNAMIC_ARCHIVE_HISTORY_REWRITE_FORBIDDEN")
    appended_archive = head_archive[len(base_archive) :]
    archived_ids = {str(row.get("security_id")) for row in appended_archive}
    if archived_ids != removed or len(appended_archive) != len(removed):
        raise SystemExit("DYNAMIC_EXIT_ARCHIVE_MISMATCH")
    for row in appended_archive:
        if row.get("dynamic_candidate_source") != "FULL_MARKET_SCREEN":
            raise SystemExit(f"INVALID_DYNAMIC_ARCHIVE_SOURCE:{row.get('security_id')}")
        if not row.get("dynamic_exit_proposal_id") or not row.get("dynamic_exit_as_of"):
            raise SystemExit(f"DYNAMIC_ARCHIVE_LINEAGE_MISSING:{row.get('security_id')}")

    base_counts = base.get("counts", {})
    counts = head.get("counts", {})
    for key in sorted((set(base_counts) | set(counts)) - COUNT_KEYS):
        if base_counts.get(key) != counts.get(key):
            raise SystemExit(f"FORBIDDEN_CANDIDATE_COUNT_METADATA_MUTATION:{key}")
    expected = {
        "candidate_core": len(head.get("candidate_core_members", [])),
        "shadow_track": len(head.get("shadow_track_members", [])),
        "research_queue": len(head_queue),
        "ready_for_user_decision": len(head.get("ready_for_user_decision_members", [])),
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            raise SystemExit(f"CANDIDATE_COUNT_MISMATCH:{key}:{counts.get(key)}:{value}")

    loop = head.get("dynamic_candidate_loop", {})
    if loop.get("orders") != 0 or loop.get("trade_authority") != "NONE":
        raise SystemExit("DYNAMIC_LOOP_AUTHORITY_VIOLATION")
    if loop.get("canonical_authority") != "MERGE_OF_GOVERNED_PR_ONLY":
        raise SystemExit("DYNAMIC_LOOP_CANONICAL_AUTHORITY_VIOLATION")
    if int(loop.get("core_shadow_ready_automatic_mutations", -1)) != 0:
        raise SystemExit("DYNAMIC_LOOP_PROTECTED_ROUTE_MUTATION_CLAIM")
    if sorted(loop.get("admissions", [])) != sorted(added):
        raise SystemExit("DYNAMIC_LOOP_ADMISSION_LINEAGE_MISMATCH")
    if sorted(loop.get("dynamic_exits", [])) != sorted(removed):
        raise SystemExit("DYNAMIC_LOOP_EXIT_LINEAGE_MISMATCH")
    completed_cycles = int(loop.get("completed_weekly_cycle_count", 0))
    threshold = int(policy["hysteresis"]["completed_weekly_cycles_for_production_acceptance"])
    if bool(head.get("continuous_candidate_engine_complete")) != (completed_cycles >= threshold):
        raise SystemExit("DYNAMIC_LOOP_ACCEPTANCE_STATE_MISMATCH")

    hash_input = deepcopy(head)
    semantic_hash = hash_input.pop("semantic_hash", None)
    if semantic_hash != canonical_hash(hash_input):
        raise SystemExit("CANDIDATE_CURRENT_SEMANTIC_HASH_MISMATCH")

    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "unchanged_research_queue_rows": len(base_ids & head_ids),
        "core_mutations": 0,
        "shadow_mutations": 0,
        "ready_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--policy", default="automation/wp3_r/candidate_dynamic_policy.json")
    args = parser.parse_args()
    result = validate(read(Path(args.base)), read(Path(args.head)), read(Path(args.policy)))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
