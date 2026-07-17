#!/usr/bin/env python3
"""Rebind the Investment OS consumer pointer to the latest accepted Current release."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
INTERFACE_PATH = ROOT / "outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path: Path) -> int:
    return int(len(pd.read_csv(path, dtype=str)))


def refresh(root: Path = ROOT) -> dict[str, Any]:
    interface_path = root / INTERFACE_PATH.relative_to(ROOT)
    current_path = root / CURRENT_RELEASE_PATH.relative_to(ROOT)
    interface = read_json(interface_path)
    current = read_json(current_path)
    blockers: list[str] = []
    if current.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        blockers.append("CURRENT_NOT_PUBLISHED")
    if current.get("hard_failures"):
        blockers.append("CURRENT_HAS_HARD_FAILURES")
    if blockers:
        raise RuntimeError(";".join(blockers))

    current_files = current.get("current_files", {})
    interface["generated_at"] = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    interface["status"] = "ACTIVE"
    interface["authority_boundary"] = "DATA_EVIDENCE_ONLY_NO_INVESTMENT_DECISION"
    interface["current_release"] = {
        "path": "outputs/current/CURRENT_RELEASE.json",
        "run_id": current["run_id"],
        "as_of_date": current["as_of_date"],
        "status": current["status"],
        "qa_status": current["qa_status"],
        "provider": current.get("market_wide_provider"),
        "hard_failure_count": len(current.get("hard_failures", [])),
        "soft_warnings": current.get("soft_warnings", []),
    }

    dataset_map = {item["dataset_id"]: item for item in interface.get("datasets", [])}
    bindings = {
        "a_share_universe": "a_share_universe",
        "daily_market_snapshot": "daily_market_snapshot",
        "market_event_flags": "market_event_flags",
    }
    errors: list[str] = []
    for dataset_id, current_key in bindings.items():
        item = dataset_map.get(dataset_id)
        current_item = current_files.get(current_key)
        if item is None or current_item is None:
            errors.append(f"MISSING_INTERFACE_BINDING_{dataset_id}")
            continue
        path = root / str(current_item["path"])
        if not path.exists():
            errors.append(f"MISSING_CURRENT_FILE_{dataset_id}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != current_item.get("sha256"):
            errors.append(f"CURRENT_FILE_HASH_MISMATCH_{dataset_id}")
            continue
        item["path"] = str(current_item["path"])
        item["sha256"] = actual_hash
        item["row_count"] = int(current_item.get("row_count", csv_rows(path)))
        manifest_path = item.get("manifest_path")
        if manifest_path:
            manifest = read_json(root / str(manifest_path))
            if str(manifest.get("run_id")) != str(current["run_id"]):
                errors.append(f"MANIFEST_RUN_ID_MISMATCH_{dataset_id}")
            if str(manifest.get("as_of_date")) != str(current["as_of_date"]):
                errors.append(f"MANIFEST_AS_OF_MISMATCH_{dataset_id}")
            manifest_hash = manifest.get("file_sha256") or manifest.get("sha256")
            if manifest_hash and manifest_hash != actual_hash:
                errors.append(f"MANIFEST_FILE_HASH_MISMATCH_{dataset_id}")
            manifest_rows = manifest.get("row_count")
            if manifest_rows is not None and int(manifest_rows) != int(item["row_count"]):
                errors.append(f"MANIFEST_ROW_COUNT_MISMATCH_{dataset_id}")
    if errors:
        raise RuntimeError(";".join(errors))

    interface["datasets"] = [dataset_map[item["dataset_id"]] for item in interface.get("datasets", [])]
    interface_path.parent.mkdir(parents=True, exist_ok=True)
    interface_path.write_text(json.dumps(interface, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "status": "PASS",
        "run_id": current["run_id"],
        "as_of_date": current["as_of_date"],
        "dataset_count": len(interface["datasets"]),
        "interface_sha256": sha256_file(interface_path),
        "authority": interface["authority_boundary"],
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    try:
        refresh(ROOT)
    except Exception as exc:
        print(f"Interface refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
