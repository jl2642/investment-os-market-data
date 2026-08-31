import pandas as pd

from scripts.scan_occ_r2b_financial_backlog import fetch_notice_index, normalize_notice_frame


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


def test_fetch_notice_index_retries_transient_failure() -> None:
    calls = {"count": 0}

    def fake_fetcher(*, symbol: str, date: str) -> pd.DataFrame:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return pd.DataFrame([{
            "代码":"000001",
            "名称":"A",
            "公告标题":"2026年半年度报告",
            "公告日期":"2026-08-20",
            "网址":"u1",
        }])

    rows, attempt = fetch_notice_index(
        pd.Timestamp("2026-08-20").date(),
        "财务报告",
        {"000001.SZ"},
        max_attempts=3,
        initial_backoff_seconds=0,
        fetcher=fake_fetcher,
    )
    assert calls["count"] == 2
    assert attempt["attempt_count"] == 2
    assert attempt["source_state"] == "SUCCESS"
    assert len(rows) == 1
