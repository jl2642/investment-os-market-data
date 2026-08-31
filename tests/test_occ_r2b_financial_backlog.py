import pandas as pd

from scripts.scan_occ_r2b_financial_backlog import normalize_notice_frame


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
