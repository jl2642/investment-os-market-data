from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.fmdl3d_final_core import (
    build_unified_current,
    cross_layer_numeric_mismatch_count,
    market_cap_replay_error_count,
    replay_row_hashes,
    shareholder_yield_replay_error_count,
)


def frames():
    cap = pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "name": "测试公司",
                "exchange": "SH",
                "board": "SH_MAIN",
                "price_as_of_date": "2026-07-17",
                "close": 10.0,
                "total_shares": 1000.0,
                "float_a_shares": 800.0,
                "total_market_cap_cny": 10000.0,
                "float_market_cap_cny": 8000.0,
                "capitalization_state": "VALID",
                "lineage_id": "a" * 64,
            }
        ]
    )
    val = pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "sector_profile": "GENERAL_NON_FINANCIAL",
                "market_as_of_date": "2026-07-17",
                "total_market_cap_cny": 10000.0,
                "float_market_cap_cny": 8000.0,
                "pe_ttm": 10.0,
                "pe_ttm_state": "VALID",
                "earnings_yield_ttm": 0.1,
                "earnings_yield_ttm_state": "VALID",
                "pb": 2.0,
                "pb_state": "VALID",
                "ps_ttm": 1.0,
                "ps_ttm_state": "VALID",
                "fcf_yield_ttm": 0.05,
                "fcf_yield_ttm_state": "VALID",
                "ev_sales_ttm": 1.1,
                "ev_sales_ttm_state": "VALID",
                "ev_operating_income_ttm": 8.0,
                "ev_operating_income_ttm_state": "VALID",
                "valid_metric_count": 7,
                "decision_grade_metric_count": 7,
                "row_hash": "b" * 64,
            }
        ]
    )
    shareholder = pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "market_as_of_date": "2026-07-17",
                "total_market_cap_cny": 10000.0,
                "implemented_cash_dividend_per_share_ttm": 0.5,
                "implemented_cash_dividend_total_cny_ttm": 500.0,
                "dividend_yield_ttm": 0.05,
                "completed_buyback_yield_ttm": 0.02,
                "completed_issuance_dilution_yield_ttm": 0.01,
                "shareholder_yield_ttm": 0.06,
                "shareholder_return_state": "COMPLETE",
                "complete_shareholder_yield": True,
                "lineage_ids_json": '["event"]',
            }
        ]
    )
    return cap, val, shareholder


def test_unified_current_preserves_component_evidence_and_hashes():
    cap, val, shareholder = frames()
    releases = {
        "FMDL-3D-A": "A",
        "FMDL-3D-B": "B",
        "FMDL-3D-C": "C",
        "FMDL-3D-D": "D",
    }
    current = build_unified_current(cap, val, shareholder, releases)
    row = current.iloc[0]
    assert row["symbol"] == "600000.SH"
    assert row["total_market_cap_cny"] == 10000.0
    assert row["pe_ttm"] == 10.0
    assert row["shareholder_yield_ttm"] == 0.06
    assert row["trade_authority"] == "NONE"
    assert replay_row_hashes(current) == 0


def test_market_cap_and_shareholder_yield_replay():
    cap, _, shareholder = frames()
    cap_errors, cap_diff = market_cap_replay_error_count(cap, 0.001)
    shareholder_errors, shareholder_diff = shareholder_yield_replay_error_count(
        shareholder, 1e-12
    )
    assert cap_errors == 0
    assert cap_diff == 0.0
    assert shareholder_errors == 0
    assert np.isclose(shareholder_diff, 0.0)


def test_cross_layer_market_cap_mismatch_is_detected():
    cap, val, shareholder = frames()
    assert sum(cross_layer_numeric_mismatch_count(cap, val, shareholder, 0.001).values()) == 0
    val.loc[0, "total_market_cap_cny"] = 10001.0
    mismatches = cross_layer_numeric_mismatch_count(cap, val, shareholder, 0.001)
    assert mismatches["capitalization_vs_valuation_total_market_cap"] == 1


def test_incomplete_shareholder_row_is_not_formula_scored():
    _, _, shareholder = frames()
    shareholder.loc[0, "complete_shareholder_yield"] = False
    shareholder.loc[0, "shareholder_yield_ttm"] = np.nan
    errors, difference = shareholder_yield_replay_error_count(shareholder, 1e-12)
    assert errors == 0
    assert difference == 0.0
