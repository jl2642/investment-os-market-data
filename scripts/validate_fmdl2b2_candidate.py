#!/usr/bin/env python3
"""Independently validate the committed FMDL-2B-2 historical candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pyarrow.parquet as pq

from scripts.run_full_backfill_shard import shard_for_symbol

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/history/candidate"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
PLAN_PATH = ROOT / "config/fmdl2_full_backfill_plan.json"
USABLE_STATES = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_hash(items: list[dict]) -> str:
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    release = json.loads((CANDIDATE / "HISTORICAL_STORE_RELEASE.json").read_text(encoding="utf-8"))
    manifest = json.loads((CANDIDATE / "HISTORICAL_STORE_MANIFEST.json").read_text(encoding="utf-8"))
    quality = json.loads((CANDIDATE / "HISTORICAL_STORE_QUALITY.json").read_text(encoding="utf-8"))
    report = json.loads((CANDIDATE / "FMDL2B2_RUN_REPORT.json").read_text(encoding="utf-8"))
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})
    status = pd.read_csv(CANDIDATE / "HISTORICAL_SYMBOL_STATUS.csv", dtype={"symbol": str})
    quarantine = pd.read_csv(CANDIDATE / "HISTORICAL_QUARANTINE.csv", dtype={"symbol": str})

    errors: list[str] = []
    release_id = str(release.get("release_id"))
    expected_shards = int(plan["sharding"]["logical_shards"])
    metrics = quality.get("metrics", {})

    if release.get("status") != "CANDIDATE_ACCEPTED_WITH_QUARANTINE":
        errors.append("RELEASE_NOT_ACCEPTED_WITH_QUARANTINE")
    if release.get("hard_failures") or quality.get("hard_failures") or report.get("hard_failures"):
        errors.append("HARD_FAILURES_PRESENT")
    if not (release_id == manifest.get("release_id") == quality.get("release_id") == report.get("release_id")):
        errors.append("RELEASE_ID_MISMATCH")
    if manifest.get("shard_count") != expected_shards or len(manifest.get("shards", [])) != expected_shards:
        errors.append("SHARD_COUNT_MISMATCH")

    if len(status) != len(universe):
        errors.append(f"STATUS_ROWS_{len(status)}_UNIVERSE_ROWS_{len(universe)}")
    if status["symbol"].duplicated().any():
        errors.append("DUPLICATE_STATUS_SYMBOL")
    if set(status["symbol"]) != set(universe["symbol"]):
        errors.append("STATUS_UNIVERSE_SYMBOL_SET_MISMATCH")

    usable = status["state"].isin(USABLE_STATES)
    if int(usable.sum()) != int(metrics.get("usable_symbols", -1)):
        errors.append("USABLE_SYMBOL_COUNT_MISMATCH")
    if int((status["state"] == "QUARANTINED").sum()) != int(metrics.get("quarantined_symbols", -1)):
        errors.append("QUARANTINE_COUNT_MISMATCH")
    if set(quarantine["symbol"]) != set(status.loc[status["state"] == "QUARANTINED", "symbol"]):
        errors.append("QUARANTINE_SYMBOL_SET_MISMATCH")

    shard_entries = sorted(manifest.get("shards", []), key=lambda item: int(item["shard_id"]))
    if [int(item["shard_id"]) for item in shard_entries] != list(range(expected_shards)):
        errors.append("SHARD_ID_SET_MISMATCH")

    total_rows = 0
    total_bytes = 0
    seen_symbols: set[str] = set()
    accepted_future_rows = 0
    accepted_duplicate_pairs = 0
    accepted_impossible_ohlc = 0
    required_columns = {
        "trade_date", "symbol", "open", "high", "low", "close", "volume_shares",
        "turnover_cny", "provider_id", "source_function", "adjustment_mode",
        "retrieved_at", "record_quality", "row_hash"
    }

    for entry in shard_entries:
        shard_id = int(entry["shard_id"])
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"MISSING_SHARD_{shard_id}")
            continue
        if sha256(path) != entry.get("sha256"):
            errors.append(f"SHARD_HASH_MISMATCH_{shard_id}")
        metadata_rows = int(pq.ParquetFile(path).metadata.num_rows)
        if metadata_rows != int(entry.get("rows", -1)):
            errors.append(f"SHARD_ROW_METADATA_MISMATCH_{shard_id}")
        total_rows += metadata_rows
        total_bytes += path.stat().st_size

        frame = pd.read_parquet(path)
        if not required_columns.issubset(frame.columns):
            errors.append(f"SHARD_SCHEMA_MISSING_COLUMNS_{shard_id}")
            continue
        if len(frame) != metadata_rows:
            errors.append(f"SHARD_READ_ROW_MISMATCH_{shard_id}")
        symbols = set(frame["symbol"].astype(str))
        if any(shard_for_symbol(symbol, expected_shards) != shard_id for symbol in symbols):
            errors.append(f"SHARD_ASSIGNMENT_ERROR_{shard_id}")
        if seen_symbols.intersection(symbols):
            errors.append(f"SYMBOL_PRESENT_IN_MULTIPLE_SHARDS_{shard_id}")
        seen_symbols.update(symbols)

        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        accepted_future_rows += int((dates > pd.Timestamp(release["as_of_date"])).sum())
        accepted_duplicate_pairs += int(frame.duplicated(["symbol", "trade_date"]).sum())
        prices = frame[["open", "high", "low", "close"]]
        valid_prices = prices.dropna()
        accepted_impossible_ohlc += int((
            (valid_prices["high"] < valid_prices[["open", "close", "low"]].max(axis=1))
            | (valid_prices["low"] > valid_prices[["open", "close", "high"]].min(axis=1))
            | (valid_prices <= 0).any(axis=1)
        ).sum())

    expected_usable_symbols = set(status.loc[usable, "symbol"].astype(str))
    if seen_symbols != expected_usable_symbols:
        errors.append(
            f"PARQUET_SYMBOL_SET_MISMATCH_MISSING_{len(expected_usable_symbols-seen_symbols)}_"
            f"EXTRA_{len(seen_symbols-expected_usable_symbols)}"
        )
    if total_rows != int(metrics.get("history_rows", -1)):
        errors.append("TOTAL_HISTORY_ROWS_MISMATCH")
    if total_bytes != int(metrics.get("base_store_bytes", -1)):
        errors.append("TOTAL_STORE_BYTES_MISMATCH")
    if aggregate_hash(shard_entries) != manifest.get("aggregate_sha256"):
        errors.append("AGGREGATE_HASH_MISMATCH")
    if accepted_future_rows:
        errors.append(f"ACCEPTED_FUTURE_ROWS_{accepted_future_rows}")
    if accepted_duplicate_pairs:
        errors.append(f"ACCEPTED_DUPLICATE_PAIRS_{accepted_duplicate_pairs}")
    if accepted_impossible_ohlc:
        errors.append(f"ACCEPTED_IMPOSSIBLE_OHLC_{accepted_impossible_ohlc}")

    validation = {
        "validation_version": "1.0.0",
        "release_id": release_id,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "metrics": {
            "universe_symbols": int(len(universe)),
            "status_symbols": int(len(status)),
            "usable_symbols": int(usable.sum()),
            "quarantined_symbols": int((status["state"] == "QUARANTINED").sum()),
            "shard_count": len(shard_entries),
            "history_rows": total_rows,
            "base_store_bytes": total_bytes,
            "accepted_future_rows": accepted_future_rows,
            "accepted_duplicate_pairs": accepted_duplicate_pairs,
            "accepted_impossible_ohlc_rows": accepted_impossible_ohlc,
        },
        "authority": "VALIDATION_ONLY_NO_FACTOR_RANK_NO_TRADE_AUTHORITY",
    }
    output = ROOT / "diagnostics/FMDL2B2_CANDIDATE_VALIDATION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
