"""Canonical normalization for A-share universe and daily market snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from ingestion.akshare.client import AkshareBundle
from pipeline.common import (
    canonical_symbol,
    clean_scalar,
    exchange_and_board,
    safe_float,
    stable_row_hash,
)


@dataclass
class NormalizedBundle:
    universe: pd.DataFrame
    snapshot: pd.DataFrame
    warnings: list[str]


def _normalized_code(value: Any) -> str:
    text = str(clean_scalar(value) or "").strip().split(".")[0]
    return text.zfill(6) if text else ""


def _date_text(value: Any) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _master_rows(bundle: AkshareBundle) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    def add(code: Any, name: Any, list_date: Any, industry: Any, source: str) -> None:
        normalized = _normalized_code(code)
        if not normalized:
            return
        records[normalized] = {
            "name": str(clean_scalar(name) or "").strip() or None,
            "list_date": _date_text(list_date),
            "industry_name": str(clean_scalar(industry) or "").strip() or None,
            "industry_source": source if clean_scalar(industry) else None,
        }

    for call in (bundle.sh_main, bundle.sh_star):
        frame = call.data
        if frame.empty:
            warnings.extend(call.warnings)
            continue
        for _, row in frame.iterrows():
            add(row.get("证券代码"), row.get("证券简称"), row.get("上市日期"), None, call.function)

    frame = bundle.sz_a.data
    if frame.empty:
        warnings.extend(bundle.sz_a.warnings)
    else:
        for _, row in frame.iterrows():
            add(
                row.get("A股代码"),
                row.get("A股简称"),
                row.get("A股上市日期"),
                row.get("所属行业"),
                bundle.sz_a.function,
            )

    frame = bundle.bj_a.data
    if frame.empty:
        warnings.extend(bundle.bj_a.warnings)
    else:
        for _, row in frame.iterrows():
            add(
                row.get("证券代码"),
                row.get("证券简称"),
                row.get("上市日期"),
                row.get("所属行业"),
                bundle.bj_a.function,
            )
    return records, warnings


def normalize_a_share_bundle(
    bundle: AkshareBundle,
    *,
    as_of_date: date,
    source_timestamp: str,
) -> NormalizedBundle:
    spot = bundle.spot.data.copy()
    required_columns = {"代码", "名称", "最新价", "昨收", "涨跌幅", "成交量", "成交额"}
    missing = sorted(required_columns.difference(spot.columns))
    if missing:
        raise ValueError(f"stock_zh_a_spot_em missing required columns: {missing}")

    spot["代码"] = spot["代码"].map(_normalized_code)
    spot = spot.loc[spot["代码"].str.fullmatch(r"[0-9]{6}", na=False)].copy()
    spot = spot.drop_duplicates(subset=["代码"], keep="first")

    masters, warnings = _master_rows(bundle)
    spot_map = {str(row["代码"]): row for _, row in spot.iterrows()}
    all_codes = sorted(set(spot_map).union(masters))
    universe_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    as_of_text = as_of_date.isoformat()

    for code in all_codes:
        spot_row = spot_map.get(code)
        master = masters.get(code, {})
        raw_name = None if spot_row is None else clean_scalar(spot_row.get("名称"))
        name = str(raw_name or master.get("name") or "").strip() or code
        exchange, board = exchange_and_board(code)
        close = None if spot_row is None else safe_float(spot_row.get("最新价"))
        prev_close = None if spot_row is None else safe_float(spot_row.get("昨收"))
        volume_lots = None if spot_row is None else safe_float(spot_row.get("成交量"))
        turnover = None if spot_row is None else safe_float(spot_row.get("成交额"))
        is_suspended = spot_row is None or close is None
        is_st = "ST" in name.upper()
        record_quality = "VALID"
        if master.get("list_date") is None or master.get("industry_name") is None:
            record_quality = "PARTIAL"
        if board == "UNKNOWN":
            record_quality = "SUSPECT"

        universe_row: dict[str, Any] = {
            "as_of_date": as_of_text,
            "symbol": canonical_symbol(code),
            "source_symbol": code,
            "name": name,
            "name_raw": None if raw_name is None else str(raw_name),
            "exchange": exchange,
            "board": board,
            "currency": "CNY",
            "security_type": "COMMON_STOCK",
            "list_date": master.get("list_date"),
            "delist_date": None,
            "listing_status": "SUSPENDED" if is_suspended else "ACTIVE",
            "is_st": bool(is_st),
            "is_suspended": bool(is_suspended),
            "industry_code": None,
            "industry_name": master.get("industry_name"),
            "industry_source": master.get("industry_source"),
            "lot_size": 100,
            "source_primary": "akshare.stock_zh_a_spot_em",
            "source_timestamp": source_timestamp,
            "record_quality": record_quality,
        }
        universe_row["row_hash"] = stable_row_hash(universe_row)
        universe_rows.append(universe_row)

        data_status = "TRADED" if close is not None else ("SUSPENDED" if code in masters else "NO_DATA")
        snapshot_row: dict[str, Any] = {
            "as_of_date": as_of_text,
            "symbol": canonical_symbol(code),
            "open": None if spot_row is None else safe_float(spot_row.get("今开")),
            "high": None if spot_row is None else safe_float(spot_row.get("最高")),
            "low": None if spot_row is None else safe_float(spot_row.get("最低")),
            "close": close,
            "prev_close": prev_close,
            "pct_change": None if spot_row is None else safe_float(spot_row.get("涨跌幅")),
            "amplitude_pct": None if spot_row is None else safe_float(spot_row.get("振幅")),
            "volume_shares": None if volume_lots is None else volume_lots * 100.0,
            "turnover_cny": turnover,
            "turnover_rate_pct": None if spot_row is None else safe_float(spot_row.get("换手率")),
            "market_cap_cny": None if spot_row is None else safe_float(spot_row.get("总市值")),
            "float_market_cap_cny": None if spot_row is None else safe_float(spot_row.get("流通市值")),
            "pe_ttm": None if spot_row is None else safe_float(spot_row.get("市盈率-动态")),
            "pb": None if spot_row is None else safe_float(spot_row.get("市净率")),
            "data_status": data_status,
            "source_primary": "akshare.stock_zh_a_spot_em",
            "source_timestamp": source_timestamp,
            "record_quality": "VALID" if close is not None and prev_close is not None else "PARTIAL",
        }
        snapshot_row["row_hash"] = stable_row_hash(snapshot_row)
        snapshot_rows.append(snapshot_row)

    universe = pd.DataFrame(universe_rows).sort_values("symbol").reset_index(drop=True)
    snapshot = pd.DataFrame(snapshot_rows).sort_values("symbol").reset_index(drop=True)
    warnings.extend(bundle.spot.warnings)
    warnings.extend(bundle.trade_calendar.warnings)
    return NormalizedBundle(universe=universe, snapshot=snapshot, warnings=warnings)
