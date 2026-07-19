from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scripts.fmdl3dd_core import (
    build_shareholder_return_current,
    classify_share_change,
    derive_share_change_events,
    normalize_dividend_frame,
)


def cfg():
    return {
        "source": {
            "dividend_source_id": "EASTMONEY_DIVIDEND_DISTRIBUTION_DETAIL",
            "dividend_source_adapter": "akshare.stock_fhps_detail_em",
            "share_change_source_id": "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
            "share_change_source_adapter": "FMDL3DB_EFFECTIVE_SHARE_LEDGER_DERIVATION",
            "ttm_days": 365,
        },
        "dividend_policy": {
            "implemented_stage_tokens": ["实施分配", "实施方案", "已实施", "实施完成"],
            "cash_ratio_basis_shares": 10.0,
            "implementation_date_priority": ["除权除息日", "股权登记日", "公告日期", "预案公告日"],
        },
        "share_change_policy": {
            "minimum_absolute_share_change": 1.0,
            "buyback_or_cancellation_tokens": ["回购", "注销"],
            "private_placement_tokens": ["增发", "非公开发行", "向特定对象发行"],
            "rights_issue_tokens": ["配股"],
            "convertible_conversion_tokens": ["转股", "可转债"],
            "equity_incentive_tokens": ["股权激励", "限制性股票"],
            "neutral_rescaling_tokens": ["送股", "转增", "拆股"],
        },
    }


def test_implemented_cash_dividend_normalizes_per_share():
    frame = pd.DataFrame([{
        "报告期": "2025-12-31",
        "现金分红-现金分红比例": 5.0,
        "预案公告日": "2026-03-01",
        "股权登记日": "2026-05-19",
        "除权除息日": "2026-05-20",
        "方案进度": "实施分配",
    }])
    result = normalize_dividend_frame("600000.SH", "测试", frame, "2026-07-19T10:00:00+08:00", cfg())
    row = result.iloc[0]
    assert row["event_stage"] == "IMPLEMENTED"
    assert row["shareholder_yield_effective"]
    assert np.isclose(row["cash_amount_per_share"], 0.5)
    assert row["effective_date"] == "2026-05-20"


def test_announced_dividend_does_not_enter_yield():
    frame = pd.DataFrame([{
        "报告期": "2025-12-31",
        "现金分红-现金分红比例": 5.0,
        "预案公告日": "2026-03-01",
        "方案进度": "董事会预案",
    }])
    result = normalize_dividend_frame("600000.SH", "测试", frame, "2026-07-19T10:00:00+08:00", cfg())
    row = result.iloc[0]
    assert row["event_stage"] == "ANNOUNCED"
    assert not row["shareholder_yield_effective"]


def test_share_change_classification_is_stage_safe():
    policy = cfg()["share_change_policy"]
    assert classify_share_change("回购股份注销", -100.0, policy) == ("SHARE_CANCELLATION", "VALID", True)
    assert classify_share_change("向特定对象发行", 100.0, policy) == ("PRIVATE_PLACEMENT", "VALID", True)
    assert classify_share_change("资本公积转增", 100.0, policy) == ("STOCK_DIVIDEND_OR_SPLIT", "VALID", False)
    assert classify_share_change("其他", 100.0, policy) == ("UNCLASSIFIED_SHARE_CHANGE", "UNCLASSIFIED_SHARE_CHANGE", False)


def test_future_share_change_is_blocked():
    ledger = pd.DataFrame([
        {"symbol": "600000.SH", "name": "测试", "source_effective_date": "2026-01-01", "total_shares": 1000.0, "change_reason": "初始", "source_row_hash": "a", "retrieved_at": "2026-07-19T10:00:00+08:00"},
        {"symbol": "600000.SH", "name": "测试", "source_effective_date": "2026-08-01", "total_shares": 900.0, "change_reason": "回购股份注销", "source_row_hash": "b", "retrieved_at": "2026-07-19T10:00:00+08:00"},
    ])
    events = derive_share_change_events(ledger, cfg(), "2026-07-17")
    row = events.iloc[0]
    assert row["event_state"] == "FUTURE_EVENT_BLOCKED"
    assert not row["shareholder_yield_effective"]


def test_shareholder_yield_formula_replays():
    cap = pd.DataFrame([{
        "symbol": "600000.SH", "name": "测试", "price_as_of_date": "2026-07-17", "close": 10.0,
        "total_shares": 1000.0, "total_market_cap_cny": 10000.0,
    }])
    attempts = pd.DataFrame([{"symbol": "600000.SH", "source_state": "SUCCESS"}])
    ledger = pd.DataFrame([{"symbol": "600000.SH", "source_effective_date": "2025-01-01", "total_shares": 1000.0}])
    events = pd.DataFrame([
        {"event_id": "d", "symbol": "600000.SH", "event_type": "CASH_DIVIDEND", "effective_date": "2026-05-01", "cash_amount_per_share": 0.5, "cash_amount_total_cny": 500.0, "share_change_ratio": None, "shareholder_yield_effective": True},
        {"event_id": "b", "symbol": "600000.SH", "event_type": "SHARE_CANCELLATION", "effective_date": "2026-06-01", "cash_amount_per_share": None, "cash_amount_total_cny": None, "share_change_ratio": -0.02, "shareholder_yield_effective": True},
        {"event_id": "i", "symbol": "600000.SH", "event_type": "PRIVATE_PLACEMENT", "effective_date": "2026-07-01", "cash_amount_per_share": None, "cash_amount_total_cny": None, "share_change_ratio": 0.01, "shareholder_yield_effective": True},
    ])
    current = build_shareholder_return_current(cap, attempts, events, ledger, cfg(), {"x": "y"})
    row = current.iloc[0]
    assert np.isclose(row["dividend_yield_ttm"], 0.05)
    assert np.isclose(row["completed_buyback_yield_ttm"], 0.02)
    assert np.isclose(row["completed_issuance_dilution_yield_ttm"], 0.01)
    assert np.isclose(row["shareholder_yield_ttm"], 0.06)
    assert row["complete_shareholder_yield"]
