from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.fmdl3db_core import (
    AUTHORITY,
    TRADE_AUTHORITY,
    VALID_CAP_STATES,
    ROOT,
    build_symbol_result,
    create_manifest,
    load_json,
    sha256_file,
    shard_for_symbol,
    write_json,
)

TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3db_engine.json"

LEDGER_COLUMNS = [
    "symbol",
    "name",
    "exchange",
    "board",
    "source_effective_date",
    "price_as_of_date",
    "total_shares",
    "float_a_shares",
    "limited_a_shares",
    "change_reason",
    "eligibility_state",
    "selected_for_current",
    "raw_fields_json",
    "source_id",
    "source_adapter",
    "retrieved_at",
    "source_row_hash",
    "authority",
    "trade_authority",
]


def _load_inputs(config: dict):
    entry = load_json(ROOT / config["entry_gate"]["pointer_path"])
    if entry.get("status") != config["entry_gate"]["required_status"]:
        raise RuntimeError("FMDL-3D-A entry gate is not accepted")
    release_path = ROOT / config["market_inputs"]["current_release_path"]
    universe_path = ROOT / config["market_inputs"]["universe_path"]
    snapshot_path = ROOT / config["market_inputs"]["snapshot_path"]
    universe_manifest = load_json(ROOT / config["market_inputs"]["universe_manifest_path"])
    snapshot_manifest = load_json(ROOT / config["market_inputs"]["snapshot_manifest_path"])
    release = load_json(release_path)
    if release.get("hard_failures"):
        raise RuntimeError("FMDL-1 Current contains hard failures")
    if release.get("as_of_date") != universe_manifest.get("as_of_date"):
        raise RuntimeError("Universe manifest as-of does not match Current release")
    if release.get("as_of_date") != snapshot_manifest.get("as_of_date"):
        raise RuntimeError("Snapshot manifest as-of does not match Current release")
    if sha256_file(universe_path) != release["current_files"]["a_share_universe"]["sha256"]:
        raise RuntimeError("Universe file hash does not match Current release")
    if sha256_file(snapshot_path) != release["current_files"]["daily_market_snapshot"]["sha256"]:
        raise RuntimeError("Snapshot file hash does not match Current release")
    universe = pd.read_csv(universe_path, encoding="utf-8-sig", dtype={"symbol": str})
    snapshot = pd.read_csv(snapshot_path, encoding="utf-8-sig", dtype={"symbol": str})
    universe["symbol"] = universe["symbol"].astype(str)
    snapshot["symbol"] = snapshot["symbol"].astype(str)
    if len(universe) != int(universe_manifest["row_count"]):
        raise RuntimeError("Universe row count does not match manifest")
    if len(snapshot) != int(snapshot_manifest["row_count"]):
        raise RuntimeError("Snapshot row count does not match manifest")
    return entry, release, universe_manifest, snapshot_manifest, universe, snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_json(args.config)
    shard_id = int(args.shard_id)
    shard_count = int(config["sharding"]["shard_count"])
    if shard_id < 0 or shard_id >= shard_count:
        raise SystemExit(f"invalid shard id {shard_id}")

    entry, release, universe_manifest, snapshot_manifest, universe, snapshot = _load_inputs(config)
    universe["__shard_id"] = universe["symbol"].map(
        lambda value: shard_for_symbol(value, shard_count)
    )
    membership = universe[universe["__shard_id"] == shard_id].copy()
    membership = membership.sort_values("symbol").reset_index(drop=True)
    if membership.empty:
        raise RuntimeError(f"shard {shard_id:02d} has no members")

    output = ROOT / config["publication"]["shard_root"] / f"shard-{shard_id:02d}"
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    run_id = f"FMDL3DB_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}_S{shard_id:02d}"
    snapshot_groups = {
        symbol: frame.copy() for symbol, frame in snapshot.groupby("symbol", sort=False)
    }
    current_rows: list[dict] = []
    ledger_rows: list[dict] = []
    retry_rows: list[dict] = []

    def execute(record: dict):
        symbol = str(record["symbol"])
        return build_symbol_result(
            record,
            snapshot_groups.get(symbol, pd.DataFrame()),
            config,
            release["run_id"],
            release["dataset_versions"]["a_share_universe"],
            release["dataset_versions"]["daily_market_snapshot"],
        )

    workers = max(1, int(config["sharding"]["workers_per_shard"]))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(execute, record): str(record["symbol"])
            for record in membership.drop(columns=["__shard_id"]).to_dict(orient="records")
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                current, ledger, retry = future.result()
            except Exception as exc:
                security = membership[membership["symbol"] == symbol].iloc[0]
                current = {
                    "symbol": symbol,
                    "name": str(security.get("name") or symbol),
                    "exchange": str(security.get("exchange") or symbol.split(".")[-1]),
                    "board": str(security.get("board") or "UNKNOWN"),
                    "price_as_of_date": release["as_of_date"],
                    "price_source_timestamp": None,
                    "close": None,
                    "price_row_hash": None,
                    "price_record_quality": None,
                    "price_data_status": None,
                    "share_effective_date": None,
                    "total_shares": None,
                    "float_a_shares": None,
                    "limited_a_shares": None,
                    "total_market_cap_cny": None,
                    "float_market_cap_cny": None,
                    "share_source_id": None,
                    "share_source_row_hash": None,
                    "capitalization_state": "CONTROLLED_QUARANTINE",
                    "state_reason": "UNHANDLED_SYMBOL_RUNNER_EXCEPTION",
                    "attempt_count": 0,
                    "source_error_type": type(exc).__name__,
                    "source_error_message": str(exc)[:1000],
                    "provider_row_count": 0,
                    "normalized_ledger_row_count": 0,
                    "invalid_source_row_count": 0,
                    "future_share_row_count": 0,
                    "universe_row_hash": None if pd.isna(security.get("row_hash")) else str(security.get("row_hash")),
                    "source_release_id": release["run_id"],
                    "source_universe_version": release["dataset_versions"]["a_share_universe"],
                    "source_snapshot_version": release["dataset_versions"]["daily_market_snapshot"],
                    "lineage_id": "0" * 64,
                    "authority": AUTHORITY,
                    "trade_authority": TRADE_AUTHORITY,
                }
                retry = {
                    "symbol": symbol,
                    "board": current["board"],
                    "attempt_count": 0,
                    "elapsed_seconds": 0.0,
                    "provider_row_count": 0,
                    "normalized_ledger_row_count": 0,
                    "invalid_source_row_count": 0,
                    "future_share_row_count": 0,
                    "capitalization_state": "CONTROLLED_QUARANTINE",
                    "source_error_type": type(exc).__name__,
                    "source_error_message": str(exc)[:1000],
                    "retrieved_at": datetime.now(TZ).isoformat(timespec="seconds"),
                    "authority": AUTHORITY,
                    "trade_authority": TRADE_AUTHORITY,
                }
                ledger = []
            current_rows.append(current)
            ledger_rows.extend(ledger)
            retry_rows.append(retry)

    current_frame = pd.DataFrame(current_rows).sort_values("symbol").reset_index(drop=True)
    ledger_frame = pd.DataFrame(ledger_rows, columns=LEDGER_COLUMNS)
    if len(ledger_frame):
        ledger_frame = ledger_frame.sort_values(
            ["symbol", "source_effective_date", "source_row_hash"]
        ).reset_index(drop=True)
    retry_frame = pd.DataFrame(retry_rows).sort_values("symbol").reset_index(drop=True)
    membership_export = membership.drop(columns=["__shard_id"]).copy()

    current_frame.to_parquet(output / "SHARD_CAPITALIZATION_CURRENT.parquet", index=False, compression="zstd")
    ledger_frame.to_parquet(output / "SHARD_EFFECTIVE_SHARE_LEDGER.parquet", index=False, compression="zstd")
    retry_frame.to_csv(output / "SHARD_RETRY_LEDGER.csv", index=False, encoding="utf-8-sig")
    membership_export.to_csv(output / "SHARD_MEMBERSHIP.csv", index=False, encoding="utf-8-sig")

    valid = current_frame[current_frame["capitalization_state"].isin(VALID_CAP_STATES)]
    selected_ledger = ledger_frame[ledger_frame["selected_for_current"].eq(True)] if len(ledger_frame) else ledger_frame
    replay_total = valid["close"] * valid["total_shares"]
    replay_float = valid["close"] * valid["float_a_shares"]
    acceptance = config["acceptance"]
    checks = {
        "ENTRY_GATE_ACCEPTED": entry.get("status") == config["entry_gate"]["required_status"],
        "MEMBERSHIP_KEYS_UNIQUE": not membership_export["symbol"].duplicated().any(),
        "CURRENT_EXACT_MEMBERSHIP": len(current_frame) == len(membership_export)
        and set(current_frame["symbol"]) == set(membership_export["symbol"]),
        "CURRENT_KEYS_UNIQUE": not current_frame["symbol"].duplicated().any(),
        "CURRENT_STATES_CONTROLLED": set(current_frame["capitalization_state"]).issubset(
            set(config["quality_states"])
        ),
        "VALID_ROWS_HAVE_COMPLETE_VALUES": valid[
            ["close", "share_effective_date", "total_shares", "float_a_shares", "total_market_cap_cny", "float_market_cap_cny", "share_source_row_hash"]
        ].notna().all().all(),
        "INVALID_ROWS_HAVE_NULL_CAPITALIZATION": current_frame[
            ~current_frame["capitalization_state"].isin(VALID_CAP_STATES)
        ][["total_market_cap_cny", "float_market_cap_cny"]].isna().all().all(),
        "ZERO_FUTURE_SELECTED_SHARE_ROWS": not selected_ledger[
            "eligibility_state"
        ].eq("FUTURE_EFFECTIVE").any() if len(selected_ledger) else True,
        "ZERO_NON_POSITIVE_SELECTED_SHARES": (
            (selected_ledger["total_shares"] > 0).all()
            and (selected_ledger["float_a_shares"] > 0).all()
        ) if len(selected_ledger) else True,
        "SELECTED_LEDGER_MATCHES_VALID_CURRENT": len(selected_ledger) == len(valid)
        and set(selected_ledger["source_row_hash"]) == set(valid["share_source_row_hash"]),
        "TOTAL_MARKET_CAP_REPLAYS": np.allclose(
            replay_total,
            valid["total_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "FLOAT_MARKET_CAP_REPLAYS": np.allclose(
            replay_float,
            valid["float_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "PRICE_AS_OF_MATCHES_RELEASE": set(current_frame["price_as_of_date"]) == {release["as_of_date"]},
        "SOURCE_RELEASE_MATCHES": set(current_frame["source_release_id"]) == {release["run_id"]},
        "ZERO_TRADE_AUTHORITY": set(current_frame["trade_authority"]) == {"NONE"}
        and (ledger_frame.empty or set(ledger_frame["trade_authority"]) == {"NONE"}),
    }
    failures = [key for key, passed in checks.items() if not bool(passed)]
    metrics = {
        "shard_id": f"{shard_id:02d}",
        "shard_count": shard_count,
        "membership_count": len(membership_export),
        "current_row_count": len(current_frame),
        "effective_share_ledger_row_count": len(ledger_frame),
        "valid_or_warning_count": len(valid),
        "valid_or_warning_ratio": float(len(valid) / len(current_frame)),
        "selected_share_row_count": len(selected_ledger),
        "source_failure_count": int(
            current_frame["capitalization_state"].eq("SHARE_SOURCE_UNAVAILABLE").sum()
        ),
        "controlled_quarantine_count": int(
            current_frame["capitalization_state"].eq("CONTROLLED_QUARANTINE").sum()
        ),
        "future_source_ledger_row_count": int(
            ledger_frame["eligibility_state"].eq("FUTURE_EFFECTIVE").sum()
        ) if len(ledger_frame) else 0,
        "invalid_source_row_count": int(retry_frame["invalid_source_row_count"].sum()),
        "maximum_attempt_count": int(retry_frame["attempt_count"].max()),
        "elapsed_source_seconds_sum": float(retry_frame["elapsed_seconds"].sum()),
    }
    decision = {
        "decision_version": "1.0.0",
        "run_id": run_id,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3D-B",
        "shard_id": f"{shard_id:02d}",
        "status": "FMDL3DB_SHARD_ACCEPTED" if not failures else "FMDL3DB_SHARD_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if passed else "FAIL"}
            for key, passed in checks.items()
        ],
        "metrics": metrics,
        "source_release_id": release["run_id"],
        "source_as_of_date": release["as_of_date"],
        "authority": AUTHORITY,
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(output / "SHARD_DECISION.json", decision)
    write_json(output / "SHARD_SOURCE_RELEASE.json", release)
    write_json(output / "SHARD_CONTRACT_SNAPSHOT.json", config)
    write_json(output / "SHARD_MANIFEST.json", create_manifest(output, run_id, "FMDL-3D-B-SHARD"))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
