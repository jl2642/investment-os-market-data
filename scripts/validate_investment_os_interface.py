#!/usr/bin/env python3
"""Validate the FMDL-1F Investment OS consumer interface against Current."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
INTERFACE_PATH = ROOT / "outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json"
SCHEMA_PATH = ROOT / "schemas/investment_os_market_data_interface.schema.json"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def fail(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    required_paths = [INTERFACE_PATH, SCHEMA_PATH, CURRENT_RELEASE_PATH]
    for path in required_paths:
        fail(path.is_file(), f"missing required file: {path.relative_to(ROOT)}", failures)
    if failures:
        print("FMDL-1F INTERFACE VALIDATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    interface = load_json(INTERFACE_PATH)
    schema = load_json(SCHEMA_PATH)
    current = load_json(CURRENT_RELEASE_PATH)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(validator.iter_errors(interface), key=lambda item: list(item.path))
    for error in schema_errors:
        failures.append(f"interface schema path={list(error.path)}: {error.message}")

    expected_dataset_ids = {"a_share_universe", "daily_market_snapshot", "market_event_flags"}
    datasets = {item["dataset_id"]: item for item in interface.get("datasets", []) if isinstance(item, dict)}
    fail(set(datasets) == expected_dataset_ids, f"dataset set mismatch: {sorted(datasets)}", failures)

    current_release = interface.get("current_release", {})
    fail(current_release.get("run_id") == current.get("run_id"), "interface/current run_id mismatch", failures)
    fail(current_release.get("as_of_date") == current.get("as_of_date"), "interface/current as_of_date mismatch", failures)
    fail(current_release.get("status") == current.get("status"), "interface/current status mismatch", failures)
    fail(current_release.get("qa_status") == current.get("qa_status"), "interface/current qa_status mismatch", failures)
    fail(current_release.get("provider") == current.get("market_wide_provider"), "interface/current provider mismatch", failures)
    fail(current_release.get("hard_failure_count") == len(current.get("hard_failures", [])), "hard-failure count mismatch", failures)
    fail(not current.get("hard_failures"), "Current contains hard failures", failures)
    fail(current.get("status") in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}, "Current is not published", failures)
    fail(current.get("authority_boundary") == "DATA_EVIDENCE_ONLY_NO_INVESTMENT_DECISION", "authority boundary mismatch", failures)

    current_files = current.get("current_files", {})
    release_keys = {
        "a_share_universe": "a_share_universe",
        "daily_market_snapshot": "daily_market_snapshot",
        "market_event_flags": "market_event_flags",
    }

    for dataset_id, item in datasets.items():
        path = ROOT / item["path"]
        fail(path.is_file(), f"missing dataset: {item['path']}", failures)
        if not path.is_file():
            continue
        actual_hash = sha256(path)
        actual_rows = csv_rows(path)
        fail(actual_hash == item["sha256"], f"interface hash mismatch: {dataset_id}", failures)
        fail(actual_rows == item["row_count"], f"interface row-count mismatch: {dataset_id} {actual_rows}!={item['row_count']}", failures)

        release_entry = current_files.get(release_keys[dataset_id], {})
        fail(release_entry.get("path") == item["path"], f"Current path mismatch: {dataset_id}", failures)
        fail(release_entry.get("sha256") == item["sha256"], f"Current hash mismatch: {dataset_id}", failures)
        if dataset_id == "market_event_flags":
            fail(release_entry.get("row_count") == item["row_count"], "Current event-flag row count mismatch", failures)

        manifest_path = item.get("manifest_path")
        quality_path = item.get("quality_path")
        if manifest_path:
            manifest = load_json(ROOT / manifest_path)
            fail(manifest.get("run_id") == current.get("run_id"), f"manifest run_id mismatch: {dataset_id}", failures)
            fail(manifest.get("as_of_date") == current.get("as_of_date"), f"manifest as_of_date mismatch: {dataset_id}", failures)
            fail(manifest.get("publication_status") == "PUBLISHED", f"manifest not published: {dataset_id}", failures)
            fail(manifest.get("file", {}).get("path") == item["path"], f"manifest file path mismatch: {dataset_id}", failures)
            fail(manifest.get("file", {}).get("sha256") == item["sha256"], f"manifest hash mismatch: {dataset_id}", failures)
            fail(manifest.get("row_count") == item["row_count"], f"manifest row count mismatch: {dataset_id}", failures)
        if quality_path:
            quality = load_json(ROOT / quality_path)
            fail(not quality.get("hard_failures"), f"quality hard failures: {dataset_id}", failures)

    allowed = set(interface.get("consumer_contract", {}).get("allowed_consumers", []))
    fail(allowed == {"INVESTMENT_OS", "PUBLIC_EQUITY_INVESTING"}, "consumer set mismatch", failures)
    fail(interface.get("downstream_handoff", {}).get("trade_authority") == "NONE", "interface creates trade authority", failures)

    if failures:
        print("FMDL-1F INTERFACE VALIDATION: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("FMDL-1F INTERFACE VALIDATION: PASS")
    print(
        json.dumps(
            {
                "run_id": current["run_id"],
                "as_of_date": current["as_of_date"],
                "datasets": {key: value["row_count"] for key, value in datasets.items()},
                "soft_warnings": current.get("soft_warnings", []),
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
