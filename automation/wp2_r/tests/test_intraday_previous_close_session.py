from __future__ import annotations

import json

from automation.wp2_r import refresh_market_marks as mod


def test_intraday_previous_close_uses_actual_prior_market_session(monkeypatch) -> None:
    sina = (
        'var hq_str_sh600000="浦发银行,10.00,10.20,10.10,10.20,10.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-08-11,09:38:57,00";'
    )
    kline = {
        "data": {
            "klines": [
                "2026-08-07,0,0,0,0,0",
                "2026-08-10,0,0,0,0,0",
                "2026-08-11,0,0,0,0,0",
            ]
        }
    }

    def fake_request(url: str, encoding: str, retries: int = 3) -> str:
        if url.startswith("https://hq.sinajs.cn"):
            return sina
        if url == mod.EASTMONEY_INDEX_KLINE_URL:
            return json.dumps(kline)
        raise AssertionError(url)

    monkeypatch.setattr(mod, "request_text", fake_request)
    monkeypatch.setattr(mod, "freshness", lambda as_of, max_days: "FRESH")
    monkeypatch.setattr(mod, "datetime", _FakeDateTime)

    rows = [{
        "security_id": "600000.SH",
        "code": "600000",
        "security_name": "浦发银行",
        "asset_class": "A_SHARE_STOCK",
    }]
    marks, errors, observations = mod.listed_marks(
        rows,
        max_days=3,
        existing_by_id={"600000.SH": {"as_of_date": "2026-08-07", "mark": 10.0}},
    )

    assert errors == []
    assert marks[0]["mark"] == 10.20
    assert marks[0]["as_of_date"] == "2026-08-10"
    assert marks[0]["mark_type"] == "LATEST_COMPLETED_CLOSE_PRIOR_SESSION"
    assert observations[0]["previous_completed_close_date"] == "2026-08-10"


class _FakeNow:
    def __init__(self, iso_date: str):
        self._iso_date = iso_date

    def date(self):
        return self

    def isoformat(self):
        return self._iso_date


class _FakeDateTime:
    @classmethod
    def now(cls, tz=None):
        return _FakeNow("2026-08-11")


def test_holiday_marks_are_session_fresh(monkeypatch) -> None:
    from datetime import datetime

    calls = []
    def completed_session(before_date: str) -> str:
        calls.append(before_date)
        return "2026-09-30"

    monkeypatch.setattr(mod, "latest_completed_listed_session", completed_session)
    marks = [
        {"security_id": "600000.SH", "as_of_date": "2026-09-30", "freshness_status": "STALE"},
        {"security_id": "017534.OF", "as_of_date": "2026-09-30", "freshness_status": "STALE"},
        {"security_id": "000001.SZ", "as_of_date": "2026-09-29", "freshness_status": "STALE"},
    ]
    reference = mod.apply_exchange_session_freshness(
        marks, now=datetime(2026, 10, 7, 22, 45, tzinfo=mod.CN)
    )
    assert reference == "2026-09-30"
    assert calls == ["2026-10-08"]
    assert [m["freshness_status"] for m in marks] == ["FRESH", "FRESH", "STALE"]
    assert marks[0]["freshness_basis"] == "CONFIRMED_COMPLETED_EXCHANGE_SESSION"


def test_newly_completed_session_rejects_old_holiday_marks(monkeypatch) -> None:
    from datetime import datetime

    monkeypatch.setattr(
        mod, "latest_completed_listed_session", lambda before_date: "2026-10-08"
    )
    marks = [{"security_id": "600000.SH", "as_of_date": "2026-09-30", "freshness_status": "STALE"}]
    reference = mod.apply_exchange_session_freshness(
        marks, now=datetime(2026, 10, 8, 22, 45, tzinfo=mod.CN)
    )
    assert reference == "2026-10-08"
    assert marks[0]["freshness_status"] == "STALE"


def test_exchange_calendar_unavailable_fails_closed(monkeypatch) -> None:
    from datetime import datetime

    def outage(before_date: str) -> str:
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(mod, "latest_completed_listed_session", outage)
    marks = [{"security_id": "600000.SH", "as_of_date": "2026-09-30", "freshness_status": "STALE"}]
    assert mod.apply_exchange_session_freshness(
        marks, now=datetime(2026, 10, 7, 22, 45, tzinfo=mod.CN)
    ) is None
    assert marks[0]["freshness_status"] == "STALE"


def test_intraday_exchange_reference_never_includes_current_session(monkeypatch) -> None:
    from datetime import datetime

    seen = []
    def confirmed_session(before_date: str) -> str:
        seen.append(before_date)
        return "2026-09-30"

    monkeypatch.setattr(mod, "latest_completed_listed_session", confirmed_session)
    marks = [{"security_id": "600000.SH", "as_of_date": "2026-09-30", "freshness_status": "STALE"}]
    assert mod.apply_exchange_session_freshness(
        marks, now=datetime(2026, 10, 8, 9, 35, tzinfo=mod.CN)
    ) == "2026-09-30"
    assert seen == ["2026-10-08"]
    assert marks[0]["freshness_status"] == "FRESH"
