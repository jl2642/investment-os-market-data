#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROTECTED = (
    "candidate_core_members",
    "shadow_track_members",
    "ready_for_user_decision_members",
)


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["security_id"]) for row in rows}


def validate(base: dict[str, Any], head: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    for field in PROTECTED:
        if base.get(field) != head.get(field):
            raise SystemExit(f"FORBIDDEN_DYNAMIC_CANDIDATE_ROUTE_MUTATION:{field}")
    base_queue = base.get("research_queue_members", [])
    head_queue = head.get("research_queue_members", [])
    added = ids(head_queue) - ids(base_queue)
    removed = ids(base_queue) - ids(head_queue)
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
    for security_id in added:
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
    for security_id in removed:
        if base_map[security_id].get("dynamic_candidate_source") != "FULL_MARKET_SCREEN":
            raise SystemExit(f"LEGACY_RESEARCH_QUEUE_AUTOMATIC_EXIT_FORBIDDEN:{security_id}")
    counts = head.get("counts", {})
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
    return {
        "added": sorted(added),
        "removed": sorted(removed),
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
