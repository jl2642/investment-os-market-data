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
    with pytest.raises(RuntimeError, match="FULL_REBASE_REQUIRES_MARKET_CLOSED_WINDOW"):
        freshness.validate_manual_recovery_window(now)


def test_manual_full_rebase_rejects_post_close_grace_window(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 15, 29, tzinfo=SHANGHAI)
    with pytest.raises(RuntimeError, match="FULL_REBASE_REQUIRES_MARKET_CLOSED_WINDOW"):
        freshness.validate_manual_recovery_window(now)


def test_manual_full_rebase_accepts_delayed_overnight_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 1, 7, tzinfo=SHANGHAI)
    result = freshness.validate_manual_recovery_window(now)
    assert result["status"] == "PASS"
    assert result["overnight_recovery_allowed"] is True
    assert result["recovery_safe_windows"] == ["00:00-08:29", "15:30-23:59"]


def test_manual_full_rebase_accepts_before_preopen_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 8, 29, tzinfo=SHANGHAI)
    result = freshness.validate_manual_recovery_window(now)
    assert result["status"] == "PASS"


def test_manual_full_rebase_rejects_preopen_guard_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _calendar(monkeypatch)
    now = datetime(2026, 8, 17, 8, 30, tzinfo=SHANGHAI)
    with pytest.raises(RuntimeError, match="FULL_REBASE_REQUIRES_MARKET_CLOSED_WINDOW"):
        freshness.validate_manual_recovery_window(now)


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

def test_delayed_cron_recovery_has_early_guarded_wakeup_and_regular_fallback() -> None:
    from pathlib import Path
    workflow = Path(".github/workflows/fmdl-2b4-full-rebase.yml").read_text(encoding="utf-8")
    assert 'cron: "0 0 * * 1-5"' in workflow
    assert 'cron: "0 8 * * 1-5"' in workflow
    assert "validate_manual_recovery_window()" in workflow
    assert "FULL_REBASE_REQUIRES_MARKET_CLOSED_WINDOW" in workflow
    assert "overnight" in workflow.lower()
    assert 'steps.recovery_window.outputs.skip' in workflow
