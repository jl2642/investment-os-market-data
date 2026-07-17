#!/usr/bin/env python3
"""Aggregate and validate all FMDL-2B-2 full-universe shard artifacts."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.run_full_backfill_shard import shard_for_symbol

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
PLAN_PATH = ROOT / "config/fmdl2_full_backfill_plan.json"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_hash(items: list[dict[str, Any]]) -> str:
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_artifact_dirs(incoming: Path) -> list[Path]:
    candidates = [path for path in incoming.rglob("shard_*_manifest.json")]
    return sorted({path.parent for path in candidates})


def write_report(payload: dict[str, Any], path: Path) -> None:
    metrics = payload["metrics"]
    lines = [
        "# FMDL-2B-2 Full-Universe Historical Backfill",
        "",
        f"- Release ID: `{payload['release_id']}`",
        f"- As-of date: `{payload['as_of_date']}`",
        f"- Attempted symbols: `{metrics['attempted_symbols']}`",
        f"- Usable symbols: `{metrics['usable_symbols']}` (`{metrics['usable_ratio']:.2%}`)",
        f"- Quarantined symbols: `{metrics['quarantined_symbols']}`",
        f"- History rows: `{metrics['history_rows']}`",
        f"- Base store size: `{metrics['base_store_size_mib']:.2f} MiB`",
        f"- Candidate status: `{payload['status']}`",
        f"- Hard failures: `{len(payload['hard_failures'])}`",
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
        "## Boundary",
        "",
        "This is a historical-store candidate only. It does not calculate production factors, rank securities, modify a candidate pool or create trade authority.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})
    current = json.loads(CURRENT_RELEASE_PATH.read_text(encoding="utf-8"))
    total_shards = int(plan["sharding"]["logical_shards"])
    as_of = date.fromisoformat(current["as_of_date"])
    incoming = Path(args.incoming)
    artifact_dirs = find_artifact_dirs(incoming)

    manifests: list[dict[str, Any]] = []
    status_frames: list[pd.DataFrame] = []
    source_files: list[tuple[Path, Path, dict[str, Any]]] = []
    hard_failures: list[str] = []

    if len(artifact_dirs) != total_shards:
        hard_failures.append(f"SHARD_MANIFEST_COUNT_{len(artifact_dirs)}_EXPECTED_{total_shards}")

    seen_shards: set[int] = set()
    for directory in artifact_dirs:
        manifest_paths = list(directory.glob("shard_*_manifest.json"))
        if len(manifest_paths) != 1:
            hard_failures.append(f"INVALID_MANIFEST_COUNT_{directory}")
            continue
        manifest_path = manifest_paths[0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shard_id = int(manifest["shard_id"])
        if shard_id in seen_shards:
            hard_failures.append(f"DUPLICATE_SHARD_{shard_id}")
            continue
        seen_shards.add(shard_id)
        if manifest.get("release_id") != args.release_id:
            hard_failures.append(f"RELEASE_ID_MISMATCH_SHARD_{shard_id}")
        if manifest.get("as_of_date") != as_of.isoformat():
            hard_failures.append(f"AS_OF_MISMATCH_SHARD_{shard_id}")
        history_path = directory / manifest["history_file"]
        status_path = directory / manifest["status_file"]
        if not history_path.exists() or file_hash(history_path) != manifest["history_sha256"]:
            hard_failures.append(f"HISTORY_HASH_MISMATCH_SHARD_{shard_id}")
        if not status_path.exists() or file_hash(status_path) != manifest["status_sha256"]:
            hard_failures.append(f"STATUS_HASH_MISMATCH_SHARD_{shard_id}")
        status = pd.read_csv(status_path, dtype={"symbol": str})
        status_frames.append(status)
        manifests.append(manifest)
        source_files.append((history_path, status_path, manifest))

    status_df = pd.concat(status_frames, ignore_index=True) if status_frames else pd.DataFrame()
    expected_symbols = set(universe["symbol"].astype(str))
    actual_symbols = set(status_df["symbol"].astype(str)) if not status_df.empty else set()
    if len(status_df) != len(universe):
        hard_failures.append(f"ATTEMPTED_ROW_COUNT_{len(status_df)}_EXPECTED_{len(universe)}")
    if status_df.get("symbol", pd.Series(dtype=str)).duplicated().any():
        hard_failures.append("DUPLICATE_SYMBOL_STATUS")
    if actual_symbols != expected_symbols:
        hard_failures.append(f"SYMBOL_SET_MISMATCH_MISSING_{len(expected_symbols-actual_symbols)}_EXTRA_{len(actual_symbols-expected_symbols)}")

    assignment_errors = 0
    if not status_df.empty:
        for row in status_df[["symbol", "assigned_shard"]].itertuples(index=False):
            if int(row.assigned_shard) != shard_for_symbol(str(row.symbol), total_shards):
                assignment_errors += 1
    if assignment_errors:
        hard_failures.append(f"SHARD_ASSIGNMENT_ERRORS_{assignment_errors}")

    usable_states = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}
    usable_mask = status_df["state"].isin(usable_states) if not status_df.empty else pd.Series(dtype=bool)
    usable_symbols = int(usable_mask.sum()) if not status_df.empty else 0
    attempted_symbols = int(len(status_df))
    usable_ratio = usable_symbols / attempted_symbols if attempted_symbols else 0.0
    gates = plan["quality_gates"]
    if usable_ratio < float(gates["hard_minimum_market_usable_ratio"]):
        hard_failures.append("MARKET_USABLE_RATIO_BELOW_HARD_MINIMUM")

    board_results: dict[str, Any] = {}
    if not status_df.empty:
        for board, group in status_df.groupby("board"):
            count = int(group["state"].isin(usable_states).sum())
            ratio = count / len(group)
            board_results[str(board)] = {"attempted": int(len(group)), "usable": count, "usable_ratio": round(ratio, 6)}
            if ratio < float(gates["minimum_board_usable_ratio"]):
                hard_failures.append(f"BOARD_USABLE_RATIO_BELOW_GATE_{board}")

    future_rows = int(status_df["future_rows"].fillna(0).sum()) if not status_df.empty else 0
    duplicate_dates = int(status_df["duplicate_dates"].fillna(0).sum()) if not status_df.empty else 0
    impossible_ohlc = int(status_df["impossible_ohlc_rows"].fillna(0).sum()) if not status_df.empty else 0
    if future_rows != 0:
        hard_failures.append("FUTURE_ROWS")
    if duplicate_dates != 0:
        hard_failures.append("DUPLICATE_DATES")
    if impossible_ohlc != 0:
        hard_failures.append("IMPOSSIBLE_OHLC")

    list_dates = pd.to_datetime(status_df.get("list_date"), errors="coerce").dt.date if not status_df.empty else pd.Series(dtype=object)
    seasoned_cutoff = as_of - timedelta(days=400)
    seasoned_mask = list_dates.map(lambda value: value is not None and pd.notna(value) and value <= seasoned_cutoff) if not status_df.empty else pd.Series(dtype=bool)
    seasoned_usable = status_df.loc[seasoned_mask & usable_mask] if not status_df.empty else pd.DataFrame()
    seasoned_target = int(gates["seasoned_listing_minimum_observations"])
    seasoned_qualified = int((seasoned_usable["observation_count"] >= seasoned_target).sum()) if not seasoned_usable.empty else 0
    seasoned_ratio = seasoned_qualified / len(seasoned_usable) if len(seasoned_usable) else 1.0
    if seasoned_ratio < float(gates["seasoned_listing_target_ratio"]):
        hard_failures.append("SEASONED_HISTORY_RATIO_BELOW_GATE")

    lineage_complete = float(status_df.loc[usable_mask, "provider_id"].notna().mean()) if usable_symbols else 0.0
    hash_complete = float(status_df.loc[usable_mask, "series_hash"].notna().mean()) if usable_symbols else 0.0
    if lineage_complete < float(gates["provider_lineage_complete_ratio"]):
        hard_failures.append("PROVIDER_LINEAGE_INCOMPLETE")
    if hash_complete < float(gates["series_hash_complete_ratio"]):
        hard_failures.append("SERIES_HASH_INCOMPLETE")

    base_root = ROOT / "datasets/history/base" / args.release_id
    candidate_root = ROOT / "outputs/history/candidate"
    if base_root.exists():
        shutil.rmtree(base_root)
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    (base_root / "shards").mkdir(parents=True, exist_ok=True)
    (base_root / "manifests").mkdir(parents=True, exist_ok=True)
    candidate_root.mkdir(parents=True, exist_ok=True)

    shard_entries: list[dict[str, Any]] = []
    total_bytes = 0
    total_rows = 0
    for history_path, status_path, manifest in sorted(source_files, key=lambda item: int(item[2]["shard_id"])):
        shard_id = int(manifest["shard_id"])
        target_history = base_root / "shards" / f"shard_{shard_id:02d}.parquet"
        target_manifest = base_root / "manifests" / f"shard_{shard_id:02d}_manifest.json"
        shutil.copy2(history_path, target_history)
        target_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_bytes += target_history.stat().st_size
        total_rows += int(manifest["history_rows"])
        shard_entries.append({
            "shard_id": shard_id,
            "path": str(target_history.relative_to(ROOT)),
            "sha256": file_hash(target_history),
            "rows": int(manifest["history_rows"]),
            "attempted_symbols": int(manifest["attempted_symbols"]),
            "usable_symbols": int(manifest["usable_symbols"]),
        })

    status_df.sort_values(["board", "symbol"]).to_csv(candidate_root / "HISTORICAL_SYMBOL_STATUS.csv", index=False, encoding="utf-8-sig")
    quarantine = status_df.loc[status_df["state"] == "QUARANTINED"].copy() if not status_df.empty else pd.DataFrame()
    quarantine.to_csv(candidate_root / "HISTORICAL_QUARANTINE.csv", index=False, encoding="utf-8-sig")

    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    quality = {
        "release_id": args.release_id,
        "as_of_date": as_of.isoformat(),
        "hard_failures": hard_failures,
        "controlled_warnings": ["QUARANTINED_SYMBOLS_PRESENT"] if len(quarantine) else [],
        "metrics": {
            "attempted_symbols": attempted_symbols,
            "usable_symbols": usable_symbols,
            "usable_ratio": round(usable_ratio, 6),
            "quarantined_symbols": int(len(quarantine)),
            "primary_symbols": int((status_df["state"] == "READY").sum()) if not status_df.empty else 0,
            "fallback_symbols": int((status_df["state"] == "PARTIAL_FALLBACK_PRICE_AMOUNT").sum()) if not status_df.empty else 0,
            "history_rows": total_rows,
            "base_store_bytes": total_bytes,
            "base_store_size_mib": round(total_bytes / (1024 * 1024), 4),
            "future_rows": future_rows,
            "duplicate_dates": duplicate_dates,
            "impossible_ohlc_rows": impossible_ohlc,
            "seasoned_usable_symbols": int(len(seasoned_usable)),
            "seasoned_qualified_symbols": seasoned_qualified,
            "seasoned_251_ratio": round(seasoned_ratio, 6),
            "provider_lineage_complete_ratio": round(lineage_complete, 6),
            "series_hash_complete_ratio": round(hash_complete, 6),
            "board_results": board_results,
        },
    }
    manifest_payload = {
        "manifest_version": "1.0.0",
        "release_id": args.release_id,
        "as_of_date": as_of.isoformat(),
        "generated_at": generated_at,
        "current_run_id": current["run_id"],
        "shard_count": len(shard_entries),
        "shards": shard_entries,
        "aggregate_sha256": aggregate_hash(shard_entries),
        "symbol_status_path": "outputs/history/candidate/HISTORICAL_SYMBOL_STATUS.csv",
        "symbol_status_sha256": file_hash(candidate_root / "HISTORICAL_SYMBOL_STATUS.csv"),
        "quarantine_path": "outputs/history/candidate/HISTORICAL_QUARANTINE.csv",
        "quarantine_sha256": file_hash(candidate_root / "HISTORICAL_QUARANTINE.csv"),
        "authority": "HISTORICAL_DATA_ONLY_NO_FACTOR_RANK_NO_TRADE_AUTHORITY",
    }
    status = "CANDIDATE_ACCEPTED_WITH_QUARANTINE" if not hard_failures else "CANDIDATE_REJECTED"
    release_payload = {
        "release_type": "FULL_MARKET_HISTORICAL_STORE_CANDIDATE",
        "release_id": args.release_id,
        "as_of_date": as_of.isoformat(),
        "generated_at": generated_at,
        "status": status,
        "hard_failures": hard_failures,
        "base_path": str(base_root.relative_to(ROOT)),
        "manifest_path": "outputs/history/candidate/HISTORICAL_STORE_MANIFEST.json",
        "quality_path": "outputs/history/candidate/HISTORICAL_STORE_QUALITY.json",
        "trade_authority": "NONE",
    }
    run_report = {
        "release_id": args.release_id,
        "as_of_date": as_of.isoformat(),
        "generated_at": generated_at,
        "status": status,
        "hard_failures": hard_failures,
        "metrics": quality["metrics"],
        "authority": "NO_FACTOR_RANK_NO_ALPHA_CLAIM_NO_TRADE_AUTHORITY",
    }
    (candidate_root / "HISTORICAL_STORE_QUALITY.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (candidate_root / "HISTORICAL_STORE_MANIFEST.json").write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (candidate_root / "HISTORICAL_STORE_RELEASE.json").write_text(json.dumps(release_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (candidate_root / "FMDL2B2_RUN_REPORT.json").write_text(json.dumps(run_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(run_report, candidate_root / "FMDL2B2_RUN_REPORT.md")
    print(json.dumps(run_report, ensure_ascii=False))
    return 0 if not hard_failures else 2


if __name__ == "__main__":
    sys.exit(main())
