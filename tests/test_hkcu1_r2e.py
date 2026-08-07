from __future__ import annotations

import pandas as pd

from pipeline.hkcu1_r2e_merge_fmdl5e import build, service_day_age


def _contract(max_age=5):
    return {
        "accepted_fmdl5e_status": "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED",
        "freshness": {"maximum_fmdl5e_age_stock_connect_service_days": max_age},
        "investable_gate": {
            "required_eligibility_prefix": "BUY_ELIGIBLE",
            "allowed_fmdl5e_investability_status": ["ELIGIBLE_CORE", "ELIGIBLE_WATCH"],
            "allowed_security_types": ["COMMON_EQUITY"],
            "minimum_avg_turnover_hkd_20d": 20_000_000,
            "minimum_active_trade_ratio_60d": 0.9,
            "maximum_zero_volume_days_20d": 2,
            "require_decision_grade_financials": True,
        },
        "next_gate": "R2F",
    }


def _calendar():
    return {"full_day_non_service_dates": ["2026-07-01"]}


def _decision(as_of="2026-08-06"):
    return {
        "status": "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED",
        "release_id": "FMDL5E_TEST",
        "as_of_date": as_of,
        "hard_failures": [],
        "trade_authority": "NONE",
    }


def _eligibility():
    return pd.DataFrame([
        {"security_code": "00005", "combined_status": "BUY_ELIGIBLE_BOTH", "buy_eligible": True, "sell_only": False, "as_of_date": "2026-08-07"},
        {"security_code": "09999", "combined_status": "BUY_ELIGIBLE_BOTH", "buy_eligible": True, "sell_only": False, "as_of_date": "2026-08-07"},
        {"security_code": "00754", "combined_status": "SELL_ONLY", "buy_eligible": False, "sell_only": True, "as_of_date": "2026-08-07"},
    ])


def _screening():
    common = {
        "security_type": "COMMON_EQUITY", "investability_status": "ELIGIBLE_CORE",
        "avg_turnover_hkd_20d": 100_000_000, "active_trade_ratio_60d": 1.0,
        "zero_volume_days_20d": 0, "latest_close": 100.0,
        "financial_decision_grade": True, "market_latest_date": "2026-08-06",
        "as_of_date": "2026-08-06",
    }
    return pd.DataFrame([
        {**common, "security_id": "HKEX:00005", "stock_code_5d": "00005"},
        {**common, "security_id": "HKEX:00754", "stock_code_5d": "00754"},
        {**common, "security_id": "HKEX:00004", "stock_code_5d": "00004"},
    ])


def test_service_day_age_counts_weekdays_only():
    assert service_day_age("2026-07-21", "2026-08-07", _calendar()) == 13


def test_current_merge_excludes_sell_only_unknown_and_missing_fmdl5e():
    universe, exclusions, quality, decision = build(
        _eligibility(), _screening(), _decision(), _calendar(), _contract(), "2026-08-07"
    )
    assert decision["status"] == "PASS_CURRENT"
    assert set(universe["stock_code_5d"]) == {"00005"}
    reasons = exclusions.set_index("stock_code_5d")["r2e_gate_reason"].to_dict()
    assert "MISSING_FMDL5E_COVERAGE" in reasons["09999"]
    assert "NOT_SOUTHBOUND_BUY_ELIGIBLE" in reasons["00754"]
    assert "NOT_SOUTHBOUND_BUY_ELIGIBLE" in reasons["00004"]
    assert quality["sell_only_in_investable_count"] == 0
    assert quality["unknown_in_investable_count"] == 0


def test_stale_fmdl5e_builds_evidence_but_blocks_current_promotion():
    universe, _, quality, decision = build(
        _eligibility(), _screening(), _decision("2026-07-21"), _calendar(), _contract(), "2026-08-07"
    )
    assert len(universe) == 1
    assert quality["fmdl5e_age_stock_connect_service_days"] == 13
    assert quality["fmdl5e_stale"] is True
    assert decision["status"] == "BLOCKED_STALE_FMDL5E"
    assert decision["publication_allowed"] is False
    assert not universe["publication_eligible"].any()


def test_lkg_continuity_builds_evidence_but_never_publishes():
    universe, _, quality, decision = build(
        _eligibility(), _screening(), _decision(), _calendar(), _contract(), "2026-08-07", "LKG_CONTINUITY"
    )
    assert len(universe) == 1
    assert quality["eligibility_source_status"] == "LKG_CONTINUITY"
    assert quality["eligibility_source_fresh"] is False
    assert quality["provisional_only"] is True
    assert decision["status"] == "BLOCKED_SOURCE_CONTINUITY"
    assert decision["publication_allowed"] is False
    assert decision["canonical_action"] == "KEEP_PREVIOUS_CANONICAL_UNCHANGED"
    assert not universe["publication_eligible"].any()


def test_lkg_continuity_and_stale_fmdl_are_both_preserved_in_decision():
    universe, _, quality, decision = build(
        _eligibility(), _screening(), _decision("2026-07-21"), _calendar(), _contract(), "2026-08-07", "LKG_CONTINUITY"
    )
    assert len(universe) == 1
    assert quality["fmdl5e_stale"] is True
    assert quality["eligibility_source_fresh"] is False
    assert decision["status"] == "BLOCKED_SOURCE_AND_STALE_FMDL5E"
    assert decision["publication_allowed"] is False
    assert decision["next_gate"] == "REFRESH_FMDL5E_THEN_RERUN_R2E"


def test_future_fmdl5e_fails_closed():
    _, _, quality, decision = build(
        _eligibility(), _screening(), _decision("2026-08-10"), _calendar(), _contract(), "2026-08-07"
    )
    assert "FMDL5E_FUTURE_VS_ELIGIBILITY" in quality["hard_failures"]
    assert decision["status"] == "BLOCKED_SOURCE_OR_QUALITY"
