from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import scripts.validate_fmdl2b4_freshness as freshness


SHANGHAI = ZoneInfo("Asia/Shanghai")
TRADE_DATES = [date(2026, 8, 14), date(2026, 8, 17)]


def _calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(freshness, "_trade_dates", lambda: TRADE_DATES)


def test_manual_full_rebase_rejects_trading_day_intraday(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 10, 0, tzinfo=SHANGHAI)
    with pytest.raises(RuntimeError, match="FULL_REBASE_REQUIRES_PREOPEN_OR_POST_CLOSE_WINDOW_ON_TRADING_DAY"):
        freshness.validate_manual_recovery_window(now)


def test_manual_full_rebase_rejects_post_close_grace_window(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 15, 29, tzinfo=SHANGHAI)
    with pytest.raises(RuntimeError, match="FULL_REBASE_REQUIRES_PREOPEN_OR_POST_CLOSE_WINDOW_ON_TRADING_DAY"):
        freshness.validate_manual_recovery_window(now)



def test_manual_full_rebase_accepts_trade_day_preopen(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 2, 54, tzinfo=SHANGHAI)
    result = freshness.validate_manual_recovery_window(now)
    assert result["status"] == "PASS"
    assert result["today_is_trade_day"] is True

def test_manual_full_rebase_accepts_after_1530(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 15, 30, tzinfo=SHANGHAI)
    result = freshness.validate_manual_recovery_window(now)
    assert result["status"] == "PASS"
    assert result["today_is_trade_day"] is True


def test_manual_full_rebase_accepts_non_trading_day(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 16, 10, 0, tzinfo=SHANGHAI)
    result = freshness.validate_manual_recovery_window(now)
    assert result["status"] == "PASS"
    assert result["today_is_trade_day"] is False
