#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from fmdl5d_core import is_financial_filing
from run_fmdl5d_disclosure_financial_store import _fetch_hkex_chunk, monthly_chunks, now_utc


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def fetch_one_chunk(start: date, end: date, retrieved_at: str) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InvestmentOS-FMDL5D-R1/1.0; research-data-pipeline)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    last_error = ""
    for attempt in range(1, 4):
        try:
            records = _fetch_hkex_chunk(session, start, end, retrieved_at)
            return {"start_date": start.isoformat(), "end_date": end.isoformat(), "records": records, "warning": ""}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}:{exc}"
            time.sleep(attempt * 2)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "records": [],
        "warning": f"HKEX_CHUNK_FAILED:{start}:{end}:{last_error}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--contract", default="config/fmdl5d_hkex_disclosure_financial_contract.json")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("FMDL5D_R1_DISCLOSURE_WORKERS", "4")))
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    source_decision = json.loads(Path(contract["source_release"]["decision_path"]).read_text(encoding="utf-8"))
    if source_decision.get("status") != contract["source_release"]["required_status"]:
        raise ValueError(f"SOURCE_RELEASE_NOT_ACCEPTED:{source_decision.get('status')}")

    overlay = pd.read_csv(contract["source_release"]["semantic_overlay_path"], dtype={"stock_code_5d": str})
    overlay["stock_code_5d"] = overlay["stock_code_5d"].astype(str).str.zfill(5)
    universe_codes = set(overlay["stock_code_5d"])
    prices = pd.read_parquet(contract["source_release"]["price_store_path"], columns=["observation_date"])
    trading_days = sorted(pd.to_datetime(prices["observation_date"], errors="coerce").dropna().dt.date.unique())
    market_max_date = max(trading_days)
    start_date = pd.Timestamp(args.start_date or contract["period_policy"]["default_start_date"]).date()
    chunks = monthly_chunks(start_date, market_max_date)
    retrieved_at = now_utc()

    completed: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(fetch_one_chunk, start, end, retrieved_at): (start, end) for start, end in chunks}
        for future in as_completed(futures):
            completed.append(future.result())

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    chunk_status: list[dict[str, Any]] = []
    for result in sorted(completed, key=lambda row: row["start_date"]):
        if result["warning"]:
            warnings.append(result["warning"])
        accepted = [
            row
            for row in result["records"]
            if row["stock_code_5d"] in universe_codes and is_financial_filing(row["title"], row["category"])
        ]
        records.extend(accepted)
        chunk_status.append(
            {
                "start_date": result["start_date"],
                "end_date": result["end_date"],
                "raw_record_count": len(result["records"]),
                "accepted_financial_record_count": len(accepted),
                "warning": result["warning"],
            }
        )

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in records:
        key = (row["stock_code_5d"], row.get("news_id", ""), row["filing_url"])
        deduped[key] = row
    records = sorted(deduped.values(), key=lambda row: row["release_timestamp"])

    write_json(output / "FMDL5D_R1_DISCLOSURES.json", records)
    status = {
        "program_id": "FMDL-5D-R1",
        "stage": "HKEX_DISCLOSURE_SCAN",
        "generated_at_utc": now_utc(),
        "source_release_id": source_decision["release_id"],
        "start_date": start_date.isoformat(),
        "end_date": market_max_date.isoformat(),
        "monthly_chunk_count": len(chunks),
        "completed_chunk_count": len(completed),
        "warning_count": len(warnings),
        "warnings": warnings,
        "accepted_financial_record_count": len(records),
        "covered_security_count": len({row["stock_code_5d"] for row in records}),
        "chunk_status": chunk_status,
        "trade_authority": "NONE",
    }
    write_json(output / "FMDL5D_R1_DISCLOSURE_STATUS.json", status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
