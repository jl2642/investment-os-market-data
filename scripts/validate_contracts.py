#!/usr/bin/env python3
"""Validate FMDL architecture and machine-readable operating contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "docs/FMDL-1A_ARCHITECTURE.md",
    "docs/DATA_CONTRACT.md",
    "docs/SOURCE_REGISTRY.md",
    "docs/QUALITY_GATES.md",
    "docs/UPDATE_CADENCE.md",
    "docs/INVESTMENT_OS_INTERFACE.md",
    "docs/FMDL-1A-R_ACCEPTANCE.md",
    "docs/FMDL-1DE_IMPLEMENTATION.md",
    "config/data_sources.json",
    "config/universe_rules.json",
    "config/quality_gates.json",
    "config/schedules.json",
    "schemas/a_share_universe.schema.json",
    "schemas/daily_market_snapshot.schema.json",
    "schemas/dataset_manifest.schema.json",
    "schemas/current_release.schema.json",
    "schemas/operating_status.schema.json",
    "scripts/validate_contracts.py",
    ".github/workflows/contract-validation.yml",
    ".github/workflows/fmdl-daily-production.yml",
]

JSON_FILES = [
    "config/data_sources.json",
    "config/universe_rules.json",
    "config/quality_gates.json",
    "config/schedules.json",
    "schemas/a_share_universe.schema.json",
    "schemas/daily_market_snapshot.schema.json",
    "schemas/dataset_manifest.schema.json",
    "schemas/current_release.schema.json",
    "schemas/operating_status.schema.json",
]


def load_json(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{relative_path} must contain a JSON object")
    return value


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        check((ROOT / relative_path).is_file(), f"Missing required file: {relative_path}", failures)

    if failures:
        print("FMDL CONTRACT VALIDATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    documents = {path: load_json(path) for path in JSON_FILES}

    universe_schema = documents["schemas/a_share_universe.schema.json"]
    snapshot_schema = documents["schemas/daily_market_snapshot.schema.json"]
    manifest_schema = documents["schemas/dataset_manifest.schema.json"]
    release_schema = documents["schemas/current_release.schema.json"]
    status_schema = documents["schemas/operating_status.schema.json"]
    universe_rules = documents["config/universe_rules.json"]
    sources = documents["config/data_sources.json"]
    quality = documents["config/quality_gates.json"]
    schedules = documents["config/schedules.json"]

    check(universe_schema.get("$id") == "a_share_universe.schema.json", "Unexpected universe schema $id", failures)
    check(snapshot_schema.get("$id") == "daily_market_snapshot.schema.json", "Unexpected snapshot schema $id", failures)
    check(manifest_schema.get("$id") == "dataset_manifest.schema.json", "Unexpected manifest schema $id", failures)
    check(release_schema.get("$id") == "current_release.schema.json", "Unexpected current release schema $id", failures)
    check(status_schema.get("$id") == "operating_status.schema.json", "Unexpected operating status schema $id", failures)
    check(universe_rules.get("schema_id") == universe_schema.get("$id"), "Universe rules schema reference mismatch", failures)

    required_universe_fields = {
        "as_of_date", "symbol", "name", "exchange", "board", "listing_status",
        "is_st", "is_suspended", "source_primary", "source_timestamp",
        "record_quality", "row_hash",
    }
    check(required_universe_fields.issubset(set(universe_schema.get("required", []))), "Universe required fields incomplete", failures)

    required_snapshot_fields = {
        "as_of_date", "symbol", "close", "prev_close", "pct_change",
        "volume_shares", "turnover_cny", "data_status", "source_primary",
        "source_timestamp", "record_quality", "row_hash",
    }
    check(required_snapshot_fields.issubset(set(snapshot_schema.get("required", []))), "Snapshot required fields incomplete", failures)

    check(sources.get("cost_policy") == "FREE_OR_FREE_TIER_ONLY", "Cost policy is not free-only", failures)
    adapters = sources.get("adapters", [])
    check(any(item.get("adapter_id") == "akshare" for item in adapters if isinstance(item, dict)), "AKShare adapter not registered", failures)

    universe_quality = quality.get("a_share_universe", {})
    snapshot_quality = quality.get("daily_market_snapshot", {})
    check(universe_quality.get("minimum_row_count", {}).get("value", 0) >= 4000, "Universe minimum row gate too low", failures)
    check(snapshot_quality.get("minimum_active_universe_coverage", {}).get("value", 0) >= 0.95, "Snapshot coverage gate below 95%", failures)
    check(quality.get("publication", {}).get("hard_gate_failure_action") == "QUARANTINE_AND_RETAIN_LKG", "LKG protection not configured", failures)

    jobs = schedules.get("jobs", [])
    daily_jobs = [item for item in jobs if isinstance(item, dict) and item.get("job_id") == "a_share_daily_market_mvp"]
    check(len(daily_jobs) == 1, "Daily market job contract missing or duplicated", failures)
    if daily_jobs:
        job = daily_jobs[0]
        check(job.get("status") == "ACTIVE_PRODUCTION_MVP", "Daily production schedule is not active", failures)
        check(job.get("github_cron_utc") == "30 9 * * 1-5", "Daily cron does not match 17:30 Asia/Shanghai", failures)
        check(job.get("requires_confirmed_trading_day") is True, "Trading calendar gate not required", failures)
        check(job.get("manual_dispatch_required") is True, "Manual dispatch requirement missing", failures)
        check(job.get("failure_behavior") == "RETAIN_LAST_KNOWN_GOOD_AND_FAIL_WORKFLOW", "Failure does not retain LKG", failures)

    manifest_statuses = manifest_schema.get("properties", {}).get("publication_status", {}).get("enum", [])
    for status in ["READY", "DEGRADED", "QUARANTINED", "FAILED", "PUBLISHED"]:
        check(status in manifest_statuses, f"Manifest status missing: {status}", failures)

    release_statuses = release_schema.get("properties", {}).get("status", {}).get("enum", [])
    check("PUBLISHED_WITH_WARNINGS" in release_statuses, "Controlled-warning release status missing", failures)
    operating_actions = status_schema.get("properties", {}).get("action", {}).get("enum", [])
    for action in ["PROMOTED_CURRENT", "RETAIN_LAST_KNOWN_GOOD", "NO_OP_NON_TRADING_DAY", "NO_OP_ALREADY_CURRENT"]:
        check(action in operating_actions, f"Operating action missing: {action}", failures)

    if failures:
        print("FMDL CONTRACT VALIDATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("FMDL CONTRACT VALIDATION: PASS")
    print(f"Validated {len(REQUIRED_FILES)} required files and {len(JSON_FILES)} JSON contracts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
