from __future__ import annotations

import pandas as pd

from scripts import fmdl3ebc_core as bc


def test_symbol_from_code_routes_exchanges():
    assert bc.symbol_from_code("600000") == "600000.SH"
    assert bc.symbol_from_code("000001") == "000001.SZ"
    assert bc.symbol_from_code("920001") == "920001.BJ"


def test_financial_title_classification_and_period():
    assert bc.classify_financial_title("2026年半年度报告") == "FINANCIAL_DISCLOSURE_NEW"
    assert bc.classify_financial_title("2025年年度报告更正公告") == "FINANCIAL_DISCLOSURE_CORRECTION"
    assert bc.classify_financial_title("关于前期会计差错更正及追溯调整的公告") == "FINANCIAL_RESTATEMENT"
    assert bc.period_end_from_title("2026年半年度报告") == "2026-06-30"
    assert bc.period_end_from_title("2025年年度报告修订版") == "2025-12-31"


def test_semantic_hash_is_order_independent():
    left = pd.DataFrame([{"event_id": "b", "symbol": "2", "value": 2}, {"event_id": "a", "symbol": "1", "value": 1}])
    right = left.iloc[::-1].reset_index(drop=True)
    assert bc.semantic_frame_hash(left) == bc.semantic_frame_hash(right)


def test_historical_replay_preserves_revision_case():
    frame = pd.DataFrame([
        {"symbol": "000001.SZ", "report_period_end": "2025-12-31", "revision_sequence": 1, "filing_title": "2025年年度报告", "available_from": "2026-03-20T09:30:00+08:00", "revision_id": "a"},
        {"symbol": "000001.SZ", "report_period_end": "2025-12-31", "revision_sequence": 2, "filing_title": "2025年年度报告更正公告", "available_from": "2026-04-01T09:30:00+08:00", "revision_id": "b"},
    ])
    cases = bc.pick_historical_replay_cases(frame)
    assert any(case["event_type"] == "FINANCIAL_DISCLOSURE_NEW" for case in cases)
    assert any(case["event_type"] == "FINANCIAL_DISCLOSURE_CORRECTION" for case in cases)


def test_semantic_hash_excludes_operational_timestamps():
    left = pd.DataFrame([{"event_id": "a", "symbol": "1", "detected_at": "2026-01-01T00:00:00+08:00"}])
    right = pd.DataFrame([{"event_id": "a", "symbol": "1", "detected_at": "2026-01-02T00:00:00+08:00"}])
    assert bc.semantic_frame_hash(left) == bc.semantic_frame_hash(right)


def test_non_report_update_notice_is_not_financial_report():
    assert not bc.is_financial_report_title("关于公司地址更新的公告")
    assert bc.is_financial_report_title("2025年年度报告补充更正公告")


def test_revision_sequence_forces_revision_classification_without_title_token():
    frame = pd.DataFrame([
        {"symbol": "000001.SZ", "report_period_end": "2025-12-31", "revision_sequence": 1, "filing_title": "2025年年度报告", "available_from": "2026-03-20T09:30:00+08:00", "revision_id": "a"},
        {"symbol": "000001.SZ", "report_period_end": "2025-12-31", "revision_sequence": 2, "filing_title": "2025年年度报告（修正版）", "available_from": "2026-04-01T09:30:00+08:00", "revision_id": "b"},
    ])
    cases = bc.pick_historical_replay_cases(frame)
    assert any(case["event_type"] != "FINANCIAL_DISCLOSURE_NEW" for case in cases)
