"""Regression tests for the Phase 3 cross-session handoff from 2026-10-15."""
from __future__ import annotations

import copy

import pytest

from automation.portfolio_execution.phase3_session_preflight import session_readiness


def coherent_inputs():
    marks = {
        "status": "PASS",
        "data_watermark": "2026-10-15",
        "orders": 0,
        "trade_authority": "NONE",
    }
    lifecycle = {
        "status": "PASS_DECISION_LIFECYCLE",
        "as_of_date": "2026-10-15",
        "orders": 0,
        "trade_authority": "NONE",
        "input_identity": {
            "market_date": "2026-10-15",
            "surface_as_of_date": "2026-10-15",
        },
        "subjects": [
            {
                "security_id": "600900.SH",
                "latest_price": 29.60,
                "price_source": "A_SHARE_FULL_MARKET",
                "price_as_of": "2026-10-15",
            },
            {
                "security_id": "017534.OF",
                "latest_price": 1.3967,
                "price_source": "S3_PORTFOLIO_MARK",
                "price_as_of": None,
            },
        ],
    }
    return marks, lifecycle


def test_aligned_session_ready():
    marks, lifecycle = coherent_inputs()
    assert session_readiness(marks, lifecycle) == (True, [])


def test_lifecycle_prior_session_defers_before_virtual_book_build():
    marks, lifecycle = coherent_inputs()
    lifecycle["as_of_date"] = "2026-10-14"
    lifecycle["input_identity"]["market_date"] = "2026-10-14"
    lifecycle["input_identity"]["surface_as_of_date"] = "2026-10-14"
    lifecycle["subjects"][0]["price_as_of"] = "2026-10-14"
    ready, issues = session_readiness(marks, lifecycle)
    assert ready is False
    assert any("LIFECYCLE_AS_OF" in issue for issue in issues)
    assert any("LISTED_PRICE:600900.SH" in issue for issue in issues)


def test_surface_old_even_when_lifecycle_rebuilt_defers():
    marks, lifecycle = coherent_inputs()
    lifecycle["input_identity"]["surface_as_of_date"] = "2026-10-14"
    ready, issues = session_readiness(marks, lifecycle)
    assert ready is False
    assert any("LIFECYCLE_SURFACE_DATE" in issue for issue in issues)


def test_one_listed_price_old_defers_even_if_header_new():
    marks, lifecycle = coherent_inputs()
    lifecycle["subjects"][0]["price_as_of"] = "2026-10-14"
    ready, issues = session_readiness(marks, lifecycle)
    assert ready is False
    assert len(issues) == 1


def test_nonlisted_fund_mark_may_have_distinct_nav_session():
    marks, lifecycle = coherent_inputs()
    lifecycle["subjects"][1]["price_as_of"] = "2026-10-13"
    assert session_readiness(marks, lifecycle) == (True, [])


@pytest.mark.parametrize("field,value", [("status", "BLOCKED"), ("trade_authority", "LIVE"), ("orders", 1)])
def test_bad_authority_fails_closed(field, value):
    marks, lifecycle = coherent_inputs()
    bad = copy.deepcopy(marks)
    bad[field] = value
    with pytest.raises(ValueError, match="PHASE3_"):
        session_readiness(bad, lifecycle)


def test_missing_lifecycle_identity_defers_not_fake_success():
    marks, lifecycle = coherent_inputs()
    del lifecycle["input_identity"]
    ready, issues = session_readiness(marks, lifecycle)
    assert ready is False
    assert len(issues) == 2
