from __future__ import annotations

import json

import pandas as pd

from scripts import fmdl3ede_core as core


def cfg():
    return {
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "propagation": {
            "price_multiple_fields": ["pe_ttm", "pb", "ps_ttm", "ev_sales_ttm", "ev_operating_income_ttm"],
            "inverse_price_fields": ["earnings_yield_ttm", "fcf_yield_ttm", "dividend_yield_ttm", "completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm"],
            "shareholder_yield_components": ["dividend_yield_ttm", "completed_buyback_yield_ttm", "completed_issuance_dilution_yield_ttm"],
        },
    }


def baseline():
    return pd.DataFrame([{
        "symbol": "600000.SH", "name": "A", "exchange": "SH", "board": "SH_MAIN", "sector_profile": "GENERAL",
        "market_as_of_date": "2026-07-16", "close": 10.0, "total_shares": 100.0, "float_a_shares": 80.0,
        "total_market_cap_cny": 1000.0, "float_market_cap_cny": 800.0, "capitalization_state": "VALID",
        "pe_ttm": 10.0, "pe_ttm_state": "VALID", "earnings_yield_ttm": 0.1, "earnings_yield_ttm_state": "VALID",
        "pb": 2.0, "pb_state": "VALID", "ps_ttm": 3.0, "ps_ttm_state": "VALID", "fcf_yield_ttm": 0.05,
        "fcf_yield_ttm_state": "VALID", "ev_sales_ttm": 4.0, "ev_sales_ttm_state": "VALID",
        "ev_operating_income_ttm": 8.0, "ev_operating_income_ttm_state": "VALID",
        "valuation_valid_metric_count": 7, "valuation_decision_grade_metric_count": 7,
        "implemented_cash_dividend_per_share_ttm": 0.2, "implemented_cash_dividend_total_cny_ttm": 20.0,
        "dividend_yield_ttm": 0.02, "completed_buyback_yield_ttm": 0.01,
        "completed_issuance_dilution_yield_ttm": -0.005, "shareholder_yield_ttm": 0.025,
        "shareholder_return_state": "COMPLETE", "complete_shareholder_yield": True,
        "capitalization_lineage_id": "x", "valuation_row_hash": "y",
        "shareholder_event_lineage_ids_json": "[]", "component_release_ids_json": json.dumps({"FMDL-3D": "base"}),
        "row_hash": "0" * 64, "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY", "trade_authority": "NONE",
    }])


def delta():
    return pd.DataFrame([{"symbol": "600000.SH", "refreshed_close": 12.0, "trade_authority": "NONE"}])


def test_incremental_equals_full_rebuild_and_is_idempotent():
    base = baseline()
    inc = core.incremental_propagate(base, delta(), cfg=cfg(), release_id="R", incremental_release_id="BC", target_date="2026-07-17")
    full = core.full_rebuild(base, delta(), cfg=cfg(), release_id="R", incremental_release_id="BC", target_date="2026-07-17")
    assert int(core.comparison_audit(inc, full)["mismatch_count"].sum()) == 0
    replay = core.incremental_propagate(inc, delta(), cfg=cfg(), release_id="R", incremental_release_id="BC", target_date="2026-07-17")
    assert int(core.comparison_audit(inc, replay)["mismatch_count"].sum()) == 0
    assert inc.iloc[0]["total_market_cap_cny"] == 1200.0
    assert inc.iloc[0]["pe_ttm"] == 12.0
    assert round(inc.iloc[0]["earnings_yield_ttm"], 8) == round(0.1 / 1.2, 8)
    assert inc.iloc[0]["trade_authority"] == "NONE"


def test_failure_inputs_are_rejected():
    base = baseline()
    duplicate = pd.concat([delta(), delta()], ignore_index=True)
    events = pd.DataFrame([{"event_id": "a", "effective_at": "2026-07-18T00:00:00+08:00", "trade_authority": "NONE"}])
    errors = core.validate_delta_inputs(base, duplicate, events, target_date="2026-07-17")
    assert "DUPLICATE_MARKET_SYMBOL" in errors
    assert any(error.startswith("FUTURE_FINANCIAL_EVENT") for error in errors)


def test_semantic_hash_ignores_order():
    left = pd.DataFrame([{"symbol": "2", "value": 2}, {"symbol": "1", "value": 1}])
    right = left.iloc[::-1].reset_index(drop=True)
    assert core.semantic_frame_hash(left) == core.semantic_frame_hash(right)


def test_stable_hash_canonicalizes_non_finite_values():
    assert core.stable_hash({"value": float("nan")}) == core.stable_hash({"value": None})
    assert core.stable_hash({"value": float("inf")}) == core.stable_hash({"value": None})
