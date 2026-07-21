#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from fmdl5d_core import load_field_registry
from run_fmdl5d_disclosure_financial_store import fetch_security_financials, now_utc


def partition_rows(rows: list[dict[str, Any]], shard_index: int, shard_count: int) -> list[dict[str, Any]]:
    if shard_count <= 0:
        raise ValueError("SHARD_COUNT_MUST_BE_POSITIVE")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("SHARD_INDEX_OUT_OF_RANGE")
    ordered = sorted(rows, key=lambda row: (str(row.get("stock_code_5d", "")), str(row.get("security_id", ""))))
    return [row for position, row in enumerate(ordered) if position % shard_count == shard_index]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_raw_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    if rows:
        pd.DataFrame(rows).to_parquet(path, index=False)
    else:
        pd.DataFrame(columns=["raw_fact_id"]).to_parquet(path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--shard-index", required=True, type=int)
    parser.add_argument("--shard-count", required=True, type=int)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--registry", default="config/fmdl5d_hk_financial_field_registry.json")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("FMDL5D_R1_WORKERS", "8")))
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    registry, _ = load_field_registry(Path(args.registry))
    source_decision = json.loads(Path(contract["source_release"]["decision_path"]).read_text(encoding="utf-8"))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    overlay = pd.read_csv(contract["source_release"]["semantic_overlay_path"], dtype={"stock_code_5d": str})
    overlay["stock_code_5d"] = overlay["stock_code_5d"].astype(str).str.zfill(5)
    equity = overlay[overlay["security_type"].astype(str) == "COMMON_EQUITY"].to_dict(orient="records")
    selected = partition_rows(equity, args.shard_index, args.shard_count)
    start_date = pd.Timestamp(args.start_date or contract["period_policy"]["default_start_date"]).date()

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                fetch_security_financials,
                security,
                registry,
                start_date,
                int(contract["period_policy"]["maximum_periods_per_statement"]),
            ): security
            for security in selected
        }
        for future in as_completed(futures):
            security = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "security_id": security["security_id"],
                        "issuer_id": security["issuer_id"],
                        "stock_code_5d": security["stock_code_5d"],
                        "profile": "UNKNOWN",
                        "raw_rows": [],
                        "unmapped": [],
                        "periods": [],
                        "fiscal_year_end": None,
                        "latest_currency": None,
                        "indicator_error": "",
                        "statement_status": {"all": f"FAILED:{type(exc).__name__}:{exc}"},
                        "successful_statement_count": 0,
                        "source_hashes": {},
                    }
                )

    results.sort(key=lambda row: row["stock_code_5d"])
    raw_rows: list[dict[str, Any]] = []
    unmapped_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    for result in results:
        raw_rows.extend(result.get("raw_rows", []))
        unmapped_rows.extend(result.get("unmapped", []))
        metadata_rows.append({key: value for key, value in result.items() if key not in {"raw_rows", "unmapped"}})

    prefix = f"FMDL5D_R1_SHARD_{args.shard_index:02d}"
    write_raw_parquet(output / f"{prefix}_RAW.parquet", raw_rows)
    pd.DataFrame(unmapped_rows).to_csv(output / f"{prefix}_UNMAPPED.csv", index=False, encoding="utf-8-sig")
    write_json(output / f"{prefix}_RESULTS.json", metadata_rows)

    expected_ids = {row["security_id"] for row in selected}
    actual_ids = {row["security_id"] for row in metadata_rows}
    status = {
        "program_id": "FMDL-5D-R1",
        "stage": "STRUCTURED_FINANCIAL_SHARD",
        "generated_at_utc": now_utc(),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "selected_security_count": len(selected),
        "completed_security_count": len(metadata_rows),
        "missing_security_ids": sorted(expected_ids - actual_ids),
        "unexpected_security_ids": sorted(actual_ids - expected_ids),
        "structured_success_security_count": sum(row.get("successful_statement_count", 0) >= 2 for row in metadata_rows),
        "security_failure_count": sum(row.get("successful_statement_count", 0) < 2 for row in metadata_rows),
        "raw_fact_count": len(raw_rows),
        "unmapped_row_count": len(unmapped_rows),
        "source_release_id": source_decision["release_id"],
        "trade_authority": "NONE",
    }
    write_json(output / f"{prefix}_STATUS.json", status)
    return 2 if status["missing_security_ids"] or status["unexpected_security_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
