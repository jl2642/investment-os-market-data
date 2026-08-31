import json

import pandas as pd

from scripts import fmdl3ede_core as core
from scripts.run_occ_r2a_valuation_refresh import build_market_delta


def test_build_market_delta_preserves_financial_baseline_scope() -> None:
    baseline = pd.DataFrame([
        {"symbol": "A", "close": 10.0},
        {"symbol": "B", "close": 20.0},
        {"symbol": "C", "close": 30.0},
    ])
    snapshot = pd.DataFrame([
        {"symbol": "A", "close": 11.0},
        {"symbol": "B", "close": 21.0},
        {"symbol": "X", "close": 99.0},
    ])
    delta, metrics = build_market_delta(baseline, snapshot)
    assert len(delta) == 3
    assert metrics["baseline_symbol_count"] == 3
    assert metrics["source_symbol_count"] == 3
    assert metrics["source_symbols_outside_financial_baseline"] == 1
    assert metrics["financial_baseline_symbols_missing_from_source"] == 1
    assert metrics["matched_positive_close_count"] == 2
    assert metrics["market_coverage_ratio"] == 2 / 3


def test_market_propagation_updates_valuation_but_not_financial_denominator() -> None:
    cfg = json.load(open("config/fmdl3ede_propagation_resilience.json", encoding="utf-8"))
    baseline = pd.DataFrame([{
        "symbol": "A",
        "close": 10.0,
        "total_shares": 100.0,
        "float_a_shares": 80.0,
        "total_market_cap_cny": 1000.0,
        "float_market_cap_cny": 800.0,
        "pe_ttm": 20.0,
        "pb": 2.0,
        "ps_ttm": 4.0,
        "ev_sales_ttm": 5.0,
        "ev_operating_income_ttm": 10.0,
        "earnings_yield_ttm": 0.05,
        "fcf_yield_ttm": 0.10,
        "dividend_yield_ttm": 0.03,
        "completed_buyback_yield_ttm": 0.01,
        "completed_issuance_dilution_yield_ttm": -0.005,
        "shareholder_yield_ttm": 0.035,
        "market_as_of_date": "2026-07-17",
        "component_release_ids_json": "{}",
        "capitalization_lineage_id": "old",
        "valuation_row_hash": "old",
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
        "row_hash": "old",
    }])
    delta = pd.DataFrame([{
        "symbol": "A",
        "baseline_close": 10.0,
        "refreshed_close": 20.0,
    }])
    refreshed = core.incremental_propagate(
        baseline,
        delta,
        cfg=cfg,
        release_id="R2A_TEST",
        incremental_release_id="R2A_MARKET_ONLY",
        target_date="2026-08-28",
    ).iloc[0]
    assert refreshed["close"] == 20.0
    assert refreshed["total_market_cap_cny"] == 2000.0
    assert refreshed["pe_ttm"] == 40.0
    assert refreshed["pb"] == 4.0
    assert refreshed["fcf_yield_ttm"] == 0.05
    assert refreshed["market_as_of_date"] == "2026-08-28"
    assert refreshed["trade_authority"] == "NONE"
