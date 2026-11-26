import pandas as pd
import pytest

from scripts.scan_occ_r2b_financial_backlog import accepted_baseline_start, normalize_notice_frame


def test_normalize_notice_frame_filters_to_financial_titles_and_universe() -> None:
    frame = pd.DataFrame([
        {"代码":"000001","名称":"A","公告标题":"2026年半年度报告","公告日期":"2026-08-20","网址":"u1"},
        {"代码":"000002","名称":"B","公告标题":"关于董事会决议的公告","公告日期":"2026-08-20","网址":"u2"},
        {"代码":"000003","名称":"C","公告标题":"2026年半年度报告","公告日期":"2026-08-20","网址":"u3"},
    ])
    rows = normalize_notice_frame(
        frame,
        day=pd.Timestamp("2026-08-20").date(),
        category="财务报告",
        universe={"000001.SZ", "000002.SZ"},
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "000001.SZ"
    assert rows[0]["period_end"] == "2026-06-30"
    assert rows[0]["trade_authority"] == "NONE"


def test_normalize_notice_frame_event_id_is_deterministic() -> None:
    frame = pd.DataFrame([{
        "代码":"600000","名称":"P","公告标题":"2026年半年度报告","公告日期":"2026-08-28","网址":"same"
    }])
    kwargs = dict(day=pd.Timestamp("2026-08-28").date(), category="财务报告", universe={"600000.SH"})
    left = normalize_notice_frame(frame, **kwargs)
    right = normalize_notice_frame(frame, **kwargs)
    assert left[0]["event_id"] == right[0]["event_id"]


def _accepted_financial_context():
    return (
        {"domain_id": "FINANCIAL_STATEMENT_CONTEXT", "status": "PASS",
         "qc_status": "PASS_FINANCIAL_BASELINE_REBUILT", "trade_authority": "NONE",
         "data_watermark": "2026-11-10", "source_commit_sha": "accepted-immutable-commit"},
        {"status": "PASS", "qc_status": "PASS_FINANCIAL_BASELINE_REBUILT",
         "trade_authority": "NONE", "market_as_of_date": "2026-11-10",
         "financial_report_period_watermark": "2026-09-30",
         "generated_at": "2026-11-11T21:40:58+08:00",
         "releases": {"statement_release_id": "FMDL3B4_20261111T212048+0800"}},
    )


def test_backlog_starts_at_accepted_pit_not_publication_date():
    pointer, context = _accepted_financial_context()
    assert accepted_baseline_start(pointer, context) == "2026-11-10"


@pytest.mark.parametrize("field, value", [
    ("market_as_of_date", "2026-07-17"),
    ("financial_report_period_watermark", "2026-12-31"),
    ("status", "FAIL"),
    ("trade_authority", "ORDER"),
    ("releases", {}),
])
def test_backlog_rejects_wrong_or_unaccepted_financial_baseline(field, value):
    pointer, context = _accepted_financial_context()
    context[field] = value
    with pytest.raises(ValueError):
        accepted_baseline_start(pointer, context)


def test_scan_recovers_only_failed_slots_and_counts_invalid_responses(monkeypatch):
    from scripts import scan_occ_r2b_financial_backlog as scan
    day = pd.Timestamp("2026-11-25").date()
    calls = []
    valid = pd.DataFrame([{"代码":"600000","公告标题":"2026年第三季度报告","公告日期":"2026-11-25","网址":"same"}])
    def fetch(symbol, date):
        calls.append(symbol)
        if symbol == "财务报告" and calls.count(symbol) == 1:
            return None
        return valid
    monkeypatch.setattr(scan.ak, "stock_notice_report", fetch)
    monkeypatch.setattr(scan.time, "sleep", lambda s: None)
    events, attempts = scan.scan_live(day, day, {"600000.SH"}, ["财务报告","信息变更"])
    assert calls == ["财务报告","信息变更","财务报告"]
    assert len(events) == 1
    assert attempts["source_state"].tolist() == ["SUCCESS","SUCCESS"]
    assert attempts["attempt_count"].tolist() == [2,1]
    assert attempts.iloc[0]["initial_error_type"] == "TypeError"


def test_scan_rejects_nonempty_schema_drift_and_does_not_retry_rate_limit(monkeypatch):
    from scripts import scan_occ_r2b_financial_backlog as scan
    day = pd.Timestamp("2026-11-25").date()
    calls = []
    def fetch(symbol, date):
        calls.append(symbol)
        if symbol == "limited":
            raise RuntimeError("HTTP 429 rate limit")
        if symbol == "drift":
            return pd.DataFrame([{"unexpected":1}])
        return pd.DataFrame()
    monkeypatch.setattr(scan.ak, "stock_notice_report", fetch)
    monkeypatch.setattr(scan.time, "sleep", lambda s: None)
    events, attempts = scan.scan_live(day, day, {"600000.SH"}, ["limited","drift","empty"])
    assert calls == ["limited","drift","empty","drift"]
    assert len(events) == 0
    assert attempts["source_state"].tolist() == ["FAILED","FAILED","SUCCESS_EMPTY"]
    assert attempts["attempt_count"].tolist() == [1,2,1]


def test_scan_does_not_repeat_complete_outage(monkeypatch):
    from scripts import scan_occ_r2b_financial_backlog as scan
    day = pd.Timestamp("2026-11-25").date()
    calls = []
    def fetch(symbol, date):
        calls.append(symbol)
        raise RuntimeError("connection closed")
    monkeypatch.setattr(scan.ak, "stock_notice_report", fetch)
    monkeypatch.setattr(scan.time, "sleep", lambda s: pytest.fail("complete outage must not retry"))
    _, attempts = scan.scan_live(day, day, set(), ["a","b"])
    assert calls == ["a","b"]
    assert attempts["source_state"].tolist() == ["FAILED","FAILED"]


@pytest.mark.parametrize("payload,expected", [
    ({"success":True,"data":{"total_hits":0,"list":[]}},True),
    ({"success":1,"data":{"total_hits":0,"list":[]}},True),
    ({"success":True,"data":{"total_hits":1,"list":[]}},False),
    ({"success":True,"data":{"total_hits":0,"list":[{"title":"notice"}]}},False),
    ({"success":False,"data":{"total_hits":0,"list":[]}},False),
    ({"data":{"total_hits":0,"list":[]}},False),
    ({"success":True,"data":{"total_hits":0}},False),
])
def test_empty_provider_confirmation_requires_explicit_zero(monkeypatch,payload,expected):
    from scripts import scan_occ_r2b_financial_backlog as scan
    class Response:
        def raise_for_status(self): pass
        def json(self): return payload
    def get(url,params,timeout):
        assert params["begin_time"]==params["end_time"]=="2026-11-15"
        assert params["f_node"]=="1"
        return Response()
    monkeypatch.setattr(scan.requests,"get",get)
    assert scan.confirm_provider_empty(pd.Timestamp("2026-11-15").date(),"财务报告") is expected


@pytest.mark.parametrize("confirmed", [True, False])
def test_adapter_keyerror_is_empty_only_after_source_confirmation(monkeypatch,confirmed):
    from scripts import scan_occ_r2b_financial_backlog as scan
    day=pd.Timestamp("2026-11-15").date()
    calls=[]
    def fetch(symbol,date):
        calls.append(symbol)
        if symbol=="财务报告":
            raise KeyError("代码")
        return pd.DataFrame()
    monkeypatch.setattr(scan.ak,"stock_notice_report",fetch)
    monkeypatch.setattr(scan,"confirm_provider_empty",lambda d,c: confirmed)
    monkeypatch.setattr(scan.time,"sleep",lambda s: pytest.fail("no repeat of confirmed or unresolved adapter error"))
    _,attempts=scan.scan_live(day,day,set(),["财务报告","信息变更"])
    assert calls==["财务报告","信息变更"]
    assert attempts.iloc[0]["source_state"]==("SUCCESS_EMPTY" if confirmed else "FAILED")
    assert bool(attempts.iloc[0]["empty_confirmation_attempted"])
    assert bool(attempts.iloc[0]["confirmed_empty_after_adapter_error"])==confirmed
    assert "代码" in attempts.iloc[0]["adapter_error_before_confirmation"]
