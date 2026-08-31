import json

import pandas as pd

from scripts import fmdl3ede_core as core
from scripts.run_occ_r2a_valuation_refresh import build_market_delta, sanitize_market_only_metrics


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
        "ev_sales_ttm_state": "VALID",
        "ev_operating_income_ttm": 10.0,
        "ev_operating_income_ttm_state": "VALID",
        "pe_ttm_state": "VALID",
        "earnings_yield_ttm_state": "VALID",
        "pb_state": "VALID",
        "ps_ttm_state": "VALID",
        "fcf_yield_ttm_state": "VALID",
        "valuation_valid_metric_count": 7,
        "valuation_decision_grade_metric_count": 7,
        "earnings_yield_ttm": 0.05,
        "fcf_yield_ttm": 0.10,
        "dividend_yield_ttm": 0.03,
        "completed_buyback_yield_ttm": 0.01,
        "completed_issuance_dilution_yield_ttm": 0.005,
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
    )
    refreshed = sanitize_market_only_metrics(refreshed, baseline).iloc[0]
    assert refreshed["close"] == 20.0
    assert refreshed["total_market_cap_cny"] == 2000.0
    assert refreshed["pe_ttm"] == 40.0
    assert refreshed["pb"] == 4.0
    assert refreshed["fcf_yield_ttm"] == 0.05
    assert refreshed["dividend_yield_ttm"] == 0.015
    assert refreshed["completed_buyback_yield_ttm"] == 0.01
    assert refreshed["completed_issuance_dilution_yield_ttm"] == 0.005
    assert refreshed["shareholder_yield_ttm"] == 0.02
    assert pd.isna(refreshed["ev_sales_ttm"])
    assert pd.isna(refreshed["ev_operating_income_ttm"])
    assert refreshed["ev_sales_ttm_state"] == "BLOCKED_STALE_EV_COMPONENTS_PENDING_OCC_R2B"
    assert refreshed["valuation_valid_metric_count"] == 5
    assert refreshed["valuation_decision_grade_metric_count"] == 5
    assert refreshed["market_as_of_date"] == "2026-08-28"
    assert refreshed["trade_authority"] == "NONE"


def test_blocked_ev_metrics_remain_numeric_nan_for_comparison_audit() -> None:
    cfg = json.load(open("config/fmdl3ede_propagation_resilience.json", encoding="utf-8"))
    baseline = pd.DataFrame([{
        "symbol":"A","close":10.0,"total_shares":100.0,"float_a_shares":80.0,
        "total_market_cap_cny":1000.0,"float_market_cap_cny":800.0,
        "pe_ttm":20.0,"pe_ttm_state":"VALID","earnings_yield_ttm":0.05,"earnings_yield_ttm_state":"VALID",
        "pb":2.0,"pb_state":"VALID","ps_ttm":4.0,"ps_ttm_state":"VALID",
        "fcf_yield_ttm":0.10,"fcf_yield_ttm_state":"VALID",
        "ev_sales_ttm":5.0,"ev_sales_ttm_state":"VALID",
        "ev_operating_income_ttm":10.0,"ev_operating_income_ttm_state":"VALID",
        "valuation_valid_metric_count":7,"valuation_decision_grade_metric_count":7,
        "dividend_yield_ttm":0.03,"completed_buyback_yield_ttm":0.01,
        "completed_issuance_dilution_yield_ttm":0.005,"shareholder_yield_ttm":0.035,
        "market_as_of_date":"2026-07-17","component_release_ids_json":"{}",
        "capitalization_lineage_id":"old","valuation_row_hash":"old",
        "authority":"DATA_AND_RESEARCH_EVIDENCE_ONLY","trade_authority":"NONE","row_hash":"old",
    }])
    delta = pd.DataFrame([{"symbol":"A","baseline_close":10.0,"refreshed_close":20.0}])
    left = sanitize_market_only_metrics(core.incremental_propagate(
        baseline, delta, cfg=cfg, release_id="A", incremental_release_id="A", target_date="2026-08-28"
    ), baseline)
    right = sanitize_market_only_metrics(core.full_rebuild(
        baseline, delta, cfg=cfg, release_id="A", incremental_release_id="A", target_date="2026-08-28"
    ), baseline)
    assert pd.api.types.is_numeric_dtype(left["ev_sales_ttm"])
    audit = core.comparison_audit(left, right)
    assert int(audit["mismatch_count"].sum()) == 0
