#!/usr/bin/env python3
"""Run the FMDL-2B-1 real historical-store pilot.

The pilot is deterministic, retry-aware and fail-closed. It writes only pilot
artifacts and never promotes a full-market history store or creates trade
permission.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import benchmark_historical_sources as base

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
CONFIG_PATH = ROOT / "config/fmdl2_history_store.json"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"
ROUTE_PATH = ROOT / "config/fmdl2_historical_source_routes.json"
OUTPUT_DIR = ROOT / "outputs/pilot/fmdl2b1"


def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_contracts() -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any], dict[str, Any]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    release = json.loads(CURRENT_RELEASE_PATH.read_text(encoding="utf-8"))
    route = json.loads(ROUTE_PATH.read_text(encoding="utf-8"))
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})

    if release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        raise RuntimeError("FMDL-1 Current is not published")
    if release.get("hard_failures"):
        raise RuntimeError("FMDL-1 Current contains hard failures")
    if route.get("status") != "ACTIVE_FOR_FMDL_2B_INITIAL_BACKFILL":
        raise RuntimeError("FMDL-2A source route is not active for initial backfill")
    if route["primary"]["provider_id"] != "sina_daily":
        raise RuntimeError("Pilot contract requires the accepted Sina primary route")
    return config, universe, release, route


def select_pilot_sample(universe: pd.DataFrame, config: dict[str, Any], as_of: date) -> pd.DataFrame:
    required = {"symbol", "board", "is_st", "is_suspended", "list_date"}
    missing = required.difference(universe.columns)
    if missing:
        raise RuntimeError(f"Universe missing pilot fields: {sorted(missing)}")

    quotas = config["pilot"]["board_quotas"]
    selected: list[pd.DataFrame] = []
    for board, quota in quotas.items():
        group = universe.loc[universe["board"] == board].copy()
        if len(group) < int(quota):
            raise RuntimeError(f"Board {board} has {len(group)} rows, below quota {quota}")
        list_dates = pd.to_datetime(group["list_date"], errors="coerce").dt.date
        recent_cutoff = as_of - timedelta(days=config["history_policy"]["seasoned_listing_calendar_days"])
        group["special_priority"] = (
            group["is_st"].astype(str).str.lower().eq("true").astype(int) * 4
            + group["is_suspended"].astype(str).str.lower().eq("true").astype(int) * 3
            + list_dates.map(lambda value: int(value is not None and value >= recent_cutoff)) * 2
            + list_dates.isna().astype(int)
        )
        group["stable_key"] = group["symbol"].map(stable_key)
        group = group.sort_values(["special_priority", "stable_key"], ascending=[False, True])
        selected.append(group.head(int(quota)).copy())

    sample = pd.concat(selected, ignore_index=True)
    sample["stable_key"] = sample["symbol"].map(stable_key)
    sample = sample.sort_values(["board", "stable_key"]).reset_index(drop=True)
    sample["sample_order"] = range(1, len(sample) + 1)
    shard_size = int(config["pilot"]["shard_size"])
    sample["shard_id"] = ((sample["sample_order"] - 1) // shard_size).map(lambda value: f"shard_{value:02d}")
    expected = int(config["pilot"]["sample_size"])
    if len(sample) != expected:
        raise RuntimeError(f"Pilot sample size {len(sample)} != expected {expected}")
    return sample


def source_call(
    provider_id: str,
    call: Callable[[str], pd.DataFrame],
    symbol: str,
    *,
    requested_end: date,
    attempts: int,
    timeout_seconds: int,
    backoff_seconds: list[float],
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    errors: list[str] = []
    total_latency = 0.0
    last_meta: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        try:
            frame, latency = base.timed_call(lambda: call(symbol), timeout_seconds)
            total_latency += latency
            normalized, meta = base.normalize_history(frame)
            last_meta = meta
            if normalized.empty:
                raise ValueError("normalized_history_empty")
            normalized = normalized.loc[normalized["date"].dt.date <= requested_end].copy()
            if normalized.empty:
                raise ValueError("no_rows_at_or_before_as_of")
            return normalized, {
                "provider_id": provider_id,
                "attempts": attempt,
                "errors": errors,
                "latency_seconds": round(total_latency, 4),
                **meta,
            }
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:1000])
            if attempt < attempts:
                delay = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)] if backoff_seconds else 1.5
                time.sleep(float(delay))
    return None, {
        "provider_id": provider_id,
        "attempts": attempts,
        "errors": errors,
        "latency_seconds": round(total_latency, 4),
        **last_meta,
    }


def canonicalize_history(
    normalized: pd.DataFrame,
    *,
    symbol: str,
    provider_id: str,
    retrieved_at: str,
) -> pd.DataFrame:
    function = "stock_zh_a_daily" if provider_id == "sina_daily" else "stock_zh_a_hist_tx"
    quality = "VALID" if provider_id == "sina_daily" else "PARTIAL_FALLBACK_PRICE_AMOUNT"
    output = pd.DataFrame({
        "trade_date": normalized["date"].dt.date.map(str),
        "symbol": symbol,
        "open": pd.to_numeric(normalized["open"], errors="coerce"),
        "high": pd.to_numeric(normalized["high"], errors="coerce"),
        "low": pd.to_numeric(normalized["low"], errors="coerce"),
        "close": pd.to_numeric(normalized["close"], errors="coerce"),
        "volume_shares": pd.to_numeric(normalized["volume"], errors="coerce") if provider_id == "sina_daily" else math.nan,
        "turnover_cny": pd.to_numeric(normalized["amount"], errors="coerce"),
        "provider_id": provider_id,
        "source_function": function,
        "adjustment_mode": "qfq",
        "retrieved_at": retrieved_at,
        "record_quality": quality,
    })
    hashes: list[str] = []
    for row in output.to_dict(orient="records"):
        hashes.append(stable_hash(row))
    output["row_hash"] = hashes
    return output


def validate_series(frame: pd.DataFrame, as_of: date) -> tuple[bool, list[str], dict[str, int]]:
    reasons: list[str] = []
    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    future_rows = int((dates.dt.date > as_of).sum())
    duplicate_dates = int(dates.duplicated().sum())
    required_prices = frame[["open", "high", "low", "close"]].dropna()
    impossible_ohlc = int((
        (required_prices["high"] < required_prices[["open", "close", "low"]].max(axis=1))
        | (required_prices["low"] > required_prices[["open", "close", "high"]].min(axis=1))
        | (required_prices[["open", "high", "low", "close"]] <= 0).any(axis=1)
    ).sum())
    negative_volume = int((frame["volume_shares"].dropna() < 0).sum())
    negative_amount = int((frame["turnover_cny"].dropna() < 0).sum())
    if future_rows:
        reasons.append("FUTURE_ROWS")
    if duplicate_dates:
        reasons.append("DUPLICATE_DATES")
    if impossible_ohlc:
        reasons.append("IMPOSSIBLE_OHLC")
    if negative_volume:
        reasons.append("NEGATIVE_VOLUME")
    if negative_amount:
        reasons.append("NEGATIVE_AMOUNT")
    return not reasons, reasons, {
        "future_rows": future_rows,
        "duplicate_dates": duplicate_dates,
        "impossible_ohlc_rows": impossible_ohlc,
        "negative_volume_rows": negative_volume,
        "negative_amount_rows": negative_amount,
    }


def fetch_symbol(
    row: pd.Series,
    *,
    providers: dict[str, Callable[[str], pd.DataFrame]],
    config: dict[str, Any],
    as_of: date,
    retrieved_at: str,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    symbol = str(row["symbol"])
    board = str(row["board"])
    route = config["provider_route"]
    primary, primary_meta = source_call(
        "sina_daily", providers["sina_daily"], symbol,
        requested_end=as_of,
        attempts=int(route["primary_attempts"]),
        timeout_seconds=int(route["per_attempt_timeout_seconds"]),
        backoff_seconds=[float(item) for item in route["backoff_seconds"]],
    )
    selected = primary
    selected_meta = primary_meta
    fallback_used = False

    if primary is None and board in set(route["restricted_fallback_boards"]):
        fallback, fallback_meta = source_call(
            "tencent_hist", providers["tencent_hist"], symbol,
            requested_end=as_of,
            attempts=1,
            timeout_seconds=int(route["per_attempt_timeout_seconds"]),
            backoff_seconds=[],
        )
        if fallback is not None:
            selected = fallback
            selected_meta = fallback_meta
            fallback_used = True
        else:
            selected_meta = {
                "provider_id": "NONE",
                "attempts": int(primary_meta.get("attempts", 0)) + int(fallback_meta.get("attempts", 0)),
                "errors": [*primary_meta.get("errors", []), *fallback_meta.get("errors", [])],
                "latency_seconds": round(float(primary_meta.get("latency_seconds", 0)) + float(fallback_meta.get("latency_seconds", 0)), 4),
            }

    status: dict[str, Any] = {
        "symbol": symbol,
        "board": board,
        "list_date": row.get("list_date"),
        "is_st": row.get("is_st"),
        "is_suspended": row.get("is_suspended"),
        "shard_id": row["shard_id"],
        "provider_id": selected_meta.get("provider_id", "NONE"),
        "fallback_used": fallback_used,
        "attempts": selected_meta.get("attempts", 0),
        "latency_seconds": selected_meta.get("latency_seconds", 0),
        "source_errors": " | ".join(selected_meta.get("errors", [])),
        "state": "QUARANTINED",
        "quarantine_reason": None,
        "observation_count": 0,
        "first_valid_date": None,
        "latest_valid_date": None,
        "has_volume": False,
        "has_amount": False,
        "series_hash": None,
    }
    if selected is None:
        status["quarantine_reason"] = "ALL_ALLOWED_PROVIDERS_FAILED"
        return None, status

    canonical = canonicalize_history(
        selected, symbol=symbol, provider_id=str(selected_meta["provider_id"]), retrieved_at=retrieved_at
    )
    valid, reasons, counts = validate_series(canonical, as_of)
    status.update(counts)
    if not valid:
        status["quarantine_reason"] = ",".join(reasons)
        return None, status

    status.update({
        "state": "READY" if not fallback_used else "PARTIAL_FALLBACK_PRICE_AMOUNT",
        "observation_count": int(len(canonical)),
        "first_valid_date": str(canonical["trade_date"].min()),
        "latest_valid_date": str(canonical["trade_date"].max()),
        "has_volume": bool(canonical["volume_shares"].notna().any()),
        "has_amount": bool(canonical["turnover_cny"].notna().any()),
        "series_hash": stable_hash({"symbol": symbol, "row_hashes": canonical["row_hash"].tolist()}),
    })
    return canonical, status


def write_report(payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    lines = [
        "# FMDL-2B-1 Historical Store Pilot",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- As-of date: `{payload['as_of_date']}`",
        f"- Sample size: `{payload['sample_size']}`",
        f"- Usable symbols: `{metrics['usable_symbols']}` (`{metrics['usable_ratio']:.2%}`)",
        f"- Primary Sina symbols: `{metrics['primary_symbols']}`",
        f"- Restricted Tencent fallback symbols: `{metrics['fallback_symbols']}`",
        f"- Quarantined symbols: `{metrics['quarantined_symbols']}`",
        f"- Total normalized rows: `{metrics['history_rows']}`",
        f"- Parquet size: `{metrics['parquet_size_mib']:.2f} MiB`",
        f"- Projected 5,529-symbol store: `{metrics['projected_full_store_mib']:.2f} MiB`",
        f"- Runtime: `{metrics['runtime_minutes']:.2f} minutes`",
        f"- Pilot decision: `{payload['pilot_decision']}`",
        "",
        "## Board results",
        "",
        "| Board | Attempted | Usable | Ratio |",
        "|---|---:|---:|---:|",
    ]
    for board, result in metrics["board_results"].items():
        lines.append(f"| {board} | {result['attempted']} | {result['usable']} | {result['usable_ratio']:.2%} |")
    lines.extend([
        "",
        "## Recommended full-market design",
        "",
        f"- Storage: `{payload['recommendation']['storage_format']}` with `{payload['recommendation']['compression']}` compression",
        f"- Logical shards: `{payload['recommendation']['logical_shards']}`",
        f"- Symbols per shard: approximately `{payload['recommendation']['symbols_per_shard']}`",
        f"- Initial maximum parallel workers: `{payload['recommendation']['initial_max_workers']}`",
        f"- Estimated sequential full-backfill runtime: `{payload['recommendation']['estimated_sequential_full_runtime_minutes']:.1f} minutes`",
        "",
        "## Boundary",
        "",
        "This pilot validates storage and ingestion engineering only. It is not a full-market history release, factor table, stock rank, alpha claim or trade instruction.",
    ])
    (OUTPUT_DIR / "FMDL2B1_PILOT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pause-seconds", type=float, default=None)
    args = parser.parse_args()

    started = time.perf_counter()
    config, universe, release, _route = load_contracts()
    as_of = date.fromisoformat(release["as_of_date"])
    retrieved_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    run_id = datetime.now(tz=BUSINESS_TZ).strftime("FMDL2B1_PILOT_%Y%m%dT%H%M%S%z")
    sample = select_pilot_sample(universe, config, as_of)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    shard_dir = OUTPUT_DIR / "shards"
    quarantine_dir = OUTPUT_DIR / "quarantine"
    shard_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    sample.to_csv(OUTPUT_DIR / "PILOT_SAMPLE.csv", index=False, encoding="utf-8-sig")

    start = as_of - timedelta(days=int(config["history_policy"]["retrieval_calendar_days"]))
    provider_functions = base.provider_functions(start.strftime("%Y%m%d"), as_of.strftime("%Y%m%d"))
    if "sina_daily" not in provider_functions or "tencent_hist" not in provider_functions:
        raise RuntimeError("Installed AKShare does not expose accepted pilot provider functions")

    pause_seconds = float(config["pilot"]["pause_seconds"] if args.pause_seconds is None else args.pause_seconds)
    statuses: list[dict[str, Any]] = []
    total_parquet_bytes = 0
    total_history_rows = 0

    for shard_id, shard_sample in sample.groupby("shard_id", sort=True):
        shard_frames: list[pd.DataFrame] = []
        for _, row in shard_sample.iterrows():
            history, status = fetch_symbol(
                row, providers=provider_functions, config=config, as_of=as_of, retrieved_at=retrieved_at
            )
            statuses.append(status)
            if history is not None:
                shard_frames.append(history)
            else:
                (quarantine_dir / f"{row['symbol'].replace('.', '_')}.json").write_text(
                    json.dumps(status, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
                )
            time.sleep(pause_seconds)

        shard_frame = pd.concat(shard_frames, ignore_index=True) if shard_frames else pd.DataFrame()
        shard_path = shard_dir / f"{shard_id}.parquet"
        shard_frame.to_parquet(shard_path, index=False, compression=config["canonical_store"]["compression"])
        total_parquet_bytes += shard_path.stat().st_size
        total_history_rows += len(shard_frame)

    status_df = pd.DataFrame(statuses).sort_values(["board", "symbol"]).reset_index(drop=True)
    status_df.to_csv(OUTPUT_DIR / "PILOT_SYMBOL_STATUS.csv", index=False, encoding="utf-8-sig")
    usable_states = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}
    usable_mask = status_df["state"].isin(usable_states)
    board_results: dict[str, Any] = {}
    for board, group in status_df.groupby("board"):
        usable = int(group["state"].isin(usable_states).sum())
        board_results[str(board)] = {
            "attempted": int(len(group)),
            "usable": usable,
            "usable_ratio": round(usable / len(group), 6),
        }

    runtime_minutes = (time.perf_counter() - started) / 60.0
    usable_symbols = int(usable_mask.sum())
    sample_size = int(len(status_df))
    parquet_size_mib = total_parquet_bytes / (1024 * 1024)
    projected_full_store_mib = parquet_size_mib * len(universe) / max(1, sample_size)
    latencies = status_df.loc[usable_mask, "latency_seconds"].dropna().astype(float).tolist()
    median_latency = statistics.median(latencies) if latencies else 0.0
    projected_sequential = median_latency * len(universe) / 60.0

    gate = config["pilot_acceptance_gates"]
    hard_failures: list[str] = []
    if usable_symbols / sample_size < float(gate["minimum_usable_symbol_ratio"]):
        hard_failures.append("USABLE_RATIO_BELOW_GATE")
    if any(item["usable_ratio"] < float(gate["minimum_board_usable_ratio"]) for item in board_results.values()):
        hard_failures.append("BOARD_USABLE_RATIO_BELOW_GATE")
    if int(status_df["future_rows"].fillna(0).sum()) > int(gate["maximum_future_rows"]):
        hard_failures.append("FUTURE_ROWS")
    if int(status_df["duplicate_dates"].fillna(0).sum()) > int(gate["maximum_duplicate_dates_after_normalization"]):
        hard_failures.append("DUPLICATE_DATES")
    if int(status_df["impossible_ohlc_rows"].fillna(0).sum()) > int(gate["maximum_impossible_ohlc_rows"]):
        hard_failures.append("IMPOSSIBLE_OHLC")
    if runtime_minutes > float(gate["maximum_runtime_minutes"]):
        hard_failures.append("RUNTIME_ABOVE_GATE")
    if projected_full_store_mib > float(gate["maximum_projected_full_store_mib"]):
        hard_failures.append("PROJECTED_STORE_SIZE_ABOVE_GATE")

    recommendation = {
        "storage_format": "PARQUET",
        "compression": config["canonical_store"]["compression"],
        "logical_shards": 24,
        "symbols_per_shard": math.ceil(len(universe) / 24),
        "initial_max_workers": 3 if median_latency <= 3 else 2,
        "estimated_sequential_full_runtime_minutes": round(projected_sequential, 2),
        "checkpoint_policy": "PER_SHARD_AND_PER_SYMBOL_STATUS",
        "resumability": "RETRY_ONLY_NON_USABLE_SYMBOLS",
    }
    payload = {
        "pilot_version": "1.0.0",
        "run_id": run_id,
        "generated_at": retrieved_at,
        "as_of_date": as_of.isoformat(),
        "current_run_id": release["run_id"],
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "sample_size": sample_size,
        "sample_sha256": hashlib.sha256((OUTPUT_DIR / "PILOT_SAMPLE.csv").read_bytes()).hexdigest(),
        "pilot_decision": "READY_FOR_FULL_MARKET_BACKFILL" if not hard_failures else "PILOT_REMEDIATION_REQUIRED",
        "hard_failures": hard_failures,
        "metrics": {
            "usable_symbols": usable_symbols,
            "usable_ratio": round(usable_symbols / sample_size, 6),
            "primary_symbols": int((status_df["state"] == "READY").sum()),
            "fallback_symbols": int((status_df["state"] == "PARTIAL_FALLBACK_PRICE_AMOUNT").sum()),
            "quarantined_symbols": int((status_df["state"] == "QUARANTINED").sum()),
            "history_rows": int(total_history_rows),
            "parquet_bytes": int(total_parquet_bytes),
            "parquet_size_mib": round(parquet_size_mib, 4),
            "projected_full_store_mib": round(projected_full_store_mib, 4),
            "runtime_minutes": round(runtime_minutes, 4),
            "median_symbol_latency_seconds": round(median_latency, 4),
            "future_rows": int(status_df["future_rows"].fillna(0).sum()),
            "duplicate_dates": int(status_df["duplicate_dates"].fillna(0).sum()),
            "impossible_ohlc_rows": int(status_df["impossible_ohlc_rows"].fillna(0).sum()),
            "board_results": board_results,
        },
        "recommendation": recommendation,
        "authority": "NO_FACTOR_RANK_NO_ALPHA_CLAIM_NO_TRADE_AUTHORITY",
    }
    (OUTPUT_DIR / "FMDL2B1_PILOT_REPORT.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    release_payload = {
        "release_type": "PILOT_ONLY_NOT_FULL_MARKET_CURRENT",
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "status": payload["pilot_decision"],
        "sample_size": sample_size,
        "usable_symbols": usable_symbols,
        "history_rows": total_history_rows,
        "hard_failures": hard_failures,
        "artifact_root": "outputs/pilot/fmdl2b1",
        "trade_authority": "NONE",
    }
    (OUTPUT_DIR / "PILOT_RELEASE.json").write_text(
        json.dumps(release_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_report(payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not hard_failures else 2


if __name__ == "__main__":
    sys.exit(main())
