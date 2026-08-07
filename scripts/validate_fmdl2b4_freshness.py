#!/usr/bin/env python3
"""Fail-closed freshness precheck for scheduled/manual FMDL-2B-4 runs."""

from __future__ import annotations

import argparse
from datetime import datetime, time
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from scripts.fmdl2b4_history import ROOT, read_json

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
MARKET_CLOSE = time(15, 0)


def latest_completed_trade_date(current: datetime | None = None) -> str:
    calendar = ak.tool_trade_date_hist_sina()
    if calendar is None or not isinstance(calendar, pd.DataFrame) or calendar.empty:
        raise RuntimeError("TRADING_CALENDAR_UNAVAILABLE")
    column = next((name for name in ("trade_date", "交易日", "date") if name in calendar.columns), None)
    if column is None:
        raise RuntimeError("TRADING_CALENDAR_DATE_COLUMN_MISSING")

    local_now = current or datetime.now(tz=BUSINESS_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=BUSINESS_TZ)
    else:
        local_now = local_now.astimezone(BUSINESS_TZ)

    dates = sorted(set(pd.to_datetime(calendar[column], errors="coerce").dropna().dt.date))
    today = local_now.date()
    today_is_trade_day = today in dates
    same_day_completed = (not today_is_trade_day) or local_now.time() >= MARKET_CLOSE
    eligible = [
        item
        for item in dates
        if item < today or (item == today and same_day_completed)
    ]
    if not eligible:
        raise RuntimeError("NO_COMPLETED_TRADE_DATE")
    return eligible[-1].isoformat()


def validate(root: Path = ROOT) -> dict:
    release = read_json(root / "outputs/current/CURRENT_RELEASE.json")
    expected = latest_completed_trade_date()
    errors: list[str] = []
    if release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        errors.append("CURRENT_NOT_PUBLISHED")
    if release.get("hard_failures"):
        errors.append("CURRENT_HAS_HARD_FAILURES")
    if str(release.get("as_of_date")) != expected:
        errors.append(f"CURRENT_AS_OF_{release.get('as_of_date')}_EXPECTED_{expected}")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "expected_latest_completed_session": expected,
        "current_as_of_date": release.get("as_of_date"),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise RuntimeError(";".join(errors))
    return result


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    try:
        validate(ROOT)
    except Exception as exc:
        print(f"FMDL-2B-4 freshness failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
