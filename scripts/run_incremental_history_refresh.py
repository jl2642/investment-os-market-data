#!/usr/bin/env python3
"""Build an FMDL-2B-4 incremental composite-history candidate."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts import benchmark_historical_sources as source_base
from scripts.fmdl2b4_history import (
    ROOT,
    canonical_hash,
    component_entry,
    composite_metrics,
    latest_observations,
    load_current_manifest,
    read_json,
    relative_path,
    sha256_file,
)
from scripts.run_full_backfill_shard import shard_for_symbol
from scripts.run_history_pilot import fetch_symbol

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
CONFIG_PATH = ROOT / "config/fmdl2_incremental_refresh.json"
HISTORY_CONFIG_PATH = ROOT / "config/fmdl2_history_store.json"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
SNAPSHOT_PATH = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
BASE_STATUS_PATH = ROOT / "outputs/history/candidate/HISTORICAL_SYMBOL_STATUS.csv"
CURRENT_STATUS_PATH = ROOT / "outputs/history/current/HISTORY_CURRENT_STATUS.csv"
CANDIDATE_ROOT = ROOT / "outputs/history/refresh_candidate"


def stable_row_hash(row: dict[str, Any]) -> str:
    return canonical_hash(row)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _number(value: Any) -> float | None:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(converted):
        return None
    number = float(converted)
    return number if math.isfinite(number) else None


def load_status(root: Path = ROOT) -> pd.DataFrame:
    current = root / CURRENT_STATUS_PATH.relative_to(ROOT)
    path = current if current.exists() else root / BASE_STATUS_PATH.relative_to(ROOT)
    status = pd.read_csv(path, dtype={"symbol": str})
    if status["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_PRIOR_HISTORY_STATUS_SYMBOL")
    return status


def completed_sessions_between(start_date: str, end_date: str) -> list[str]:
    if start_date >= end_date:
        return []
    calendar = ak.tool_trade_date_hist_sina()
    if calendar is None or not isinstance(calendar, pd.DataFrame) or calendar.empty:
        raise RuntimeError("TRADING_CALENDAR_UNAVAILABLE")
    column = next((name for name in ("trade_date", "交易日", "date") if name in calendar.columns), None)
    if column is None:
        raise RuntimeError("TRADING_CALENDAR_DATE_COLUMN_MISSING")
    dates = pd.to_datetime(calendar[column], errors="coerce").dropna().dt.date
    lower = date.fromisoformat(start_date)
    upper = date.fromisoformat(end_date)
    return [item.isoformat() for item in dates if lower < item <= upper]


def continuity_passes(
    snapshot_row: pd.Series,
    prior_close: float,
    config: dict[str, Any],
) -> tuple[bool, float | None, float | None]:
    close = _number(snapshot_row.get("close"))
    pct_change = _number(snapshot_row.get("pct_change"))
    prev_close = _number(snapshot_row.get("prev_close"))
    expected_prior: float | None = None
    if close is not None and pct_change is not None and abs(1.0 + pct_change / 100.0) > 1e-12:
        expected_prior = close / (1.0 + pct_change / 100.0)
    elif prev_close is not None:
        expected_prior = prev_close
    if expected_prior is None:
        return False, None, None
    difference = abs(expected_prior - prior_close)
    tolerance = max(
        float(config["daily_fast_path"]["continuity_absolute_cny_tolerance"]),
        abs(prior_close) * float(config["daily_fast_path"]["continuity_relative_tolerance"]),
    )
    return difference <= tolerance, expected_prior, difference


def canonical_incremental_row(snapshot_row: pd.Series, generated_at: str, config: dict[str, Any]) -> dict[str, Any]:
    output = {
        "trade_date": str(snapshot_row["as_of_date"]),
        "symbol": str(snapshot_row["symbol"]),
        "open": _number(snapshot_row.get("open")),
        "high": _number(snapshot_row.get("high")),
        "low": _number(snapshot_row.get("low")),
        "close": _number(snapshot_row.get("close")),
        "volume_shares": _number(snapshot_row.get("volume_shares")),
        "turnover_cny": _number(snapshot_row.get("turnover_cny")),
        "provider_id": "sina_public_snapshot",
        "source_function": "stock_zh_a_spot",
        "adjustment_mode": config["daily_fast_path"]["snapshot_adjustment_mode"],
        "retrieved_at": generated_at,
        "record_quality": config["daily_fast_path"]["snapshot_record_quality"],
    }
    output["row_hash"] = stable_row_hash(output)
    return output


def validate_incremental_rows(frame: pd.DataFrame, as_of_date: str) -> list[str]:
    errors: list[str] = []
    if frame.empty:
        return errors
    if frame.duplicated(["symbol", "trade_date"]).any():
        errors.append("DUPLICATE_INCREMENTAL_SYMBOL_DATE")
    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    if dates.isna().any():
        errors.append("INVALID_INCREMENTAL_DATE")
    if (dates > pd.Timestamp(as_of_date)).any():
        errors.append("FUTURE_INCREMENTAL_ROW")
    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    valid = prices.dropna()
    impossible = (
        (valid <= 0).any(axis=1)
        | (valid["high"] < valid[["open", "close", "low"]].max(axis=1))
        | (valid["low"] > valid[["open", "close", "high"]].min(axis=1))
    )
    if impossible.any():
        errors.append(f"IMPOSSIBLE_INCREMENTAL_OHLC_{int(impossible.sum())}")
    return errors


def attempt_repairs(
    repair_symbols: list[str],
    universe: pd.DataFrame,
    *,
    as_of_date: str,
    generated_at: str,
    history_config: dict[str, Any],
    logical_shards: int,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    if not repair_symbols:
        return pd.DataFrame(), {}
    as_of = date.fromisoformat(as_of_date)
    start = as_of - timedelta(days=int(history_config["history_policy"]["retrieval_calendar_days"]))
    providers = source_base.provider_functions(start.strftime("%Y%m%d"), as_of.strftime("%Y%m%d"))
    universe_map = universe.set_index("symbol").to_dict(orient="index")
    frames: list[pd.DataFrame] = []
    outcomes: dict[str, dict[str, Any]] = {}
    for symbol in repair_symbols:
        row = {"symbol": symbol, **universe_map[symbol]}
        row["shard_id"] = f"shard_{shard_for_symbol(symbol, logical_shards):02d}"
        history, status = fetch_symbol(
            pd.Series(row),
            providers=providers,
            config=history_config,
            as_of=as_of,
            retrieved_at=generated_at,
        )
        outcomes[symbol] = status
        if history is not None:
            history = history.copy()
            history["record_quality"] = history["record_quality"].astype(str).map(
                lambda value: f"FULL_REPAIR_{value}"
            )
            frames.append(history)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), outcomes


def compact_deltas(
    entries: list[dict[str, Any]],
    *,
    run_id: str,
    target_date: str,
    output_root: Path,
    threshold: int,
) -> list[dict[str, Any]]:
    if len(entries) <= threshold:
        return entries
    frames = [pd.read_parquet(ROOT / item["path"]) for item in entries]
    compacted = pd.concat(frames, ignore_index=True)
    compacted["trade_date"] = pd.to_datetime(compacted["trade_date"], errors="coerce")
    compacted = compacted.sort_values(["symbol", "trade_date", "retrieved_at"])
    compacted = compacted.drop_duplicates(["symbol", "trade_date"], keep="last")
    compacted["trade_date"] = compacted["trade_date"].dt.date.astype(str)
    path = output_root / f"compacted_delta_{run_id}.parquet"
    compacted.to_parquet(path, index=False, compression="zstd")
    return [component_entry(path, as_of_date=target_date, row_count=len(compacted), kind="COMPACTED_DELTA")]


def build_candidate(root: Path = ROOT) -> dict[str, Any]:
    config = read_json(root / CONFIG_PATH.relative_to(ROOT))
    history_config = read_json(root / HISTORY_CONFIG_PATH.relative_to(ROOT))
    current_release = read_json(root / CURRENT_RELEASE_PATH.relative_to(ROOT))
    universe = pd.read_csv(root / UNIVERSE_PATH.relative_to(ROOT), dtype={"symbol": str})
    snapshot = pd.read_csv(root / SNAPSHOT_PATH.relative_to(ROOT), dtype={"symbol": str})
    prior_manifest = load_current_manifest(root)
    prior_status = load_status(root)

    target_date = str(current_release["as_of_date"])
    previous_date = str(prior_manifest["as_of_date"])
    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    run_id = datetime.now(tz=BUSINESS_TZ).strftime("FMDL2B4_%Y%m%dT%H%M%S%z")

    hard_failures: list[str] = []
    warnings: list[str] = []
    required_universe = {"symbol", "board", "list_date", "is_st", "is_suspended"}
    if required_universe.difference(universe.columns):
        hard_failures.append("UNIVERSE_SCHEMA_MISSING")
    if universe["symbol"].duplicated().any():
        hard_failures.append("DUPLICATE_UNIVERSE_SYMBOL")
    if set(snapshot["symbol"].astype(str)) != set(universe["symbol"].astype(str)):
        hard_failures.append("SNAPSHOT_UNIVERSE_SYMBOL_SET_MISMATCH")
    if set(snapshot["as_of_date"].astype(str)) != {target_date}:
        hard_failures.append("SNAPSHOT_AS_OF_MISMATCH")
    if current_release.get("hard_failures"):
        hard_failures.append("FMDL1_CURRENT_HAS_HARD_FAILURES")
    if hard_failures:
        raise RuntimeError(";".join(hard_failures))

    sessions = completed_sessions_between(previous_date, target_date)
    if target_date == previous_date:
        sessions = []
    elif sessions != [target_date]:
        hard_failures.append(f"MULTI_SESSION_GAP_{len(sessions)}")

    if CANDIDATE_ROOT.exists():
        shutil.rmtree(CANDIDATE_ROOT)
    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)

    if target_date == previous_date:
        report = {
            "run_id": run_id,
            "as_of_date": target_date,
            "previous_as_of_date": previous_date,
            "status": "NO_OP_ALREADY_CURRENT",
            "hard_failures": [],
            "controlled_warnings": [],
            "authority": "HISTORY_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
        }
        (CANDIDATE_ROOT / "FMDL2B4_HISTORY_REFRESH_REPORT.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report

    if hard_failures:
        quality = {
            "quality_version": "1.0.0",
            "run_id": run_id,
            "as_of_date": target_date,
            "previous_as_of_date": previous_date,
            "status": "FAIL",
            "hard_failures": hard_failures,
            "controlled_warnings": [],
            "current_preserved": True,
            "authority": "HISTORY_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
        }
        (CANDIDATE_ROOT / "HISTORY_REFRESH_QUALITY.json").write_text(
            json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        raise RuntimeError(";".join(hard_failures))

    latest = latest_observations(prior_manifest, root=root)
    latest_map = latest.set_index("symbol").to_dict(orient="index") if not latest.empty else {}
    prior_status_map = prior_status.set_index("symbol").to_dict(orient="index")
    universe_map = universe.set_index("symbol").to_dict(orient="index")
    snapshot_map = snapshot.set_index("symbol")
    logical_shards = int(prior_manifest["logical_shards"])

    repair_reasons: dict[str, str] = {}
    for symbol in universe["symbol"].astype(str):
        prior = prior_status_map.get(symbol, {})
        state = str(prior.get("refresh_state") or prior.get("state") or "UNKNOWN")
        if symbol not in latest_map:
            repair_reasons[symbol] = "NO_ACCEPTED_PRIOR_HISTORY"
        elif state in {"QUARANTINED", "REPAIR_REQUIRED", "BLOCKED"}:
            repair_reasons[symbol] = "PRIOR_QUARANTINE_RETRY"

    incremental_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    continuity_diagnostics: list[dict[str, Any]] = []
    for symbol in universe["symbol"].astype(str):
        urow = universe_map[symbol]
        srow = snapshot_map.loc[symbol]
        prior = latest_map.get(symbol)
        data_status = str(srow.get("data_status", "UNKNOWN"))
        status_payload = {
            "symbol": symbol,
            "board": str(urow["board"]),
            "list_date": urow.get("list_date"),
            "is_st": _as_bool(urow.get("is_st")),
            "is_suspended": _as_bool(urow.get("is_suspended")),
            "as_of_date": target_date,
            "previous_as_of_date": previous_date,
            "refresh_state": "QUARANTINED",
            "refresh_reason": None,
            "provider_id": str(prior.get("provider_id", "NONE")) if prior else "NONE",
            "latest_history_date": str(prior.get("trade_date")) if prior else None,
            "last_close": _number(prior.get("close")) if prior else None,
            "continuity_expected_prior": None,
            "continuity_difference": None,
        }
        if symbol in repair_reasons:
            status_payload["refresh_state"] = "REPAIR_REQUIRED"
            status_payload["refresh_reason"] = repair_reasons[symbol]
            status_rows.append(status_payload)
            continue
        if data_status != "TRADED":
            status_payload["refresh_state"] = "READY_SUSPENDED_NO_APPEND"
            status_payload["refresh_reason"] = f"SNAPSHOT_{data_status}"
            status_rows.append(status_payload)
            continue
        prior_close = _number(prior.get("close")) if prior else None
        if prior_close is None:
            repair_reasons[symbol] = "MISSING_PRIOR_CLOSE"
            status_payload["refresh_state"] = "REPAIR_REQUIRED"
            status_payload["refresh_reason"] = "MISSING_PRIOR_CLOSE"
            status_rows.append(status_payload)
            continue
        passes, expected_prior, difference = continuity_passes(srow, prior_close, config)
        status_payload["continuity_expected_prior"] = expected_prior
        status_payload["continuity_difference"] = difference
        continuity_diagnostics.append({
            "symbol": symbol,
            "prior_close": prior_close,
            "expected_prior": expected_prior,
            "difference": difference,
            "passes": passes,
        })
        if not passes:
            repair_reasons[symbol] = "QFQ_CONTINUITY_BREAK"
            status_payload["refresh_state"] = "REPAIR_REQUIRED"
            status_payload["refresh_reason"] = "QFQ_CONTINUITY_BREAK"
            status_rows.append(status_payload)
            continue
        row = canonical_incremental_row(srow, generated_at, config)
        incremental_rows.append(row)
        status_payload.update({
            "refresh_state": "READY_INCREMENTAL",
            "refresh_reason": None,
            "provider_id": row["provider_id"],
            "latest_history_date": target_date,
            "last_close": row["close"],
        })
        status_rows.append(status_payload)

    max_repairs = int(config["targeted_repair"]["maximum_automatic_repairs_per_run"])
    repair_symbols = sorted(repair_reasons)[:max_repairs]
    if len(repair_reasons) > max_repairs:
        warnings.append(f"REPAIR_CANDIDATES_ABOVE_AUTOMATIC_LIMIT_{len(repair_reasons)}")
    repair_frame, repair_outcomes = attempt_repairs(
        repair_symbols,
        universe,
        as_of_date=target_date,
        generated_at=generated_at,
        history_config=history_config,
        logical_shards=logical_shards,
    )
    repaired_symbols = set(repair_frame["symbol"].astype(str)) if not repair_frame.empty else set()
    status_frame = pd.DataFrame(status_rows).set_index("symbol")
    for symbol in repair_symbols:
        outcome = repair_outcomes.get(symbol, {})
        if symbol in repaired_symbols:
            series = repair_frame.loc[repair_frame["symbol"].astype(str) == symbol]
            status_frame.loc[symbol, "refresh_state"] = "REPAIRED_FULL_HISTORY"
            status_frame.loc[symbol, "refresh_reason"] = repair_reasons[symbol]
            status_frame.loc[symbol, "provider_id"] = str(outcome.get("provider_id", "UNKNOWN"))
            status_frame.loc[symbol, "latest_history_date"] = str(series["trade_date"].max())
            status_frame.loc[symbol, "last_close"] = float(series.sort_values("trade_date")["close"].iloc[-1])
        else:
            status_frame.loc[symbol, "refresh_state"] = "QUARANTINED"
            status_frame.loc[symbol, "refresh_reason"] = str(outcome.get("quarantine_reason") or repair_reasons[symbol])
    status_frame = status_frame.reset_index().sort_values(["board", "symbol"]).reset_index(drop=True)

    incremental = pd.DataFrame(incremental_rows)
    incremental_errors = validate_incremental_rows(incremental, target_date)
    hard_failures.extend(incremental_errors)
    data_root = root / config["composite_store"]["incremental_path"] / run_id
    repair_root = root / config["composite_store"]["repair_path"] / run_id
    data_root.mkdir(parents=True, exist_ok=True)
    repair_root.mkdir(parents=True, exist_ok=True)
    delta_entries = list(prior_manifest.get("delta_files", []))
    repair_entries = list(prior_manifest.get("repair_files", []))
    if not incremental.empty:
        delta_path = data_root / "daily_delta.parquet"
        incremental.to_parquet(delta_path, index=False, compression="zstd")
        delta_entries.append(component_entry(delta_path, as_of_date=target_date, row_count=len(incremental), kind="DAILY_DELTA"))
    if not repair_frame.empty:
        repair_path = repair_root / "full_series_repairs.parquet"
        repair_frame.to_parquet(repair_path, index=False, compression="zstd")
        repair_entries.append(component_entry(repair_path, as_of_date=target_date, row_count=len(repair_frame), kind="FULL_SERIES_REPAIR"))

    delta_entries = compact_deltas(
        delta_entries,
        run_id=run_id,
        target_date=target_date,
        output_root=data_root,
        threshold=int(config["composite_store"]["maximum_delta_files_before_compaction"]),
    )
    status_path = CANDIDATE_ROOT / "HISTORY_CURRENT_STATUS.csv"
    status_frame.to_csv(status_path, index=False, encoding="utf-8-sig")
    continuity_path = CANDIDATE_ROOT / "HISTORY_CONTINUITY_DIAGNOSTICS.csv"
    pd.DataFrame(continuity_diagnostics).to_csv(continuity_path, index=False, encoding="utf-8-sig")

    candidate_manifest = {
        "manifest_version": "1.0.0",
        "release_id": run_id,
        "generated_at": generated_at,
        "as_of_date": target_date,
        "previous_release_id": prior_manifest.get("release_id"),
        "previous_as_of_date": previous_date,
        "base_release_id": prior_manifest["base_release_id"],
        "base_manifest_path": prior_manifest["base_manifest_path"],
        "base_manifest_sha256": prior_manifest["base_manifest_sha256"],
        "logical_shards": logical_shards,
        "delta_files": delta_entries,
        "repair_files": repair_entries,
        "status_path": relative_path(status_path, root),
        "status_sha256": sha256_file(status_path),
        "continuity_diagnostics_path": relative_path(continuity_path, root),
        "continuity_diagnostics_sha256": sha256_file(continuity_path),
        "component_aggregate_sha256": canonical_hash([*delta_entries, *repair_entries]),
        "status": "CANDIDATE_BUILT",
        "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }
    manifest_path = CANDIDATE_ROOT / "HISTORY_CURRENT_MANIFEST.json"
    manifest_path.write_text(json.dumps(candidate_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = composite_metrics(candidate_manifest, root=root)
    traded_count = int((snapshot["data_status"].astype(str) == "TRADED").sum())
    accepted_current = int((status_frame["refresh_state"].isin(["READY_INCREMENTAL", "REPAIRED_FULL_HISTORY"])).sum())
    append_ratio = accepted_current / traded_count if traded_count else 1.0
    unresolved = int(status_frame["refresh_state"].isin(["QUARANTINED", "REPAIR_REQUIRED"]).sum())
    if append_ratio < float(config["daily_fast_path"]["minimum_market_append_ratio"]):
        hard_failures.append(f"MARKET_APPEND_RATIO_{append_ratio:.6f}_BELOW_GATE")
    if metrics["duplicate_symbol_date_rows"]:
        hard_failures.append("COMPOSITE_DUPLICATE_SYMBOL_DATE")
    if metrics["future_rows"]:
        hard_failures.append("COMPOSITE_FUTURE_ROWS")
    if metrics["impossible_ohlc_rows"]:
        hard_failures.append("COMPOSITE_IMPOSSIBLE_OHLC")
    if unresolved:
        warnings.append(f"UNRESOLVED_HISTORY_SYMBOLS_{unresolved}")
    repaired_count = int((status_frame["refresh_state"] == "REPAIRED_FULL_HISTORY").sum())
    suspended_count = int((status_frame["refresh_state"] == "READY_SUSPENDED_NO_APPEND").sum())
    if repaired_count:
        warnings.append(f"FULL_SERIES_REPAIRS_{repaired_count}")
    if suspended_count:
        warnings.append(f"SUSPENDED_NO_APPEND_{suspended_count}")

    quality = {
        "quality_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "as_of_date": target_date,
        "previous_as_of_date": previous_date,
        "status": "FAIL" if hard_failures else "PASS_WITH_WARNINGS" if warnings else "PASS",
        "hard_failures": hard_failures,
        "controlled_warnings": warnings,
        "metrics": {
            **metrics,
            "universe_symbols": int(len(universe)),
            "traded_snapshot_symbols": traded_count,
            "incremental_rows": int(len(incremental)),
            "repaired_symbols": repaired_count,
            "repair_rows": int(len(repair_frame)),
            "suspended_no_append": suspended_count,
            "unresolved_history_symbols": unresolved,
            "accepted_current_session_ratio": round(append_ratio, 8),
            "delta_file_count": len(delta_entries),
            "repair_file_count": len(repair_entries),
        },
        "current_preserved_on_failure": True,
        "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }
    quality_path = CANDIDATE_ROOT / "HISTORY_REFRESH_QUALITY.json"
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidate_manifest["quality_path"] = relative_path(quality_path, root)
    candidate_manifest["quality_sha256"] = sha256_file(quality_path)
    candidate_manifest["status"] = "CANDIDATE_PASS" if not hard_failures else "CANDIDATE_FAIL"
    manifest_path.write_text(json.dumps(candidate_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "report_version": "1.0.0",
        "run_id": run_id,
        "as_of_date": target_date,
        "previous_as_of_date": previous_date,
        "status": quality["status"],
        "metrics": quality["metrics"],
        "hard_failures": hard_failures,
        "controlled_warnings": warnings,
        "history_candidate_manifest": relative_path(manifest_path, root),
        "non_claims": [
            "NO_FACTOR_ALPHA_CLAIM",
            "NO_CANDIDATE_POOL_CHANGE",
            "NO_SIMULATION_OR_REAL_PORTFOLIO_CHANGE",
            "NO_TRADE_AUTHORITY",
        ],
        "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }
    (CANDIDATE_ROOT / "FMDL2B4_HISTORY_REFRESH_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    if hard_failures:
        raise RuntimeError(";".join(hard_failures))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    try:
        build_candidate(ROOT)
    except Exception as exc:
        print(f"FMDL-2B-4 history refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
