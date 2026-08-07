from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import scripts.validate_fmdl2b4_freshness as freshness
from scripts.run_incremental_history_refresh_v2 import (
    canonical_incremental_row,
    continuity_passes,
    snapshot_ohlc_is_valid,
)


def config() -> dict:
    return {
        "daily_fast_path": {
            "snapshot_adjustment_mode": "qfq_current_session_equivalent",
            "snapshot_record_quality": "VALIDATED_INCREMENTAL",
            "continuity_relative_tolerance": 0.003,
            "continuity_absolute_cny_tolerance": 0.02,
        }
    }


def test_indexed_snapshot_row_preserves_symbol_identity() -> None:
    row = pd.Series(
        {
            "as_of_date": "2026-07-17",
            "open": 10.0,
            "high": 10.2,
            "low": 9.9,
            "close": 10.1,
            "volume_shares": 1000.0,
            "turnover_cny": 10100.0,
        },
        name="600000.SH",
    )
    output = canonical_incremental_row(row, "2026-07-17T18:00:00+08:00", config())
    assert output["symbol"] == "600000.SH"
    assert output["trade_date"] == "2026-07-17"
    assert output["row_hash"]


def test_impossible_snapshot_ohlc_is_rejected_before_fast_append() -> None:
    row = pd.Series({
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "close": 10.1,
        "pct_change": 1.0,
        "prev_close": 10.0,
    })
    assert snapshot_ohlc_is_valid(row) is False
    passed, expected, difference = continuity_passes(row, 10.0, config())
    assert passed is False
    assert expected is None
    assert difference is None


def test_valid_snapshot_still_uses_qfq_continuity_gate() -> None:
    row = pd.Series({
        "open": 10.0,
        "high": 10.2,
        "low": 9.9,
        "close": 10.1,
        "pct_change": 1.0,
        "prev_close": 10.0,
    })
    assert snapshot_ohlc_is_valid(row) is True
    passed, expected, difference = continuity_passes(row, 10.0, config())
    assert passed is True
    assert expected == 10.0
    assert difference == 0.0


def _freshness_calendar() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": pd.to_datetime([
            "2026-08-06",
            "2026-08-07",
            "2026-08-10",
        ])
    })


def _published_release(as_of_date: str) -> dict:
    return {
        "status": "PUBLISHED_WITH_WARNINGS",
        "hard_failures": [],
        "as_of_date": as_of_date,
    }


def test_freshness_uses_previous_session_during_live_a_share_session(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    current = datetime(2026, 8, 7, 11, 55, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert freshness.latest_completed_trade_date(current) == "2026-08-06"
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-06"]


def test_freshness_marks_same_day_completed_at_market_close_but_allows_publication_grace(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    current = datetime(2026, 8, 7, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert freshness.latest_completed_trade_date(current) == "2026-08-07"
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-06", "2026-08-07"]


def test_freshness_post_close_grace_accepts_prior_or_same_day_until_1530(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    current = datetime(2026, 8, 7, 15, 29, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert freshness.latest_completed_trade_date(current) == "2026-08-07"
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-06", "2026-08-07"]


def test_freshness_validate_accepts_prior_session_during_post_close_publication_grace(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    monkeypatch.setattr(freshness, "read_json", lambda _: _published_release("2026-08-06"))
    current = datetime(2026, 8, 7, 15, 6, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = freshness.validate(Path("."), current=current)
    assert result["status"] == "PASS"
    assert result["expected_latest_completed_session"] == "2026-08-07"
    assert result["acceptable_current_sessions"] == ["2026-08-06", "2026-08-07"]
    assert result["post_close_publication_grace_active"] is True


def test_freshness_after_publication_grace_requires_same_day(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    current = datetime(2026, 8, 7, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert freshness.latest_completed_trade_date(current) == "2026-08-07"
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-07"]


def test_freshness_validate_rejects_prior_session_after_publication_grace(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    monkeypatch.setattr(freshness, "read_json", lambda _: _published_release("2026-08-06"))
    current = datetime(2026, 8, 7, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    with pytest.raises(RuntimeError, match="CURRENT_AS_OF_2026-08-06_EXPECTED_ONE_OF_2026-08-07"):
        freshness.validate(Path("."), current=current)


def test_freshness_weekend_uses_most_recent_completed_session(monkeypatch) -> None:
    monkeypatch.setattr(freshness.ak, "tool_trade_date_hist_sina", _freshness_calendar)
    current = datetime(2026, 8, 8, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert freshness.latest_completed_trade_date(current) == "2026-08-07"
    assert freshness.acceptable_completed_trade_dates(current) == ["2026-08-07"]
