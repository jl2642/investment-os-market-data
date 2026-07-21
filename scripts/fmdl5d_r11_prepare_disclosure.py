#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_fmdl5d_disclosure_financial_store import monthly_chunks, now_utc


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def chunk_key(start_date: str, end_date: str) -> tuple[str, str]:
    return start_date, end_date


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--expected-shards", type=int, default=12)
    parser.add_argument("--start-date", default="")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = read_json(Path(args.contract))
    source_decision = read_json(Path(contract["source_release"]["decision_path"]))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    prices = pd.read_parquet(contract["source_release"]["price_store_path"], columns=["observation_date"])
    trading_days = sorted(pd.to_datetime(prices["observation_date"], errors="coerce").dropna().dt.date.unique())
    market_max_date = max(trading_days)
    start_date = pd.Timestamp(args.start_date or contract["period_policy"]["default_start_date"]).date()
    expected_chunks = monthly_chunks(start_date, market_max_date)
    expected_chunk_keys = {chunk_key(start.isoformat(), end.isoformat()) for start, end in expected_chunks}

    status_paths = sorted(source.rglob("FMDL5D_R11_DISCLOSURE_SHARD_*_STATUS.json"))
    record_paths = sorted(source.rglob("FMDL5D_R11_DISCLOSURE_SHARD_*_RECORDS.json"))
    statuses = [read_json(path) for path in status_paths]
    records = [row for path in record_paths for row in read_json(path)]

    runtime_failures: list[str] = []
    if len(status_paths) != args.expected_shards:
        runtime_failures.append(f"DISCLOSURE_STATUS_COUNT_MISMATCH:{len(status_paths)}:{args.expected_shards}")
    if len(record_paths) != args.expected_shards:
        runtime_failures.append(f"DISCLOSURE_RECORD_COUNT_MISMATCH:{len(record_paths)}:{args.expected_shards}")

    shard_indices = [int(status.get("shard_index", -1)) for status in statuses]
    duplicate_shard_indices = sorted({index for index in shard_indices if shard_indices.count(index) > 1})
    missing_shard_indices = sorted(set(range(args.expected_shards)) - set(shard_indices))
    unexpected_shard_indices = sorted(set(shard_indices) - set(range(args.expected_shards)))
    if duplicate_shard_indices:
        runtime_failures.append(f"DUPLICATE_DISCLOSURE_SHARDS:{duplicate_shard_indices}")
    if missing_shard_indices:
        runtime_failures.append(f"MISSING_DISCLOSURE_SHARDS:{missing_shard_indices}")
    if unexpected_shard_indices:
        runtime_failures.append(f"UNEXPECTED_DISCLOSURE_SHARDS:{unexpected_shard_indices}")

    selected_chunk_keys: list[tuple[str, str]] = []
    completed_chunk_keys: list[tuple[str, str]] = []
    warnings: list[str] = []
    chunk_status: list[dict[str, Any]] = []
    for status in statuses:
        if status.get("source_release_id") != source_decision["release_id"]:
            runtime_failures.append(f"DISCLOSURE_SOURCE_RELEASE_MISMATCH:{status.get('shard_index')}")
        if int(status.get("shard_count", -1)) != args.expected_shards:
            runtime_failures.append(f"DISCLOSURE_SHARD_COUNT_MISMATCH:{status.get('shard_index')}")
        selected_chunk_keys.extend(
            chunk_key(item["start_date"], item["end_date"]) for item in status.get("selected_chunks", [])
        )
        completed_chunk_keys.extend(
            chunk_key(item["start_date"], item["end_date"]) for item in status.get("chunk_status", [])
        )
        warnings.extend(status.get("warnings", []))
        chunk_status.extend(status.get("chunk_status", []))

    selected_set = set(selected_chunk_keys)
    completed_set = set(completed_chunk_keys)
    duplicate_selected_chunks = sorted({key for key in selected_chunk_keys if selected_chunk_keys.count(key) > 1})
    duplicate_completed_chunks = sorted({key for key in completed_chunk_keys if completed_chunk_keys.count(key) > 1})
    missing_selected_chunks = sorted(expected_chunk_keys - selected_set)
    unexpected_selected_chunks = sorted(selected_set - expected_chunk_keys)
    missing_completed_chunks = sorted(expected_chunk_keys - completed_set)
    unexpected_completed_chunks = sorted(completed_set - expected_chunk_keys)

    if duplicate_selected_chunks:
        runtime_failures.append(f"DUPLICATE_SELECTED_DISCLOSURE_CHUNKS:{len(duplicate_selected_chunks)}")
    if duplicate_completed_chunks:
        runtime_failures.append(f"DUPLICATE_COMPLETED_DISCLOSURE_CHUNKS:{len(duplicate_completed_chunks)}")
    if missing_selected_chunks:
        runtime_failures.append(f"MISSING_SELECTED_DISCLOSURE_CHUNKS:{len(missing_selected_chunks)}")
    if unexpected_selected_chunks:
        runtime_failures.append(f"UNEXPECTED_SELECTED_DISCLOSURE_CHUNKS:{len(unexpected_selected_chunks)}")
    if missing_completed_chunks:
        runtime_failures.append(f"MISSING_COMPLETED_DISCLOSURE_CHUNKS:{len(missing_completed_chunks)}")
    if unexpected_completed_chunks:
        runtime_failures.append(f"UNEXPECTED_COMPLETED_DISCLOSURE_CHUNKS:{len(unexpected_completed_chunks)}")
    if warnings:
        runtime_failures.append(f"DISCLOSURE_CHUNK_WARNINGS:{len(warnings)}")

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in records:
        key = (str(row.get("stock_code_5d", "")), str(row.get("news_id", "")), str(row.get("filing_url", "")))
        deduped[key] = row
    combined_records = sorted(deduped.values(), key=lambda row: row.get("release_timestamp", ""))

    combined_status = {
        "program_id": "FMDL-5D-R1.1",
        "stage": "HKEX_DISCLOSURE_AGGREGATE",
        "generated_at_utc": now_utc(),
        "source_release_id": source_decision["release_id"],
        "start_date": start_date.isoformat(),
        "end_date": market_max_date.isoformat(),
        "expected_shard_count": args.expected_shards,
        "completed_shard_count": len(statuses),
        "expected_monthly_chunk_count": len(expected_chunk_keys),
        "selected_monthly_chunk_count": len(selected_set),
        "completed_monthly_chunk_count": len(completed_set),
        "accepted_financial_record_count": len(combined_records),
        "covered_security_count": len({row.get("stock_code_5d") for row in combined_records}),
        "warning_count": len(warnings),
        "warnings": warnings,
        "runtime_failures": sorted(set(runtime_failures)),
        "missing_shard_indices": missing_shard_indices,
        "missing_selected_chunks": missing_selected_chunks,
        "missing_completed_chunks": missing_completed_chunks,
        "chunk_status": sorted(chunk_status, key=lambda row: (row.get("start_date", ""), row.get("end_date", ""))),
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_R1_DISCLOSURES.json", combined_records)
    write_json(output / "FMDL5D_R1_DISCLOSURE_STATUS.json", combined_status)
    print(json.dumps(combined_status, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if runtime_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
