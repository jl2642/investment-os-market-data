from __future__ import annotations

import json

import pandas as pd

from scripts import fmdl3dc_core as core


def config():
    return {
        "business_timezone": "Asia/Shanghai",
        "engine": {
            "market_cutoff_time": "15:00:00",
            "valuation_version": "1.0.0",
            "valid_input_states": ["VALID", "VALID_WITH_WARNING"],
        },
    }


def cap_row():
    return pd.Series(
        {
            "symbol": "600000.SH",
            "name": "测试公司",
            "exchange": "SH",
            "board": "SH_MAIN",
            "price_as_of_date": "2026-07-17",
            "total_market_cap_cny": 1000.0,
            "float_market_cap_cny": 800.0,
            "capitalization_state": "VALID",
            "lineage_id": "a" * 64,
        }
    )


def metric(metric_id: str, profiles: str = "GENERAL_NON_FINANCIAL"):
    formulas = {
        "VAL_PE_TTM": "DIVIDE(total_market_cap_cny,net_income_parent_ttm)",
        "VAL_PS_TTM": "DIVIDE(total_market_cap_cny,revenue_ttm)",
        "VAL_FCF_YIELD_TTM": "DIVIDE(ADD(cfo_ttm,capex_ttm),total_market_cap_cny)",
        "VAL_EV_SALES_TTM": "DIVIDE(enterprise_value_cny,revenue_ttm)",
    }
    required = {
        "VAL_PE_TTM": "total_market_cap_cny|net_income_parent_ttm",
        "VAL_PS_TTM": "total_market_cap_cny|revenue_ttm",
        "VAL_FCF_YIELD_TTM": "cfo_ttm|capex_ttm|total_market_cap_cny",
        "VAL_EV_SALES_TTM": "total_market_cap_cny|short_term_debt|long_term_debt|bonds_payable|cash_equivalents|revenue_ttm",
    }
    return pd.Series(
        {
            "metric_id": metric_id,
            "metric_name": metric_id,
            "metric_family": "VALUATION",
            "formula": formulas[metric_id],
            "required_inputs": required[metric_id],
            "output_unit": "RATIO",
            "applicable_sector_profiles": profiles,
        }
    )


def derived_row(values: dict, states: dict | None = None, available: dict | None = None):
    states = states or {key: "VALID" for key in values}
    available = available or {key: "2026-06-30T09:00:00+08:00" for key in values}
    fact_ids = {key: [f"fact-{key}"] for key in values}
    return pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "period_end": "2026-06-30",
                "fiscal_period_type": "H1",
                **values,
                "input_states_json": json.dumps(states),
                "input_available_from_json": json.dumps(available),
                "input_fact_ids_json": json.dumps(fact_ids),
            }
        ]
    )


def test_future_denominator_is_blocked():
    rows = derived_row(
        {"net_income_parent_ttm": 100.0},
        available={"net_income_parent_ttm": "2026-07-17T16:00:00+08:00"},
    )
    result = core.evaluate_metric(
        cap_row(), "GENERAL_NON_FINANCIAL", rows, metric("VAL_PE_TTM"), config()
    )
    assert result["quality_state"] == "FUTURE_DENOMINATOR_BLOCKED"
    assert result["metric_value"] is None


def test_non_positive_earnings_never_create_valid_pe():
    rows = derived_row({"net_income_parent_ttm": -10.0})
    result = core.evaluate_metric(
        cap_row(), "GENERAL_NON_FINANCIAL", rows, metric("VAL_PE_TTM"), config()
    )
    assert result["quality_state"] == "NON_POSITIVE_EARNINGS"
    assert result["metric_value"] is None


def test_general_company_ps_is_not_forced_onto_bank():
    rows = derived_row({"revenue_ttm": 500.0})
    result = core.evaluate_metric(
        cap_row(), "BANK", rows, metric("VAL_PS_TTM"), config()
    )
    assert result["quality_state"] == "NOT_APPLICABLE_SECTOR"
    assert result["metric_value"] is None


def test_negative_fcf_is_valid_negative_evidence_with_warning():
    rows = derived_row({"cfo_ttm": 20.0, "capex_ttm": -50.0})
    result = core.evaluate_metric(
        cap_row(),
        "GENERAL_NON_FINANCIAL",
        rows,
        metric("VAL_FCF_YIELD_TTM"),
        config(),
    )
    assert result["quality_state"] == "VALID_WITH_WARNING"
    assert result["metric_value"] == -0.03
    assert result["decision_grade"] is True


def test_incomplete_ev_components_remain_missing():
    rows = derived_row(
        {
            "short_term_debt": 10.0,
            "long_term_debt": 20.0,
            "bonds_payable": 5.0,
            "cash_equivalents": None,
            "revenue_ttm": 500.0,
        },
        states={
            "short_term_debt": "VALID",
            "long_term_debt": "VALID",
            "bonds_payable": "VALID",
            "cash_equivalents": "MISSING_REQUIRED_INPUT",
            "revenue_ttm": "VALID",
        },
    )
    result = core.evaluate_metric(
        cap_row(),
        "GENERAL_NON_FINANCIAL",
        rows,
        metric("VAL_EV_SALES_TTM"),
        config(),
    )
    assert result["quality_state"] == "MISSING_REQUIRED_INPUT"
    assert result["metric_value"] is None
