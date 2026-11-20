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
POST_CLOSE_PUBLICATION_GRACE_END = time(15, 30)
PRE_MARKET_RECOVERY_CUTOFF = time(8, 30)
MANUAL_RECOVERY_EARLIEST = time(15, 30)


def _local_now(current: datetime | None = None) -> datetime:
    local_now = current or datetime.now(tz=BUSINESS_TZ)
    if local_now.tzinfo is None:
        return local_now.replace(tzinfo=BUSINESS_TZ)
    return local_now.astimezone(BUSINESS_TZ)


def _trade_dates() -> list:
    calendar = ak.tool_trade_date_hist_sina()
    if calendar is None or not isinstance(calendar, pd.DataFrame) or calendar.empty:
        raise RuntimeError("TRADING_CALENDAR_UNAVAILABLE")
    column = next((name for name in ("trade_date", "交易日", "date") if name in calendar.columns), None)
    if column is None:
        raise RuntimeError("TRADING_CALENDAR_DATE_COLUMN_MISSING")
    return sorted(set(pd.to_datetime(calendar[column], errors="coerce").dropna().dt.date))


def validate_manual_recovery_window(current: datetime | None = None) -> dict:
    """Allow recovery only when the A-share spot source cannot contain live-session quotes.

    The workflow rebuilds one market-wide spot snapshot before running all 24
    history shards. On trading days, the snapshot may be used overnight before
    the conservative 08:30 pre-market cutoff, or after the 15:30 close-settlement
    boundary. The 08:30-15:30 window is blocked to avoid pre-open auction,
    intraday and unsettled-close contamination.

    The snapshot as-of date is derived from the exchange calendar and 15:30
    publication cutoff. After the snapshot is built, validate_fmdl2b4_freshness
    independently requires its as-of date to equal the latest completed session.
    This allows a delayed cron arriving overnight to recover safely without
    weakening the post-refresh data-date check. Non-trading days remain safe.
    """
    local_now = _local_now(current)
    dates = _trade_dates()
    today = local_now.date()
    today_is_trade_day = today in dates
    errors: list[str] = []
    if (
        today_is_trade_day
        and PRE_MARKET_RECOVERY_CUTOFF <= local_now.time() < MANUAL_RECOVERY_EARLIEST
    ):
        errors.append("FULL_REBASE_REQUIRES_MARKET_CLOSED_WINDOW")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "business_time": local_now.isoformat(),
        "today_is_trade_day": today_is_trade_day,
        "market_session_guard_start": PRE_MARKET_RECOVERY_CUTOFF.isoformat(timespec="minutes"),
        "market_session_guard_end": MANUAL_RECOVERY_EARLIEST.isoformat(timespec="minutes"),
        "recovery_safe_windows": ["00:00-08:29", "15:30-23:59"],
        "overnight_recovery_allowed": today_is_trade_day and local_now.time() < PRE_MARKET_RECOVERY_CUTOFF,
        "post_close_recovery_allowed": local_now.time() >= MANUAL_RECOVERY_EARLIEST,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise RuntimeError(";".join(errors))
    return result

def acceptable_completed_trade_dates(current: datetime | None = None) -> list[str]:
    """Return Current as-of dates acceptable at this wall-clock instant.

    A-share continuous trading ends at 15:00 Beijing, but the free public source can
    need a short settlement/publication interval before the same-day close is exposed
    through the production snapshot route. During 15:00-15:30 on a trading day, both
    the just-finished session and the immediately prior completed session are accepted.
    After 15:30, only the same-day session is accepted. Before 15:00, only the prior
    completed session is accepted. Non-trading days use the most recent trade date.
    """
    dates = _trade_dates()
    local_now = _local_now(current)
    today = local_now.date()
    today_is_trade_day = today in dates

    prior = [item for item in dates if item < today]
    if not today_is_trade_day:
        eligible = [item for item in dates if item <= today]
        if not eligible:
            raise RuntimeError("NO_COMPLETED_TRADE_DATE")
        return [eligible[-1].isoformat()]

    if not prior:
        raise RuntimeError("NO_COMPLETED_TRADE_DATE")
    prior_date = prior[-1].isoformat()
    today_date = today.isoformat()

    if local_now.time() < MARKET_CLOSE:
        return [prior_date]
    if local_now.time() < POST_CLOSE_PUBLICATION_GRACE_END:
        return [prior_date, today_date]
    return [today_date]


def latest_completed_trade_date(current: datetime | None = None) -> str:
    """Return the strict latest completed exchange session for reporting semantics."""
    dates = _trade_dates()
    local_now = _local_now(current)
    today = local_now.date()
    today_is_trade_day = today in dates
    same_day_completed = today_is_trade_day and local_now.time() >= MARKET_CLOSE
    eligible = [
        item
        for item in dates
        if item < today or (item == today and same_day_completed)
    ]
    if not eligible:
        raise RuntimeError("NO_COMPLETED_TRADE_DATE")
    return eligible[-1].isoformat()


def validate(root: Path = ROOT, current: datetime | None = None) -> dict:
    release = read_json(root / "outputs/current/CURRENT_RELEASE.json")
    acceptable = acceptable_completed_trade_dates(current)
    expected = acceptable[-1]
    current_as_of = str(release.get("as_of_date"))
    errors: list[str] = []
    if release.get("status") not in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}:
        errors.append("CURRENT_NOT_PUBLISHED")
    if release.get("hard_failures"):
        errors.append("CURRENT_HAS_HARD_FAILURES")
    if current_as_of not in acceptable:
        errors.append(
            f"CURRENT_AS_OF_{release.get('as_of_date')}_EXPECTED_ONE_OF_{'_OR_'.join(acceptable)}"
        )
    local_now = _local_now(current)
    grace_active = (
        local_now.date().isoformat() == expected
        and MARKET_CLOSE <= local_now.time() < POST_CLOSE_PUBLICATION_GRACE_END
        and len(acceptable) == 2
    )
    result = {
        "status": "PASS" if not errors else "FAIL",
        "expected_latest_completed_session": expected,
        "acceptable_current_sessions": acceptable,
        "post_close_publication_grace_active": grace_active,
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
