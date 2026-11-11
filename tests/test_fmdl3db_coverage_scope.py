from __future__ import annotations

import pandas as pd
import pytest

from scripts.fmdl3db_core import capitalization_coverage_population


def fixture_rows():
    universe = pd.DataFrame([
        {"symbol": "600000.SH", "listing_status": "ACTIVE", "is_suspended": False},
        {"symbol": "000003.SZ", "listing_status": "SUSPENDED", "is_suspended": True},
        {"symbol": "000004.SZ", "listing_status": "SUSPENDED", "is_suspended": True},
    ])
    snapshot = pd.DataFrame([
        {"symbol": "600000.SH", "data_status": "TRADED", "record_quality": "VALID", "close": 10.0},
        {"symbol": "000003.SZ", "data_status": "SUSPENDED", "record_quality": "PARTIAL", "close": None},
        {"symbol": "000004.SZ", "data_status": "SUSPENDED", "record_quality": "PARTIAL", "close": None},
    ])
    current = pd.DataFrame([
        {"symbol": "600000.SH", "capitalization_state": "VALID",
         "state_reason": "ACCEPTED_PRICE_AND_PIT_EFFECTIVE_SHARES",
         "close": 10.0, "total_market_cap_cny": 1000.0, "float_market_cap_cny": 800.0},
        {"symbol": "000003.SZ", "capitalization_state": "PRICE_UNAVAILABLE",
         "state_reason": "NON_POSITIVE_OR_MISSING_CLOSE",
         "close": None, "total_market_cap_cny": None, "float_market_cap_cny": None},
        {"symbol": "000004.SZ", "capitalization_state": "PRICE_UNAVAILABLE",
         "state_reason": "NON_POSITIVE_OR_MISSING_CLOSE",
         "close": None, "total_market_cap_cny": None, "float_market_cap_cny": None},
    ])
    return universe, snapshot, current


def test_source_confirmed_no_price_suspensions_preserved_but_not_in_eligible_denominator():
    universe, snapshot, current = fixture_rows()
    result = capitalization_coverage_population(universe, snapshot, current)
    assert result["eligible_count"] == 1
    assert result["excluded_suspended_no_price_count"] == 2
    assert result["excluded_mask"].tolist() == [False, True, True]
    assert all(result["checks"].values())
    assert len(current) == 3  # Never remove/quasi-price the full source cohort.
    assert current["total_market_cap_cny"].notna().sum() == 1


def test_suspended_without_matching_universe_evidence_must_not_be_excluded():
    universe, snapshot, current = fixture_rows()
    universe.loc[1, "listing_status"] = "ACTIVE"
    result = capitalization_coverage_population(universe, snapshot, current)
    assert result["eligible_count"] == 2
    assert result["excluded_suspended_no_price_count"] == 1
    assert not result["checks"]["SOURCE_SUSPENDED_NO_PRICE_EXACTLY_CLASSIFIED"]
    assert not result["checks"]["SOURCE_SUSPENSIONS_MATCH_UNIVERSE"]


def test_missing_price_on_active_security_cannot_be_reclassified_as_suspension():
    universe, snapshot, current = fixture_rows()
    current.loc[0, "capitalization_state"] = "PRICE_UNAVAILABLE"
    current.loc[0, "total_market_cap_cny"] = None
    current.loc[0, "float_market_cap_cny"] = None
    current.loc[0, "close"] = None
    snapshot.loc[0, "close"] = None
    result = capitalization_coverage_population(universe, snapshot, current)
    assert result["eligible_count"] == 1
    assert result["excluded_mask"].tolist() == [False, True, True]


def test_malformed_suspension_quarantine_fails_closed():
    universe, snapshot, current = fixture_rows()
    current.loc[1, "total_market_cap_cny"] = 1234567.0
    result = capitalization_coverage_population(universe, snapshot, current)
    assert result["excluded_mask"].tolist() == [False, False, True]
    assert not result["checks"]["SOURCE_SUSPENDED_NO_PRICE_EXACTLY_CLASSIFIED"]


def test_duplicate_or_incoherent_roster_fails_closed():
    universe, snapshot, current = fixture_rows()
    with pytest.raises(ValueError, match="duplicate"):
        capitalization_coverage_population(
            pd.concat([universe, universe.iloc[[0]]], ignore_index=True),
            snapshot, current,
        )
    with pytest.raises(ValueError, match="exactly equal"):
        capitalization_coverage_population(universe.iloc[:2], snapshot, current)
