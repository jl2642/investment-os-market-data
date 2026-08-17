from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from automation.wp3_2a.acquire_universe import completed_session_from_sina_calendar


CALENDAR = b'var KLC_TD_SH = new Array("2026-08-13","2026-08-14","2026-08-17","2026-08-18");'


def test_sina_calendar_uses_today_after_close() -> None:
    now = datetime(2026, 8, 17, 17, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert completed_session_from_sina_calendar(CALENDAR, now) == "2026-08-17"


def test_sina_calendar_uses_previous_session_before_close() -> None:
    now = datetime(2026, 8, 17, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert completed_session_from_sina_calendar(CALENDAR, now) == "2026-08-14"


def test_sina_calendar_ignores_future_sessions() -> None:
    now = datetime(2026, 8, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert completed_session_from_sina_calendar(CALENDAR, now) == "2026-08-14"


def test_sina_calendar_fails_closed_when_no_dates_exist() -> None:
    now = datetime(2026, 8, 17, 17, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert completed_session_from_sina_calendar(b"no trading dates", now) is None
