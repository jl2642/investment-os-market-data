from __future__ import annotations

from datetime import date

import pandas as pd

from pipeline.hkcu1_fetch_adjustment_events import parse_notice_html
from pipeline.hkcu1_resilience import classify_sse_evidence, decide
from pipeline.hkcu1_resolve_effective_dates import next_service_day, resolve_events


def test_sse_403_is_source_blocked_not_code_defect():
    evidence = {
        "status": "BLOCKED",
        "landing_http_status": 403,
        "payload_http_status": 403,
        "error": "PlaywrightTimeoutError: download timeout",
    }
    assert classify_sse_evidence(evidence) == "SOURCE_BLOCKED"


def test_lkg_preserves_continuity_but_never_publication():
    evidence = {"status": "BLOCKED", "landing_http_status": 403, "payload_http_status": 403}
    lkg = {"source_as_of_dates": {"SH": "2026-08-06", "SZ": "2026-08-07"}}
    result = decide(evidence, lkg, "2026-08-07", max_continuity_age_days=14)
    assert result["status"] == "DEGRADED_CONTINUITY"
    assert result["continuity_available"] is True
    assert result["publication_allowed"] is False
    assert result["canonical_action"] == "KEEP_PREVIOUS_CANONICAL_UNCHANGED"


def test_old_lkg_fails_closed():
    evidence = {"status": "BLOCKED", "error": "connection reset"}
    lkg = {"source_as_of_dates": {"SH": "2026-07-01", "SZ": "2026-07-01"}}
    result = decide(evidence, lkg, "2026-08-07", max_continuity_age_days=14)
    assert result["status"] == "BLOCKED_NO_FRESH_SOURCE"
    assert result["continuity_available"] is False
    assert result["publication_allowed"] is False


def test_parse_sse_out_preserves_next_trading_day_rule():
    html = """
    <html><body>
      <h1>关于沪港通下港股通标的调整的通知</h1>
      <p>2026-07-09</p>
      <p>标的名单发生调整，并自下一港股通交易日起生效。</p>
      <table><tr><th>代码</th><th>英文简称</th><th>简体中文简称（参考）</th><th>调整方向</th></tr>
      <tr><td>00754</td><td>HOPSON DEV HOLD</td><td>合生创展集团</td><td>调出</td></tr>
      <tr><td>02983</td><td>HESAI-W</td><td>禾赛-W</td><td>调入</td></tr></table>
      <p>中国投资信息有限公司 2026年7月9日</p>
    </body></html>
    """.encode()
    rows, notice_date = parse_notice_html(html, "https://www.sse.com.cn/example.shtml", "SSE", "SH", "2026-08-07T00:00:00+00:00")
    by_code = {row["security_code"]: row for row in rows}
    assert notice_date == "2026-07-09"
    assert by_code["00754"]["direction"] == "OUT"
    assert by_code["00754"]["effective_from"] is None
    assert by_code["00754"]["effective_rule"] == "NEXT_STOCK_CONNECT_TRADING_DAY"
    assert by_code["02983"]["direction"] == "IN"


def test_parse_szse_explicit_effective_date():
    html = """
    <html><body>
      <h1>关于深港通下的港股通标的证券名单调整的公告</h1>
      <p>时间：2026-06-30</p>
      <p>港股通标的证券名单发生调整并自2026年06月30日起生效。</p>
      <table><tr><th>代码</th><th>简称</th><th>调整方向</th></tr>
      <tr><td>01448</td><td>福寿园</td><td>调出</td></tr></table>
    </body></html>
    """.encode()
    rows, notice_date = parse_notice_html(html, "https://www.szse.cn/example.html", "SZSE", "SZ", "2026-08-07T00:00:00+00:00")
    assert notice_date == "2026-06-30"
    assert rows[0]["security_code"] == "01448"
    assert rows[0]["direction"] == "OUT"
    assert rows[0]["effective_from"] == "2026-06-30"
    assert rows[0]["effective_rule"] == "EXPLICIT_IN_NOTICE"


def _calendar_2026() -> dict:
    return {
        "year": 2026,
        "full_day_non_service_dates": [
            "2026-04-03", "2026-04-06", "2026-04-07",
            "2026-07-01",
        ],
    }


def test_next_service_day_normal_weekday():
    assert next_service_day(date(2026, 7, 9), _calendar_2026()) == date(2026, 7, 10)


def test_next_service_day_skips_weekend_and_official_closures():
    # 2026-04-03 and 04-06/07 are full-day Southbound closures; 04-04/05 weekend.
    assert next_service_day(date(2026, 4, 2), _calendar_2026()) == date(2026, 4, 8)


def test_effective_date_resolution_marks_future_event_without_applying_it_early():
    events = pd.DataFrame([
        {
            "security_code": "00754",
            "channel": "SH",
            "direction": "OUT",
            "announcement_date": "2026-07-09",
            "effective_from": None,
            "effective_rule": "NEXT_STOCK_CONNECT_TRADING_DAY",
        }
    ])
    result = resolve_events(events, _calendar_2026(), "2026-07-09").iloc[0]
    assert result["effective_from"] == "2026-07-10"
    assert bool(result["future_event"]) is True


def test_explicit_effective_date_is_preserved():
    events = pd.DataFrame([
        {
            "security_code": "01448",
            "channel": "SZ",
            "direction": "OUT",
            "announcement_date": "2026-06-30",
            "effective_from": "2026-06-30",
            "effective_rule": "EXPLICIT_IN_NOTICE",
        }
    ])
    result = resolve_events(events, _calendar_2026(), "2026-06-30").iloc[0]
    assert result["effective_from"] == "2026-06-30"
    assert bool(result["future_event"]) is False
