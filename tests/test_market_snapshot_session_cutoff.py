from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from pipeline.common import latest_completed_trade_date
import scripts.validate_fmdl2b4_freshness as freshness


BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def _calendar() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": pd.to_datetime([
            "2026-08-06",
            "2026-08-07",
            "2026-08-10",
        ])
    })


def test_market_snapshot_stays_on_prior_session_during_post_close_publication_grace(monkeypatch) -> None:
    calendar = _calendar()
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", lambda: calendar)
    current = datetime(2026, 8, 7, 15, 29, 59, tzinfo=BUSINESS_TZ)

    assert latest_completed_trade_date(calendar, current) == pd.Timestamp("2026-08-06").date()
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-06", "2026-08-07"]


def test_market_snapshot_switches_to_same_day_at_freshness_cutoff(monkeypatch) -> None:
    calendar = _calendar()
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", lambda: calendar)
    current = datetime(2026, 8, 7, 15, 30, 0, tzinfo=BUSINESS_TZ)

    assert latest_completed_trade_date(calendar, current) == pd.Timestamp("2026-08-07").date()
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-07"]


def test_market_snapshot_after_cutoff_remains_same_day(monkeypatch) -> None:
    calendar = _calendar()
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", lambda: calendar)
    current = datetime(2026, 8, 7, 15, 35, 0, tzinfo=BUSINESS_TZ)

    assert latest_completed_trade_date(calendar, current) == pd.Timestamp("2026-08-07").date()
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-07"]


def test_non_trading_day_uses_most_recent_trade_date(monkeypatch) -> None:
    calendar = _calendar()
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", lambda: calendar)
    current = datetime(2026, 8, 8, 12, 0, tzinfo=BUSINESS_TZ)

    assert latest_completed_trade_date(calendar, current) == pd.Timestamp("2026-08-07").date()
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-07"]
