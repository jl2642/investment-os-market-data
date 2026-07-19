from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scripts.fmdl3da_core import (
    build_capitalization_snapshot,
    build_event_contract_samples,
    evaluate_metric,
)


def pilot_row(symbol="000001.SZ", profile="GENERAL_NON_FINANCIAL"):
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "name": "Test",
                "sector_profile": profile,
                "board": "SZ_MAIN",
                "expected_capitalization_state": "SUPPORTED",
                "pilot_role": "test",
            }
        ]
    )


def cap_evidence(symbol="000001.SZ", future=False):
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "price_as_of_date": "2026-07-17",
                "close": 10.0,
                "price_source_id": "FMDL1_ACCEPTED_CURRENT_PRICE",
                "price_source_timestamp": "2026-07-17T17:00:00+08:00",
                "share_effective_date": "2026-07-18" if future else "2026-07-01",
                "total_shares": 100.0,
                "float_a_shares": 80.0,
                "share_source_id": "EASTMONEY_EFFECTIVE_SHARE_CAPITAL",
                "future_effective_share_flag": future,
                "total_market_cap_cny": 1000.0,
                "float_market_cap_cny": 800.0,
                "capitalization_source_id": "COMPOSITE_CURRENT_CAPITALIZATION",
            }
        ]
    )


def derived_row(symbol="000001.SZ", net_income=100.0, profile="GENERAL_NON_FINANCIAL"):
    tokens = {
        "net_income_parent_ttm": net_income,
        "parent_equity": 500.0,
        "revenue_ttm": 800.0,
        "cfo_ttm": 90.0,
        "capex_ttm": -30.0,
        "short_term_debt": 20.0,
        "long_term_debt": 30.0,
        "bonds_payable": 10.0,
        "cash_equivalents": 40.0,
        "operating_income_ttm": 120.0,
    }
    states = {token: "VALID" for token in tokens}
    available = {token: "2026-04-30T09:30:00+08:00" for token in tokens}
    facts = {token: [f"{symbol}-{token}"] for token in tokens}
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "sector_profile": profile,
                "period_end": "2026-03-31",
                "fiscal_period_type": "Q1",
                **tokens,
                "input_states_json": json.dumps(states),
                "input_available_from_json": json.dumps(available),
                "input_fact_ids_json": json.dumps(facts),
            }
        ]
    )


def metric(metric_id, required, profiles="GENERAL_NON_FINANCIAL", build_stage="3D_A_PILOT"):
    formulas = {
        "VAL_PE_TTM": "DIVIDE(total_market_cap_cny,net_income_parent_ttm)",
        "VAL_PS_TTM": "DIVIDE(total_market_cap_cny,revenue_ttm)",
        "VAL_FCF_YIELD_TTM": "DIVIDE(ADD(cfo_ttm,capex_ttm),total_market_cap_cny)",
    }
    return pd.Series(
        {
            "metric_id": metric_id,
            "metric_name": metric_id,
            "metric_family": "VALUATION",
            "formula": formulas.get(metric_id, "NA"),
            "required_inputs": required,
            "output_unit": "RATIO",
            "applicable_sector_profiles": profiles,
            "denominator_rule": "TEST",
            "build_stage": build_stage,
            "decision_grade_policy": "DECISION_GRADE_WHEN_VALID",
            "warning_policy": "NONE",
            "trade_authority": "NONE",
        }
    )


def test_capitalization_replays_and_future_share_count_is_blocked():
    valid = build_capitalization_snapshot(
        pilot_row(), cap_evidence(), "FMDL3A_TEST"
    ).iloc[0]
    assert valid["capitalization_state"] == "VALID"
    assert valid["total_market_cap_cny"] == 1000.0
    assert valid["float_market_cap_cny"] == 800.0
    future = build_capitalization_snapshot(
        pilot_row(), cap_evidence(future=True), "FMDL3A_TEST"
    ).iloc[0]
    assert future["capitalization_state"] == "FUTURE_EFFECTIVE_SHARE_BLOCKED"
    assert pd.isna(future["total_market_cap_cny"])


def test_negative_earnings_never_create_valid_pe():
    cap = build_capitalization_snapshot(
        pilot_row(), cap_evidence(), "FMDL3A_TEST"
    ).iloc[0]
    result = evaluate_metric(
        metric("VAL_PE_TTM", "total_market_cap_cny|net_income_parent_ttm"),
        cap,
        derived_row(net_income=-10.0),
        "TEST",
    )
    assert result["metric_state"] == "NON_POSITIVE_EARNINGS"
    assert result["metric_value"] is None
    assert not result["decision_grade_eligible"]


def test_financial_profile_does_not_receive_ps():
    cap = build_capitalization_snapshot(
        pilot_row(profile="BANK"), cap_evidence(), "FMDL3A_TEST"
    ).iloc[0]
    result = evaluate_metric(
        metric(
            "VAL_PS_TTM",
            "total_market_cap_cny|revenue_ttm",
            profiles="GENERAL_NON_FINANCIAL|PRE_PROFIT_OR_NEGATIVE_EARNINGS",
        ),
        cap,
        derived_row(profile="BANK"),
        "TEST",
    )
    assert result["metric_state"] == "NOT_APPLICABLE_SECTOR"
    assert result["metric_value"] is None


def test_negative_fcf_yield_is_valid_negative_evidence():
    cap = build_capitalization_snapshot(
        pilot_row(), cap_evidence(), "FMDL3A_TEST"
    ).iloc[0]
    derived = derived_row()
    derived.loc[0, "cfo_ttm"] = 10.0
    derived.loc[0, "capex_ttm"] = -30.0
    result = evaluate_metric(
        metric(
            "VAL_FCF_YIELD_TTM",
            "cfo_ttm|capex_ttm|total_market_cap_cny",
        ),
        cap,
        derived,
        "TEST",
    )
    assert result["metric_state"] == "VALID"
    assert np.isclose(result["metric_value"], -0.02)


def test_shareholder_event_stage_controls():
    registry = pd.DataFrame(
        [
            {
                "event_type": "CASH_DIVIDEND",
                "effective_stage_for_share_count": "NONE",
                "effective_stage_for_shareholder_yield": "IMPLEMENTED",
            },
            {
                "event_type": "BUYBACK",
                "effective_stage_for_share_count": "NONE",
                "effective_stage_for_shareholder_yield": "COMPLETED",
            },
            {
                "event_type": "SHARE_CANCELLATION",
                "effective_stage_for_share_count": "COMPLETED",
                "effective_stage_for_shareholder_yield": "NONE",
            },
            {
                "event_type": "PRIVATE_PLACEMENT",
                "effective_stage_for_share_count": "COMPLETED",
                "effective_stage_for_shareholder_yield": "COMPLETED",
            },
            {
                "event_type": "STOCK_DIVIDEND_OR_SPLIT",
                "effective_stage_for_share_count": "IMPLEMENTED",
                "effective_stage_for_shareholder_yield": "NONE",
            },
        ]
    )
    events = build_event_contract_samples(registry)
    index = {
        (row.event_type, row.event_stage): row
        for row in events.itertuples(index=False)
    }
    assert not index[("BUYBACK", "ANNOUNCED")].shareholder_yield_effective
    assert index[("BUYBACK", "COMPLETED")].shareholder_yield_effective
    assert not index[("PRIVATE_PLACEMENT", "REGULATORY_APPROVED")].share_count_effective
    assert index[("PRIVATE_PLACEMENT", "COMPLETED")].share_count_effective
    assert not index[("CASH_DIVIDEND", "ANNOUNCED")].shareholder_yield_effective
    assert index[("CASH_DIVIDEND", "IMPLEMENTED")].shareholder_yield_effective
