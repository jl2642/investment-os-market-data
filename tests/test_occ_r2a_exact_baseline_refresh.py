from __future__ import annotations

import json

import pandas as pd

from scripts.run_occ_r2a_exact_baseline_refresh import refresh_exact_detail


def _row(metric_id: str, value: float, inputs: dict) -> dict:
    return {
        "symbol": "000001.SZ",
        "name": "T",
        "sector_profile": "GENERAL_NON_FINANCIAL",
        "metric_id": metric_id,
        "metric_name": metric_id,
        "metric_family": "VALUATION",
        "valuation_version": "1",
        "market_as_of_date": "2026-08-28",
        "market_cutoff_timestamp": "2026-08-28T15:00:00+08:00",
        "total_market_cap_cny": 1000.0,
        "metric_value": value,
        "output_unit": "RATIO",
        "quality_state": "VALID",
        "warning_codes": "",
        "denominator_period_end": "2026-06-30",
        "denominator_available_from": "2026-08-20T10:00:00+08:00",
        "required_inputs": "|".join(inputs),
        "input_values_json": json.dumps({"total_market_cap_cny": 1000.0, **inputs}),
        "input_states_json": json.dumps({k: "VALID" for k in {"total_market_cap_cny", *inputs}}),
        "input_available_from_json": json.dumps({k: "2026-08-20T10:00:00+08:00" for k in {"total_market_cap_cny", *inputs}}),
        "input_fact_ids_json": "{}",
        "formula": "x",
        "capitalization_lineage_id": "old",
        "metric_lineage_id": "a" * 64,
        "decision_grade": True,
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def test_exact_financial_denominator_is_preserved_while_market_moves() -> None:
    detail = pd.DataFrame([
        _row("VAL_PE_TTM", 10.0, {"net_income_parent_ttm": 100.0}),
        _row("VAL_EARNINGS_YIELD_TTM", 0.1, {"net_income_parent_ttm": 100.0}),
        _row("VAL_PS_TTM", 2.0, {"revenue_ttm": 500.0}),
        _row("VAL_EV_SALES_TTM", 2.2, {
            "short_term_debt": 100.0,
            "long_term_debt": 50.0,
            "bonds_payable": 0.0,
            "cash_equivalents": 50.0,
            "revenue_ttm": 500.0,
        }),
    ])
    base = pd.DataFrame([{"symbol": "000001.SZ", "close": 10.0}])
    target = pd.DataFrame([{"symbol": "000001.SZ", "close": 12.0}])
    out, metrics = refresh_exact_detail(
        detail, base, target,
        target_date="2026-08-31",
        target_market_release_id="MKT_NEW",
        exact_release_id="EXACT_828",
    )
    rows = {r["metric_id"]: r for r in out.to_dict("records")}
    assert rows["VAL_PE_TTM"]["metric_value"] == 12.0
    assert round(rows["VAL_EARNINGS_YIELD_TTM"]["metric_value"], 10) == round(100.0 / 1200.0, 10)
    assert rows["VAL_PS_TTM"]["metric_value"] == 2.4
    assert rows["VAL_EV_SALES_TTM"]["metric_value"] == 2.6
    assert json.loads(rows["VAL_PE_TTM"]["input_values_json"])["net_income_parent_ttm"] == 100.0
    assert rows["VAL_PE_TTM"]["market_as_of_date"] == "2026-08-31"
    assert metrics["market_coverage_ratio"] == 1.0


def test_missing_target_price_fails_closed_at_metric_level() -> None:
    detail = pd.DataFrame([_row("VAL_PE_TTM", 10.0, {"net_income_parent_ttm": 100.0})])
    base = pd.DataFrame([{"symbol": "000001.SZ", "close": 10.0}])
    target = pd.DataFrame([{"symbol": "000001.SZ", "close": None}])
    out, metrics = refresh_exact_detail(
        detail, base, target,
        target_date="2026-08-31",
        target_market_release_id="MKT_NEW",
        exact_release_id="EXACT_828",
    )
    row = out.iloc[0]
    assert row["quality_state"] == "CONTROLLED_CAPITALIZATION_QUARANTINE"
    assert bool(row["decision_grade"]) is False
    assert pd.isna(row["metric_value"])
    assert metrics["market_coverage_ratio"] == 0.0
