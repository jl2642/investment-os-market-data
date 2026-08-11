from __future__ import annotations

import pytest

from automation.wp2_r.validate_portfolio_current_contract import (
    expected_economic_states,
    validate_expected_economic_state,
)


def _real_source():
    return {
        "holdings": [
            {
                "code": "110017",
                "holding_name": "易方达增强回报债券A",
                "asset_class": "BOND_FUND",
                "quantity_or_shares": 71422.49,
                "cost_price_or_cost": 100000.0,
            },
            {
                "code": "605090",
                "holding_name": "九丰能源",
                "asset_class": "A_SHARE_STOCK",
                "quantity_or_shares": 9900,
                "cost_price_or_cost": 33.055,
            },
        ],
        "as_of": "2026-08-06T11:02:00+08:00",
    }


def _sim_source():
    return {"holdings": [], "as_of": "2026-08-06T11:03:00+08:00"}


def _ledger(entries):
    return {
        "trade_authority": "NONE",
        "entries": entries,
        "continuity_confirmed_through": "2026-08-11T09:27:00+08:00",
    }


def test_confirmed_full_sale_authorizes_security_removal() -> None:
    ledger = _ledger([
        {
            "delta_id": "REAL_20260806_SELL_110017_ALL",
            "account": "REAL",
            "action": "SELL",
            "asset_class": "BOND_FUND",
            "security_id": "110017.OF",
            "security_name": "易方达增强回报债券A",
            "quantity_delta": -71422.49,
            "unit_price": 1.407,
            "fees": 100.49,
            "status": "CONFIRMED_BY_USER",
            "confirmation_authority": "USER",
        }
    ])
    expected_real, applied, _, _ = expected_economic_states(_real_source(), _sim_source(), ledger)
    assert applied == ["REAL_20260806_SELL_110017_ALL"]
    assert [row["security_id"] for row in expected_real] == ["605090.SH"]

    current = {"holdings": expected_real}
    validate_expected_economic_state(label="REAL", expected_rows=expected_real, current_payload=current)


def test_security_removal_without_confirmed_delta_still_fails() -> None:
    expected_real, applied, _, _ = expected_economic_states(_real_source(), _sim_source(), _ledger([]))
    assert applied == []
    current = {"holdings": [row for row in expected_real if row["security_id"] != "110017.OF"]}
    with pytest.raises(AssertionError, match="REAL_SECURITY_SET_MISMATCH_AFTER_AUTHORIZED_DELTAS"):
        validate_expected_economic_state(label="REAL", expected_rows=expected_real, current_payload=current)
