#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from fmdl5d_r12_matrix import build_month_matrix
from run_fmdl5d_disclosure_financial_store import now_utc


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = read_json(Path(args.contract))
    source_decision = read_json(Path(contract["source_release"]["decision_path"]))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    start = date.fromisoformat(args.start_date or contract["period_policy"]["default_start_date"])
    source_metrics = source_decision.get("metrics", {})
    inferred_end = source_metrics.get("max_market_date") or source_metrics.get("market_max_date")
    if not inferred_end and not args.end_date:
        raise ValueError("SOURCE_RELEASE_MARKET_MAX_DATE_MISSING")
    end = date.fromisoformat(args.end_date or str(inferred_end))
    expected_rows = build_month_matrix(start, end)
    expected_by_month = {row["month_key"]: row for row in expected_rows}

    status_paths = sorted(source.rglob("FMDL5D_R12_DISCLOSURE_MONTH_*_STATUS.json"))
    statuses = [read_json(path) for path in status_paths]
    month_keys = [str(status.get("month_key", "")) for status in statuses]
    duplicate_month_keys = sorted({key for key in month_keys if key and month_keys.count(key) > 1})
    missing_month_keys = sorted(set(expected_by_month) - set(month_keys))
    unexpected_month_keys = sorted(set(month_keys) - set(expected_by_month))

    runtime_failures: list[str] = []
    warnings: list[str] = []
    if len(status_paths) != len(expected_rows):
        runtime_failures.append(f"DISCLOSURE_MONTH_STATUS_COUNT_MISMATCH:{len(status_paths)}:{len(expected_rows)}")
    if duplicate_month_keys:
        runtime_failures.append(f"DUPLICATE_DISCLOSURE_MONTHS:{duplicate_month_keys}")
    if missing_month_keys:
        runtime_failures.append(f"MISSING_DISCLOSURE_MONTHS:{missing_month_keys}")
    if unexpected_month_keys:
        runtime_failures.append(f"UNEXPECTED_DISCLOSURE_MONTHS:{unexpected_month_keys}")

    records: list[dict[str, Any]] = []
    month_status: list[dict[str, Any]] = []
    completed_month_keys: list[str] = []
    for status in statuses:
        month_key = str(status.get("month_key", ""))
        month_status.append(status)
        if status.get("program_id") != "FMDL-5D-R1.2":
            runtime_failures.append(f"DISCLOSURE_MONTH_PROGRAM_MISMATCH:{month_key}:{status.get('program_id')}")
        if status.get("source_release_id") != source_decision["release_id"]:
            runtime_failures.append(f"DISCLOSURE_MONTH_SOURCE_RELEASE_MISMATCH:{month_key}")
        expected = expected_by_month.get(month_key)
        if expected and (status.get("start_date") != expected["start_date"] or status.get("end_date") != expected["end_date"]):
            runtime_failures.append(f"DISCLOSURE_MONTH_RANGE_MISMATCH:{month_key}")
        if status.get("state") != "SUCCESS":
            runtime_failures.append(f"DISCLOSURE_MONTH_NOT_SUCCESS:{month_key}:{status.get('state')}")
        if int(status.get("completed_window_count", -1)) != int(status.get("expected_window_count", -2)):
            runtime_failures.append(f"DISCLOSURE_MONTH_WINDOW_COUNT_MISMATCH:{month_key}")
        if status.get("failed_windows"):
            runtime_failures.append(f"DISCLOSURE_MONTH_FAILED_WINDOWS:{month_key}:{len(status.get('failed_windows', []))}")
        warnings.extend(str(item) for item in status.get("warnings", []))

        safe_month = month_key.replace("-", "_")
        candidates = list(source.rglob(f"FMDL5D_R12_DISCLOSURE_MONTH_{safe_month}_RECORDS.json"))
        candidates = [path for path in candidates if "_WINDOW_" not in path.name]
        if len(candidates) != 1:
            runtime_failures.append(f"DISCLOSURE_MONTH_RECORD_FILE_COUNT_MISMATCH:{month_key}:{len(candidates)}")
        else:
            records.extend(read_json(candidates[0]))
        if status.get("state") == "SUCCESS":
            completed_month_keys.append(month_key)

    if warnings:
        runtime_failures.append(f"DISCLOSURE_MONTH_WARNINGS:{len(warnings)}")

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in records:
        key = (str(row.get("stock_code_5d", "")), str(row.get("news_id", "")), str(row.get("filing_url", "")))
        deduped[key] = row
    combined_records = sorted(deduped.values(), key=lambda row: row.get("release_timestamp", ""))

    combined_status = {
        "program_id": "FMDL-5D-R1.2",
        "stage": "HKEX_DISCLOSURE_MONTH_AGGREGATE",
        "generated_at_utc": now_utc(),
        "source_release_id": source_decision["release_id"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "expected_month_count": len(expected_rows),
        "completed_month_count": len(set(completed_month_keys)),
        "expected_monthly_chunk_count": len(expected_rows),
        "completed_monthly_chunk_count": len(set(completed_month_keys)),
        "accepted_financial_record_count": len(combined_records),
        "covered_security_count": len({row.get("stock_code_5d") for row in combined_records}),
        "warning_count": len(warnings),
        "warnings": warnings,
        "runtime_failures": sorted(set(runtime_failures)),
        "missing_month_keys": missing_month_keys,
        "unexpected_month_keys": unexpected_month_keys,
        "duplicate_month_keys": duplicate_month_keys,
        "month_status": sorted(month_status, key=lambda row: row.get("month_key", "")),
        "request_policy": "SINGLE_MONTH_JOB_WITH_WEEKLY_INCREMENTAL_CHECKPOINTS_AND_BOUNDED_REQUESTS",
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_R1_DISCLOSURES.json", combined_records)
    write_json(output / "FMDL5D_R1_DISCLOSURE_STATUS.json", combined_status)
    print(json.dumps(combined_status, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if runtime_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
