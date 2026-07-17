#!/usr/bin/env python3
"""Build the FMDL-2B-3 full-market basic-factor candidate.

The engine consumes the accepted FMDL-2B-2 immutable history release and the
FMDL-1 Current interface. It calculates only factors frozen in
``config/fmdl2_factor_registry.json`` and publishes research-priority evidence
with no trade authority.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_OUTPUT = ROOT / "outputs/factors/candidate"
USABLE_HISTORY_STATES = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}
PUBLISHED_CURRENT_STATES = {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}

EXPECTED_FACTOR_IDS = {
    "return_20d", "return_60d", "return_120d", "return_250d", "momentum_250_20d",
    "distance_52w_high", "trend_consistency_60d", "positive_month_ratio_12m",
    "volatility_20d", "volatility_60d", "downside_volatility_60d",
    "max_drawdown_120d", "max_drawdown_250d", "worst_day_120d",
    "extreme_move_days_120d", "avg_turnover_cny_20d", "avg_turnover_cny_60d",
    "median_turnover_cny_60d", "turnover_stability_60d", "turnover_cv_60d",
    "volume_ratio_20_60d", "active_trade_ratio_60d", "suspension_days_20",
    "suspension_days_60", "zero_turnover_days_20", "zero_turnover_days_60",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def finite_or_none(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def load_contracts(root: Path = ROOT) -> dict[str, Any]:
    interface = read_json(root / "outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json")
    current = read_json(root / "outputs/current/CURRENT_RELEASE.json")
    factor_registry = read_json(root / "config/fmdl2_factor_registry.json")
    engine_config = read_json(root / "config/fmdl2_factor_engine.json")
    history_release = read_json(root / "outputs/history/candidate/HISTORICAL_STORE_RELEASE.json")
    history_manifest = read_json(root / "outputs/history/candidate/HISTORICAL_STORE_MANIFEST.json")

    errors: list[str] = []
    if interface.get("status") != "ACTIVE":
        errors.append("INTERFACE_NOT_ACTIVE")
    if current.get("status") not in PUBLISHED_CURRENT_STATES:
        errors.append("CURRENT_NOT_PUBLISHED")
    if current.get("hard_failures"):
        errors.append("CURRENT_HAS_HARD_FAILURES")
    if history_release.get("status") != "CANDIDATE_ACCEPTED_WITH_QUARANTINE":
        errors.append("HISTORY_RELEASE_NOT_ACCEPTED")
    if history_release.get("release_id") != history_manifest.get("release_id"):
        errors.append("HISTORY_RELEASE_ID_MISMATCH")
    if current.get("as_of_date") != history_release.get("as_of_date"):
        errors.append("CURRENT_HISTORY_AS_OF_MISMATCH")
    factor_ids = [item.get("factor_id") for item in factor_registry.get("factors", [])]
    if len(factor_ids) != len(set(factor_ids)):
        errors.append("DUPLICATE_FACTOR_ID")
    if set(factor_ids) != EXPECTED_FACTOR_IDS:
        errors.append("FACTOR_REGISTRY_IMPLEMENTATION_MISMATCH")
    if factor_registry.get("authority_boundary") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("FACTOR_AUTHORITY_BOUNDARY_MISMATCH")
    if engine_config.get("authority_boundary") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("ENGINE_AUTHORITY_BOUNDARY_MISMATCH")
    if errors:
        raise RuntimeError(";".join(errors))

    return {
        "interface": interface,
        "current": current,
        "factor_registry": factor_registry,
        "engine_config": engine_config,
        "history_release": history_release,
        "history_manifest": history_manifest,
    }


def validate_manifest_files(root: Path, manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    errors: list[str] = []
    entries = sorted(manifest.get("shards", []), key=lambda item: int(item["shard_id"]))
    if len(entries) != int(manifest.get("shard_count", -1)):
        errors.append("SHARD_COUNT_MISMATCH")
    for expected_id, entry in enumerate(entries):
        shard_id = int(entry["shard_id"])
        if shard_id != expected_id:
            errors.append(f"SHARD_SEQUENCE_ERROR_{shard_id}")
        path = root / str(entry["path"])
        if not path.exists():
            errors.append(f"MISSING_SHARD_{shard_id}")
            continue
        if sha256_file(path) != entry.get("sha256"):
            errors.append(f"SHARD_HASH_MISMATCH_{shard_id}")
        paths.append(path)
    if errors:
        raise RuntimeError(";".join(errors))
    return paths


def load_event_counts(path: Path, universe_symbols: set[str]) -> dict[str, int]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    frame = pd.read_csv(path, dtype=str)
    if frame.empty:
        return {}
    symbol_column = next(
        (name for name in ("symbol", "canonical_symbol", "security_id") if name in frame.columns),
        None,
    )
    if symbol_column is None:
        raise RuntimeError("MARKET_EVENT_FLAGS_MISSING_SYMBOL_COLUMN")
    symbols = frame[symbol_column].astype(str)
    unknown = set(symbols).difference(universe_symbols)
    if unknown:
        raise RuntimeError(f"MARKET_EVENT_FLAGS_UNKNOWN_SYMBOLS_{len(unknown)}")
    return symbols.value_counts().astype(int).to_dict()


def build_market_calendar(shard_paths: Iterable[Path], as_of_date: str) -> pd.DatetimeIndex:
    dates: list[pd.Series] = []
    as_of = pd.Timestamp(as_of_date)
    for path in shard_paths:
        frame = pd.read_parquet(path, columns=["trade_date"])
        parsed = pd.to_datetime(frame["trade_date"], errors="coerce")
        dates.append(parsed.loc[parsed.notna() & (parsed <= as_of)])
    if not dates:
        raise RuntimeError("NO_HISTORY_SHARDS_FOR_CALENDAR")
    calendar = pd.DatetimeIndex(pd.concat(dates, ignore_index=True).drop_duplicates().sort_values())
    if calendar.empty:
        raise RuntimeError("EMPTY_DERIVED_MARKET_CALENDAR")
    if calendar[-1] != as_of:
        raise RuntimeError(
            f"DERIVED_CALENDAR_LATEST_{calendar[-1].date()}_EXPECTED_{as_of.date()}"
        )
    return calendar


def trailing_expected_sessions(
    market_calendar: pd.DatetimeIndex,
    as_of: pd.Timestamp,
    list_date: pd.Timestamp | None,
    window: int,
) -> pd.DatetimeIndex:
    eligible = market_calendar[market_calendar <= as_of]
    if list_date is not None and not pd.isna(list_date):
        eligible = eligible[eligible >= list_date.normalize()]
    return eligible[-window:]


def board_extreme_threshold(board: str, is_st: bool, config: dict[str, Any]) -> float:
    if is_st:
        return float(config["extreme_move_thresholds"]["ST"])
    return float(config["extreme_move_thresholds"].get(board, config["extreme_move_thresholds"]["DEFAULT"]))


def _missing_factor(reason: str) -> tuple[None, str]:
    return None, reason


def compute_symbol_factor_values(
    history: pd.DataFrame | None,
    universe_row: dict[str, Any],
    status_row: dict[str, Any],
    factor_registry: dict[str, Any],
    engine_config: dict[str, Any],
    market_calendar: pd.DatetimeIndex,
    as_of_date: str,
    event_flag_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Calculate raw factors and per-factor availability for one symbol."""

    symbol = str(universe_row["symbol"])
    board = str(universe_row["board"])
    is_st = as_bool(universe_row.get("is_st"))
    is_suspended = as_bool(universe_row.get("is_suspended"))
    as_of = pd.Timestamp(as_of_date)
    list_date = pd.to_datetime(universe_row.get("list_date"), errors="coerce")
    list_date_value = None if pd.isna(list_date) else list_date
    history_state = str(status_row.get("state", "UNKNOWN"))

    base = {
        "as_of_date": as_of_date,
        "symbol": symbol,
        "board": board,
        "list_date": None if list_date_value is None else list_date_value.date().isoformat(),
        "is_st": is_st,
        "is_suspended": is_suspended,
        "event_flag_count": int(event_flag_count),
        "history_state": history_state,
        "history_observations": 0,
        "history_coverage_ratio_250": None,
        "history_start_date": None,
        "latest_history_date": None,
        "provider_id": str(status_row.get("provider_id") or "NONE"),
        "adjustment_mode": None,
        "factor_record_quality": "BLOCKED",
        "confidence_grade": "D",
        "available_factor_count": 0,
        "missing_factor_count": len(factor_registry["factors"]),
    }

    if history is None or history.empty or history_state not in USABLE_HISTORY_STATES:
        reason = "HISTORY_QUARANTINED" if history_state == "QUARANTINED" else "NO_ACCEPTED_HISTORY"
        detail = []
        for factor in factor_registry["factors"]:
            detail.append({
                **base,
                "factor_id": factor["factor_id"],
                "family": factor["family"],
                "direction": factor["direction"],
                "factor_value": None,
                "availability_flag": False,
                "missing_reason_code": reason,
            })
        return base, detail

    frame = history.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame = frame.loc[frame["trade_date"].notna() & (frame["trade_date"] <= as_of)].copy()
    frame = frame.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    close = pd.to_numeric(frame["close"], errors="coerce")
    valid_close = close.notna() & (close > 0)
    frame = frame.loc[valid_close].copy().reset_index(drop=True)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["turnover_cny"] = pd.to_numeric(frame.get("turnover_cny"), errors="coerce")
    frame["volume_shares"] = pd.to_numeric(frame.get("volume_shares"), errors="coerce")

    if frame.empty:
        return compute_symbol_factor_values(
            None, universe_row, {**status_row, "state": "QUARANTINED"}, factor_registry,
            engine_config, market_calendar, as_of_date, event_flag_count,
        )

    providers = sorted(set(frame["provider_id"].dropna().astype(str)))
    adjustments = sorted(set(frame["adjustment_mode"].dropna().astype(str)))
    provider_id = providers[0] if len(providers) == 1 else "MIXED"
    adjustment_mode = adjustments[0] if len(adjustments) == 1 else "MIXED"
    dates = pd.DatetimeIndex(frame["trade_date"])
    closes = frame["close"].astype(float).reset_index(drop=True)
    daily_returns = closes.pct_change(fill_method=None)
    turnovers = frame["turnover_cny"].astype(float).reset_index(drop=True)
    volumes = frame["volume_shares"].astype(float).reset_index(drop=True)

    expected_250 = trailing_expected_sessions(market_calendar, as_of, list_date_value, 250)
    coverage_denominator = len(expected_250)
    observed_250 = int(dates.isin(expected_250).sum()) if coverage_denominator else 0
    coverage = observed_250 / coverage_denominator if coverage_denominator else None

    base.update({
        "history_observations": int(len(frame)),
        "history_coverage_ratio_250": None if coverage is None else round(min(1.0, coverage), 8),
        "history_start_date": dates.min().date().isoformat(),
        "latest_history_date": dates.max().date().isoformat(),
        "provider_id": provider_id,
        "adjustment_mode": adjustment_mode,
    })

    values: dict[str, float | int | None] = {}
    reasons: dict[str, str | None] = {}

    def require_close(factor_id: str, minimum: int) -> bool:
        if len(closes) < minimum:
            values[factor_id], reasons[factor_id] = _missing_factor("INSUFFICIENT_HISTORY")
            return False
        return True

    def set_value(factor_id: str, value: Any, missing_reason: str = "NON_FINITE_RESULT") -> None:
        clean = finite_or_none(value)
        values[factor_id] = clean
        reasons[factor_id] = None if clean is not None else missing_reason

    for window in (20, 60, 120, 250):
        factor_id = f"return_{window}d"
        minimum = window + 1
        if require_close(factor_id, minimum):
            set_value(factor_id, closes.iloc[-1] / closes.iloc[-(window + 1)] - 1.0)
    if require_close("momentum_250_20d", 251):
        set_value("momentum_250_20d", closes.iloc[-21] / closes.iloc[-251] - 1.0)
    if require_close("distance_52w_high", 120):
        window_close = closes.iloc[-250:]
        set_value("distance_52w_high", closes.iloc[-1] / window_close.max() - 1.0)
    if require_close("trend_consistency_60d", 41):
        returns_60 = daily_returns.dropna().iloc[-60:]
        if returns_60.empty:
            values["trend_consistency_60d"], reasons["trend_consistency_60d"] = _missing_factor("NO_VALID_RETURNS")
        else:
            set_value("trend_consistency_60d", float((returns_60 > 0).mean()))
    if require_close("positive_month_ratio_12m", 120):
        block_returns: list[float] = []
        max_blocks = min(12, (len(closes) - 1) // 20)
        for block in range(max_blocks):
            end_position = len(closes) - 1 - block * 20
            start_position = end_position - 20
            block_returns.append(closes.iloc[end_position] / closes.iloc[start_position] - 1.0)
        if block_returns:
            set_value("positive_month_ratio_12m", sum(item > 0 for item in block_returns) / len(block_returns))
        else:
            values["positive_month_ratio_12m"], reasons["positive_month_ratio_12m"] = _missing_factor("NO_COMPLETE_20_SESSION_BLOCK")

    for window, minimum in ((20, 16), (60, 41)):
        factor_id = f"volatility_{window}d"
        if require_close(factor_id, minimum):
            returns_window = daily_returns.dropna().iloc[-window:]
            if len(returns_window) < 2:
                values[factor_id], reasons[factor_id] = _missing_factor("INSUFFICIENT_VALID_RETURNS")
            else:
                set_value(factor_id, returns_window.std(ddof=1) * math.sqrt(252.0))
    if require_close("downside_volatility_60d", 41):
        negative_returns = daily_returns.dropna().iloc[-60:]
        negative_returns = negative_returns.loc[negative_returns < 0]
        if len(negative_returns) < int(engine_config["minimum_negative_returns_for_downside_volatility"]):
            values["downside_volatility_60d"], reasons["downside_volatility_60d"] = _missing_factor("INSUFFICIENT_NEGATIVE_RETURNS")
        else:
            set_value("downside_volatility_60d", negative_returns.std(ddof=1) * math.sqrt(252.0))
    for window, minimum in ((120, 81), (250, 120)):
        factor_id = f"max_drawdown_{window}d"
        if require_close(factor_id, minimum):
            window_close = closes.iloc[-window:]
            drawdown = window_close / window_close.cummax() - 1.0
            set_value(factor_id, drawdown.min())
    if require_close("worst_day_120d", 81):
        returns_120 = daily_returns.dropna().iloc[-120:]
        if returns_120.empty:
            values["worst_day_120d"], reasons["worst_day_120d"] = _missing_factor("NO_VALID_RETURNS")
        else:
            set_value("worst_day_120d", returns_120.min())
    if require_close("extreme_move_days_120d", 81):
        threshold = board_extreme_threshold(board, is_st, engine_config)
        returns_120 = daily_returns.dropna().iloc[-120:]
        set_value("extreme_move_days_120d", int((returns_120.abs() > threshold).sum()))

    turnover_valid = turnovers.dropna()
    for window, minimum in ((20, 16), (60, 41)):
        factor_id = f"avg_turnover_cny_{window}d"
        sample = turnover_valid.iloc[-window:]
        if len(sample) < minimum:
            values[factor_id], reasons[factor_id] = _missing_factor("MISSING_OR_INSUFFICIENT_TURNOVER")
        else:
            set_value(factor_id, sample.mean())
    turnover_60 = turnover_valid.iloc[-60:]
    if len(turnover_60) < 41:
        for factor_id in ("median_turnover_cny_60d", "turnover_stability_60d", "turnover_cv_60d"):
            values[factor_id], reasons[factor_id] = _missing_factor("MISSING_OR_INSUFFICIENT_TURNOVER")
    else:
        turnover_mean = turnover_60.mean()
        turnover_median = turnover_60.median()
        set_value("median_turnover_cny_60d", turnover_median)
        if turnover_mean <= 0:
            for factor_id in ("turnover_stability_60d", "turnover_cv_60d"):
                values[factor_id], reasons[factor_id] = _missing_factor("NON_POSITIVE_MEAN_TURNOVER")
        else:
            set_value("turnover_stability_60d", min(1.0, max(0.0, turnover_median / turnover_mean)))
            set_value("turnover_cv_60d", turnover_60.std(ddof=1) / turnover_mean)
    volume_20 = volumes.dropna().iloc[-20:]
    volume_60 = volumes.dropna().iloc[-60:]
    if len(volume_60) < 41 or len(volume_20) < 16:
        values["volume_ratio_20_60d"], reasons["volume_ratio_20_60d"] = _missing_factor("MISSING_OR_INSUFFICIENT_VOLUME")
    elif volume_60.mean() <= 0:
        values["volume_ratio_20_60d"], reasons["volume_ratio_20_60d"] = _missing_factor("NON_POSITIVE_MEAN_VOLUME")
    else:
        set_value("volume_ratio_20_60d", volume_20.mean() / volume_60.mean())

    actual_dates = set(dates.normalize())
    for window in (20, 60):
        expected = trailing_expected_sessions(market_calendar, as_of, list_date_value, window)
        expected_set = set(expected.normalize())
        factor_id = f"suspension_days_{window}"
        if not expected_set:
            values[factor_id], reasons[factor_id] = _missing_factor("NO_EXPECTED_SESSIONS")
        else:
            set_value(factor_id, len(expected_set.difference(actual_dates)))

        zero_factor_id = f"zero_turnover_days_{window}"
        in_window = frame["trade_date"].isin(expected)
        traded_rows = frame.loc[in_window & (frame["close"] > 0)]
        if traded_rows.empty:
            values[zero_factor_id], reasons[zero_factor_id] = _missing_factor("NO_TRADED_ROWS_IN_WINDOW")
        elif traded_rows["turnover_cny"].notna().sum() == 0:
            values[zero_factor_id], reasons[zero_factor_id] = _missing_factor("MISSING_TURNOVER")
        else:
            set_value(zero_factor_id, int((traded_rows["turnover_cny"] == 0).sum()))

    expected_60 = trailing_expected_sessions(market_calendar, as_of, list_date_value, 60)
    if len(expected_60) < 41:
        values["active_trade_ratio_60d"], reasons["active_trade_ratio_60d"] = _missing_factor("INSUFFICIENT_EXPECTED_SESSIONS")
    else:
        in_window = frame["trade_date"].isin(expected_60)
        active = frame.loc[in_window, ["close", "turnover_cny"]]
        active_count = int(((active["close"] > 0) & (active["turnover_cny"] > 0)).sum())
        set_value("active_trade_ratio_60d", active_count / len(expected_60))

    missing_registry = EXPECTED_FACTOR_IDS.difference(values)
    if missing_registry:
        raise RuntimeError(f"UNIMPLEMENTED_FACTORS_{sorted(missing_registry)}")

    available_count = sum(value is not None for value in values.values())
    missing_count = len(values) - available_count
    latest_session = market_calendar[-1]
    latest_history = dates.max()
    stale_market_sessions = int((market_calendar > latest_history).sum())
    coverage_value = float(coverage or 0.0)

    if provider_id == "MIXED" or adjustment_mode != "qfq":
        quality = "SUSPECT"
        confidence = "D"
    elif stale_market_sessions > int(engine_config["suspect_stale_market_sessions"]) and not is_suspended:
        quality = "SUSPECT"
        confidence = "D"
    elif (
        missing_count > 0
        or is_suspended
        or event_flag_count > 0
        or history_state != "READY"
        or coverage_value < float(engine_config["valid_history_coverage_ratio_250"])
        or latest_history != latest_session
    ):
        quality = "PARTIAL"
        confidence = "B" if coverage_value >= float(engine_config["partial_confidence_coverage_ratio_250"]) else "C"
    else:
        quality = "VALID"
        confidence = "A"

    base.update({
        "factor_record_quality": quality,
        "confidence_grade": confidence,
        "available_factor_count": available_count,
        "missing_factor_count": missing_count,
    })

    detail: list[dict[str, Any]] = []
    registry_map = {item["factor_id"]: item for item in factor_registry["factors"]}
    for factor_id in sorted(EXPECTED_FACTOR_IDS):
        definition = registry_map[factor_id]
        value = values[factor_id]
        detail.append({
            **base,
            "factor_id": factor_id,
            "family": definition["family"],
            "direction": definition["direction"],
            "factor_value": value,
            "availability_flag": value is not None,
            "missing_reason_code": reasons[factor_id],
        })
    return base, detail


def add_cross_sectional_fields(detail: pd.DataFrame, engine_config: dict[str, Any]) -> pd.DataFrame:
    output = detail.copy()
    output["broad_market_percentile"] = math.nan
    output["board_neutral_percentile"] = math.nan
    output["winsorized_zscore"] = math.nan
    lower = float(engine_config["winsorization"]["lower_quantile"])
    upper = float(engine_config["winsorization"]["upper_quantile"])

    for _, group in output.groupby("factor_id", sort=True):
        eligible = group["availability_flag"].astype(bool) & pd.to_numeric(group["factor_value"], errors="coerce").notna()
        indexes = group.index[eligible]
        if indexes.empty:
            continue
        values = pd.to_numeric(output.loc[indexes, "factor_value"], errors="coerce")
        direction = str(group["direction"].iloc[0])
        ascending = direction != "LOWER_BETTER"
        output.loc[indexes, "broad_market_percentile"] = values.rank(
            method="average", pct=True, ascending=ascending
        )
        for _, board_group in output.loc[indexes].groupby("board", sort=True):
            board_values = pd.to_numeric(board_group["factor_value"], errors="coerce")
            output.loc[board_group.index, "board_neutral_percentile"] = board_values.rank(
                method="average", pct=True, ascending=ascending
            )
        lower_value = values.quantile(lower)
        upper_value = values.quantile(upper)
        winsorized = values.clip(lower=lower_value, upper=upper_value)
        std = winsorized.std(ddof=0)
        if pd.isna(std) or std == 0:
            zscore = pd.Series(0.0, index=indexes)
        else:
            zscore = (winsorized - winsorized.mean()) / std
        output.loc[indexes, "winsorized_zscore"] = zscore

    return output


def add_row_hashes(frame: pd.DataFrame, excluded: set[str] | None = None) -> pd.DataFrame:
    output = frame.copy()
    excluded = excluded or set()
    columns = [column for column in output.columns if column not in excluded and column != "row_hash"]
    hashes: list[str] = []
    for row in output[columns].to_dict(orient="records"):
        hashes.append(canonical_hash(row))
    output["row_hash"] = hashes
    return output


def build_wide_table(status: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    factor_values = detail.pivot(index="symbol", columns="factor_id", values="factor_value")
    broad = detail.pivot(index="symbol", columns="factor_id", values="broad_market_percentile")
    board = detail.pivot(index="symbol", columns="factor_id", values="board_neutral_percentile")
    zscores = detail.pivot(index="symbol", columns="factor_id", values="winsorized_zscore")
    factor_values.columns = [str(column) for column in factor_values.columns]
    broad.columns = [f"{column}__broad_pct" for column in broad.columns]
    board.columns = [f"{column}__board_pct" for column in board.columns]
    zscores.columns = [f"{column}__winsor_z" for column in zscores.columns]
    metadata = status.set_index("symbol")
    wide = metadata.join([factor_values, broad, board, zscores], how="left").reset_index()
    ordered_metadata = [
        "as_of_date", "symbol", "board", "list_date", "is_st", "is_suspended",
        "event_flag_count", "history_state", "history_observations",
        "history_coverage_ratio_250", "history_start_date", "latest_history_date",
        "provider_id", "adjustment_mode", "factor_record_quality", "confidence_grade",
        "available_factor_count", "missing_factor_count",
    ]
    remaining = sorted(column for column in wide.columns if column not in ordered_metadata)
    wide = wide[ordered_metadata + remaining]
    return add_row_hashes(wide)


def quality_payload(
    wide: pd.DataFrame,
    detail: pd.DataFrame,
    universe_count: int,
    as_of_date: str,
    history_release_id: str,
    factor_contract_version: str,
) -> dict[str, Any]:
    hard_failures: list[str] = []
    warnings: list[str] = []
    if len(wide) != universe_count:
        hard_failures.append(f"WIDE_ROWS_{len(wide)}_EXPECTED_{universe_count}")
    if wide["symbol"].duplicated().any():
        hard_failures.append("DUPLICATE_WIDE_SYMBOL")
    expected_detail_rows = universe_count * len(EXPECTED_FACTOR_IDS)
    if len(detail) != expected_detail_rows:
        hard_failures.append(f"DETAIL_ROWS_{len(detail)}_EXPECTED_{expected_detail_rows}")
    if detail.duplicated(["symbol", "factor_id"]).any():
        hard_failures.append("DUPLICATE_SYMBOL_FACTOR")
    if set(wide["as_of_date"].astype(str)) != {as_of_date}:
        hard_failures.append("WIDE_AS_OF_MISMATCH")
    if set(detail["as_of_date"].astype(str)) != {as_of_date}:
        hard_failures.append("DETAIL_AS_OF_MISMATCH")
    blocked_count = int((wide["factor_record_quality"] == "BLOCKED").sum())
    if blocked_count:
        warnings.append(f"CONTROLLED_BLOCKED_SYMBOLS_{blocked_count}")
    partial_count = int((wide["factor_record_quality"] == "PARTIAL").sum())
    suspect_count = int((wide["factor_record_quality"] == "SUSPECT").sum())
    if partial_count:
        warnings.append(f"PARTIAL_FACTOR_RECORDS_{partial_count}")
    if suspect_count:
        warnings.append(f"SUSPECT_FACTOR_RECORDS_{suspect_count}")

    coverage: dict[str, Any] = {}
    for factor_id, group in detail.groupby("factor_id", sort=True):
        available = int(group["availability_flag"].astype(bool).sum())
        coverage[str(factor_id)] = {
            "available_symbols": available,
            "missing_symbols": int(len(group) - available),
            "coverage_ratio": round(available / len(group), 8) if len(group) else 0.0,
        }

    return {
        "quality_version": "1.0.0",
        "status": "PASS" if not hard_failures and not warnings else "PASS_WITH_WARNINGS" if not hard_failures else "FAIL",
        "as_of_date": as_of_date,
        "history_release_id": history_release_id,
        "factor_contract_version": factor_contract_version,
        "hard_failures": hard_failures,
        "controlled_warnings": warnings,
        "metrics": {
            "universe_symbols": int(universe_count),
            "wide_rows": int(len(wide)),
            "detail_rows": int(len(detail)),
            "factor_count": len(EXPECTED_FACTOR_IDS),
            "valid_symbols": int((wide["factor_record_quality"] == "VALID").sum()),
            "partial_symbols": partial_count,
            "suspect_symbols": suspect_count,
            "blocked_symbols": blocked_count,
            "available_factor_values": int(detail["availability_flag"].astype(bool).sum()),
            "missing_factor_values": int((~detail["availability_flag"].astype(bool)).sum()),
        },
        "factor_coverage": coverage,
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }


def write_outputs(
    output_dir: Path,
    wide: pd.DataFrame,
    detail: pd.DataFrame,
    status: pd.DataFrame,
    quality: dict[str, Any],
    contracts: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    wide_path = output_dir / "BASIC_FACTOR_TABLE.parquet"
    detail_path = output_dir / "BASIC_FACTOR_DETAIL.parquet"
    status_path = output_dir / "BASIC_FACTOR_STATUS.csv"
    quality_path = output_dir / "BASIC_FACTOR_QUALITY.json"
    report_path = output_dir / "FMDL2B3_RUN_REPORT.json"

    wide.to_parquet(wide_path, index=False, compression="zstd")
    detail.to_parquet(detail_path, index=False, compression="zstd")
    status.to_csv(status_path, index=False, encoding="utf-8-sig")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "report_version": "1.0.0",
        "run_id": f"FMDL2B3_{generated_at.replace(':', '').replace('-', '')}",
        "generated_at": generated_at,
        "as_of_date": contracts["current"]["as_of_date"],
        "history_release_id": contracts["history_release"]["release_id"],
        "factor_contract_version": contracts["factor_registry"]["contract_version"],
        "status": quality["status"],
        "metrics": quality["metrics"],
        "hard_failures": quality["hard_failures"],
        "controlled_warnings": quality["controlled_warnings"],
        "non_claims": [
            "NO_FACTOR_ALPHA_CLAIM",
            "NO_LIVE_CANDIDATE_POOL_PROMOTION",
            "NO_SIMULATION_OR_REAL_PORTFOLIO_CHANGE",
            "NO_TRADE_AUTHORITY",
        ],
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    artifacts = []
    for dataset_id, path, rows in (
        ("basic_factor_table", wide_path, len(wide)),
        ("basic_factor_detail", detail_path, len(detail)),
        ("basic_factor_status", status_path, len(status)),
        ("basic_factor_quality", quality_path, 1),
        ("fmdl2b3_run_report", report_path, 1),
    ):
        artifacts.append({
            "dataset_id": dataset_id,
            "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": sha256_file(path),
            "row_count": int(rows),
            "bytes": path.stat().st_size,
        })

    manifest = {
        "manifest_version": "1.0.0",
        "run_id": report["run_id"],
        "generated_at": generated_at,
        "as_of_date": report["as_of_date"],
        "history_release_id": report["history_release_id"],
        "history_manifest_sha256": sha256_file(ROOT / "outputs/history/candidate/HISTORICAL_STORE_MANIFEST.json"),
        "factor_contract_version": report["factor_contract_version"],
        "factor_registry_sha256": sha256_file(ROOT / "config/fmdl2_factor_registry.json"),
        "factor_count": len(EXPECTED_FACTOR_IDS),
        "universe_symbols": int(len(wide)),
        "artifacts": artifacts,
        "aggregate_sha256": canonical_hash(artifacts),
        "status": "CANDIDATE_GENERATED" if not quality["hard_failures"] else "CANDIDATE_REJECTED",
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }
    manifest_path = output_dir / "BASIC_FACTOR_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(root: Path = ROOT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    contracts = load_contracts(root)
    as_of_date = str(contracts["current"]["as_of_date"])
    shard_paths = validate_manifest_files(root, contracts["history_manifest"])
    universe = pd.read_csv(root / "outputs/current/A_SHARE_UNIVERSE.csv", dtype={"symbol": str})
    required_universe = {"symbol", "board", "list_date", "is_st", "is_suspended"}
    missing_universe = required_universe.difference(universe.columns)
    if missing_universe:
        raise RuntimeError(f"UNIVERSE_MISSING_COLUMNS_{sorted(missing_universe)}")
    if universe["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_UNIVERSE_SYMBOL")
    history_status = pd.read_csv(
        root / "outputs/history/candidate/HISTORICAL_SYMBOL_STATUS.csv", dtype={"symbol": str}
    )
    if history_status["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_HISTORY_STATUS_SYMBOL")
    if set(history_status["symbol"]) != set(universe["symbol"]):
        raise RuntimeError("HISTORY_STATUS_UNIVERSE_MISMATCH")

    universe_symbols = set(universe["symbol"].astype(str))
    event_counts = load_event_counts(root / "outputs/current/MARKET_EVENT_FLAGS.csv", universe_symbols)
    market_calendar = build_market_calendar(shard_paths, as_of_date)
    universe_map = universe.set_index("symbol").to_dict(orient="index")
    status_map = history_status.set_index("symbol").to_dict(orient="index")

    status_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    processed: set[str] = set()
    for shard_path in shard_paths:
        shard = pd.read_parquet(shard_path)
        for symbol, group in shard.groupby("symbol", sort=True):
            symbol = str(symbol)
            if symbol in processed:
                raise RuntimeError(f"SYMBOL_IN_MULTIPLE_SHARDS_{symbol}")
            processed.add(symbol)
            base, details = compute_symbol_factor_values(
                group,
                {"symbol": symbol, **universe_map[symbol]},
                status_map[symbol],
                contracts["factor_registry"],
                contracts["engine_config"],
                market_calendar,
                as_of_date,
                int(event_counts.get(symbol, 0)),
            )
            status_rows.append(base)
            detail_rows.extend(details)

    for symbol in sorted(universe_symbols.difference(processed)):
        base, details = compute_symbol_factor_values(
            None,
            {"symbol": symbol, **universe_map[symbol]},
            status_map[symbol],
            contracts["factor_registry"],
            contracts["engine_config"],
            market_calendar,
            as_of_date,
            int(event_counts.get(symbol, 0)),
        )
        status_rows.append(base)
        detail_rows.extend(details)

    status_frame = pd.DataFrame(status_rows).sort_values(["board", "symbol"]).reset_index(drop=True)
    detail_frame = pd.DataFrame(detail_rows).sort_values(["factor_id", "board", "symbol"]).reset_index(drop=True)
    detail_frame = add_cross_sectional_fields(detail_frame, contracts["engine_config"])
    detail_frame["history_release_id"] = contracts["history_release"]["release_id"]
    detail_frame["factor_contract_version"] = contracts["factor_registry"]["contract_version"]
    detail_frame = add_row_hashes(detail_frame)
    wide_frame = build_wide_table(status_frame, detail_frame)
    quality = quality_payload(
        wide_frame,
        detail_frame,
        len(universe),
        as_of_date,
        contracts["history_release"]["release_id"],
        contracts["factor_registry"]["contract_version"],
    )
    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    manifest = write_outputs(output_dir, wide_frame, detail_frame, status_frame, quality, contracts, generated_at)
    if quality["hard_failures"]:
        raise RuntimeError(";".join(quality["hard_failures"]))
    print(json.dumps({"manifest": manifest, "quality": quality}, ensure_ascii=False))
    return {"manifest": manifest, "quality": quality}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    try:
        run(ROOT, Path(args.output_dir))
    except Exception as exc:
        print(f"FMDL-2B-3 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
