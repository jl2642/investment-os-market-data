#!/usr/bin/env python3
"""Run one deterministic FMDL-2B-2 full-universe history shard."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import benchmark_historical_sources as base
from scripts.run_history_pilot import fetch_symbol, stable_hash

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
PLAN_PATH = ROOT / "config/fmdl2_full_backfill_plan.json"
CONFIG_PATH = ROOT / "config/fmdl2_history_store.json"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"


def shard_for_symbol(symbol: str, total_shards: int) -> int:
    digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
    return int(digest, 16) % total_shards


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any]]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})
    release = json.loads(CURRENT_RELEASE_PATH.read_text(encoding="utf-8"))
    if plan.get("status") != "AUTHORIZED_FOR_FMDL_2B_2_IMPLEMENTATION":
        raise RuntimeError("Full-backfill plan is not authorized")
    if release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        raise RuntimeError("FMDL-1 Current is not published")
    if release.get("hard_failures"):
        raise RuntimeError("FMDL-1 Current contains hard failures")
    required = {"symbol", "board", "list_date", "is_st", "is_suspended"}
    missing = required.difference(universe.columns)
    if missing:
        raise RuntimeError(f"Universe missing full-backfill fields: {sorted(missing)}")
    return plan, config, universe, release


def series_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output-root", default="outputs/backfill/fmdl2b2")
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    args = parser.parse_args()

    started = time.perf_counter()
    plan, config, universe, release = load_inputs()
    total_shards = int(plan["sharding"]["logical_shards"])
    if args.shard_id < 0 or args.shard_id >= total_shards:
        raise ValueError(f"shard-id must be in [0,{total_shards - 1}]")

    universe = universe.copy()
    universe["assigned_shard"] = universe["symbol"].map(lambda value: shard_for_symbol(str(value), total_shards))
    shard = universe.loc[universe["assigned_shard"] == args.shard_id].copy()
    shard = shard.sort_values("symbol").reset_index(drop=True)
    shard["shard_id"] = f"shard_{args.shard_id:02d}"
    if shard.empty:
        raise RuntimeError(f"Shard {args.shard_id} has no symbols")

    output_root = ROOT / args.output_root / f"shard_{args.shard_id:02d}"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    quarantine_dir = output_root / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    as_of = date.fromisoformat(release["as_of_date"])
    retrieved_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    start = as_of - timedelta(days=int(config["history_policy"]["retrieval_calendar_days"]))
    providers = base.provider_functions(start.strftime("%Y%m%d"), as_of.strftime("%Y%m%d"))
    if "sina_daily" not in providers or "tencent_hist" not in providers:
        raise RuntimeError("Installed AKShare lacks accepted full-backfill providers")

    histories: list[pd.DataFrame] = []
    statuses: list[dict[str, Any]] = []
    for _, row in shard.iterrows():
        history, status = fetch_symbol(
            row,
            providers=providers,
            config=config,
            as_of=as_of,
            retrieved_at=retrieved_at,
        )
        status["release_id"] = args.release_id
        status["assigned_shard"] = args.shard_id
        for key in ("future_rows", "duplicate_dates", "impossible_ohlc_rows", "negative_volume_rows", "negative_amount_rows"):
            status.setdefault(key, 0)
        statuses.append(status)
        if history is not None:
            histories.append(history)
        else:
            quarantine_path = quarantine_dir / f"{str(row['symbol']).replace('.', '_')}.json"
            quarantine_path.write_text(
                json.dumps(status, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        time.sleep(max(0.0, args.pause_seconds))

    history_df = pd.concat(histories, ignore_index=True) if histories else pd.DataFrame()
    status_df = pd.DataFrame(statuses).sort_values(["board", "symbol"]).reset_index(drop=True)
    history_path = output_root / f"shard_{args.shard_id:02d}.parquet"
    status_path = output_root / f"shard_{args.shard_id:02d}_status.csv"
    history_df.to_parquet(history_path, index=False, compression=plan["storage"]["compression"])
    status_df.to_csv(status_path, index=False, encoding="utf-8-sig")

    usable_states = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}
    usable = status_df["state"].isin(usable_states)
    board_results: dict[str, Any] = {}
    for board, group in status_df.groupby("board"):
        count = int(group["state"].isin(usable_states).sum())
        board_results[str(board)] = {
            "attempted": int(len(group)),
            "usable": count,
            "usable_ratio": round(count / len(group), 6),
        }

    runtime_minutes = (time.perf_counter() - started) / 60.0
    manifest = {
        "manifest_version": "1.0.0",
        "release_id": args.release_id,
        "shard_id": args.shard_id,
        "shard_name": f"shard_{args.shard_id:02d}",
        "total_shards": total_shards,
        "assignment": plan["sharding"]["assignment"],
        "as_of_date": as_of.isoformat(),
        "current_run_id": release["run_id"],
        "generated_at": retrieved_at,
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "attempted_symbols": int(len(status_df)),
        "usable_symbols": int(usable.sum()),
        "quarantined_symbols": int((status_df["state"] == "QUARANTINED").sum()),
        "primary_symbols": int((status_df["state"] == "READY").sum()),
        "fallback_symbols": int((status_df["state"] == "PARTIAL_FALLBACK_PRICE_AMOUNT").sum()),
        "history_rows": int(len(history_df)),
        "future_rows": int(status_df["future_rows"].fillna(0).sum()),
        "duplicate_dates": int(status_df["duplicate_dates"].fillna(0).sum()),
        "impossible_ohlc_rows": int(status_df["impossible_ohlc_rows"].fillna(0).sum()),
        "runtime_minutes": round(runtime_minutes, 4),
        "board_results": board_results,
        "history_file": history_path.name,
        "history_sha256": series_file_hash(history_path),
        "status_file": status_path.name,
        "status_sha256": series_file_hash(status_path),
        "symbol_set_sha256": stable_hash({"symbols": sorted(status_df["symbol"].astype(str).tolist())}),
        "authority": "HISTORICAL_DATA_ONLY_NO_FACTOR_RANK_NO_TRADE_AUTHORITY",
    }
    manifest_path = output_root / f"shard_{args.shard_id:02d}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
