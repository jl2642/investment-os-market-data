#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

import build_core2_hardening as base


def parse_weight(value: Any, default: float) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric / 100.0 if numeric > 1.0 else numeric
    text = str(value).strip()
    if not text:
        return float(default)
    if text.endswith("%"):
        try:
            return float(text[:-1].strip()) / 100.0
        except ValueError:
            return float(default)
    try:
        numeric = float(text)
    except ValueError:
        return float(default)
    return numeric / 100.0 if numeric > 1.0 else numeric


def position_fit(
    sid: str,
    company_name: str,
    simulation: dict[str, Any],
    real: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    sim_holding = next((row for row in simulation.get("holdings", []) if row["security_id"] == sid), None)
    real_holding = next((row for row in real.get("holdings", []) if row["security_id"] == sid), None)
    total_assets = float(simulation["summary"]["account_total_assets"])
    default_target = float(policy["core_target_weight"])
    if sim_holding:
        current_value = float(sim_holding["market_value"])
        current_weight = current_value / total_assets
        raw_target_weight = sim_holding.get("target_weight")
        target_weight = parse_weight(raw_target_weight, default_target)
        target_value = total_assets * target_weight
        gap_value = target_value - current_value
        fit_status = (
            "ABOVE_HARD_MAX_RESEARCH_RED_FLAG"
            if current_weight > policy["single_name_hard_max_weight"]
            else "ABOVE_SOFT_MAX_REVIEW_REQUIRED"
            if current_weight > policy["soft_max_weight"]
            else "BELOW_TARGET_RESEARCH_ONLY"
            if current_weight < target_weight - 0.005
            else "AT_TARGET_BAND"
        )
    else:
        current_value = current_weight = 0.0
        raw_target_weight = None
        target_weight = default_target
        target_value = total_assets * target_weight
        gap_value = target_value
        fit_status = "NOT_HELD_RESEARCH_ONLY"
    return {
        "security_id": sid,
        "security_name": company_name,
        "simulation_position": sim_holding,
        "real_account_position": real_holding,
        "simulation_total_assets": round(total_assets, 6),
        "current_market_value": round(current_value, 6),
        "current_weight": round(current_weight, 8),
        "target_weight_raw": raw_target_weight,
        "target_weight_reference": target_weight,
        "target_weight_parse_policy": "PERCENT_STRING_OR_DECIMAL_WITH_POLICY_FALLBACK",
        "target_market_value_reference": round(target_value, 6),
        "market_value_gap_to_reference": round(gap_value, 6),
        "fit_status": fit_status,
        "portfolio_role": sim_holding.get("portfolio_bucket") if sim_holding else "CORE_RESEARCH_CANDIDATE",
        "broker_verified": False,
        "position_change_authorized": False,
        "order_authorized": False,
        "trade_authority": "NONE",
    }


base.position_fit = position_fit


if __name__ == "__main__":
    base.main()
