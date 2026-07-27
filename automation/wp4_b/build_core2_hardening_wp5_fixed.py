#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

import build_core2_hardening as base
import build_core2_hardening_fixed as _prior_fixes  # noqa: F401 - applies factor, weight and JSON patches


PROVIDER_MARKET_CAP_UNIT = "CNY_10K"
PROVIDER_MARKET_CAP_TO_RMB = 10_000.0


def scenario_model(company: dict[str, Any], market_row: dict[str, Any]) -> dict[str, Any]:
    """Build a one-year earnings/PE scenario using the provider's 10k-RMB cap unit.

    Eastmoney-style A-share total_market_cap is carried in CNY 10,000 units in the
    accepted market file. The earlier WP4-B implementation treated it as RMB,
    understating market cap and share count by 10,000x and overstating implied
    prices by the same factor. This adapter repairs only that unit conversion.
    """
    assumptions = company["scenario_assumptions"]
    current_price = float(market_row["last_price"])
    provider_market_cap = float(market_row["total_market_cap"])
    current_market_cap_rmb = provider_market_cap * PROVIDER_MARKET_CAP_TO_RMB
    shares = current_market_cap_rmb / current_price

    current_market_cap_rmb_bn = current_market_cap_rmb / 1e9
    implied_share_count_bn = shares / 1e9
    if not (10.0 <= current_market_cap_rmb_bn <= 5_000.0):
        raise ValueError(f"WP4B_MARKET_CAP_SCALE_INVALID:{current_market_cap_rmb_bn}")
    if not (0.1 <= implied_share_count_bn <= 100.0):
        raise ValueError(f"WP4B_SHARE_COUNT_SCALE_INVALID:{implied_share_count_bn}")

    cases = []
    for name, case in assumptions["scenarios"].items():
        revenue = assumptions["base_revenue_rmb_bn"] * (1.0 + float(case["revenue_growth"]))
        net_income = revenue * float(case["net_margin"])
        implied_market_cap = net_income * float(case["exit_pe"])
        implied_price = implied_market_cap * 1e9 / shares
        price_return = implied_price / current_price - 1.0
        if not (0.1 * current_price <= implied_price <= 10.0 * current_price):
            raise ValueError(f"WP4B_IMPLIED_PRICE_SCALE_INVALID:{name}:{implied_price}")
        cases.append({
            "scenario": name,
            "revenue_growth": case["revenue_growth"],
            "net_margin": case["net_margin"],
            "exit_pe": case["exit_pe"],
            "forward_revenue_rmb_bn": round(revenue, 6),
            "forward_net_income_rmb_bn": round(net_income, 6),
            "implied_market_cap_rmb_bn": round(implied_market_cap, 6),
            "implied_price": round(implied_price, 6),
            "price_return_vs_current": round(price_return, 8),
        })

    return {
        "model_type": assumptions["model_type"],
        "current_price": current_price,
        "provider_market_cap_raw": provider_market_cap,
        "provider_market_cap_unit": PROVIDER_MARKET_CAP_UNIT,
        "provider_market_cap_to_rmb_multiplier": PROVIDER_MARKET_CAP_TO_RMB,
        "current_market_cap_rmb_bn": round(current_market_cap_rmb_bn, 6),
        "implied_share_count_bn": round(implied_share_count_bn, 6),
        "base_year": assumptions["base_year"],
        "base_revenue_rmb_bn": assumptions["base_revenue_rmb_bn"],
        "critical_drivers": assumptions["critical_drivers"],
        "cases": cases,
        "model_limitations": [
            "One-year earnings and exit-multiple model is a decision interface, not a full statutory forecast",
            "Provider total_market_cap is explicitly converted from CNY 10,000 units to RMB",
            "No automatic target price or trading action is authorized",
            "Scenario assumptions require refresh after material earnings, guidance, regulation or capital-allocation events",
        ],
    }


base.scenario_model = scenario_model


if __name__ == "__main__":
    base.main()
