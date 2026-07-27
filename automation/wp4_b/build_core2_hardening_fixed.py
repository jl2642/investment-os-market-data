#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import build_core2_hardening as base


FACTOR_ALIASES = {
    "GROWTH_REVENUE_YOY": "FIN_REVENUE_YOY",
    "GROWTH_NET_PROFIT_YOY": "FIN_PARENT_NI_YOY",
    "PROFIT_ROE": "FIN_ROE_AVG_PARENT_EQUITY_TTM",
    "PROFIT_ROA": "FIN_ROA_AVG_ASSETS_TTM",
    "CASH_OCF_TO_NET_PROFIT": "FIN_CFO_TO_PARENT_NI_TTM",
    "BALANCE_DEBT_TO_ASSETS": "FIN_LIABILITIES_TO_ASSETS",
}


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(payload: Any) -> str:
    raw = json.dumps(
        json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def factor_pivot(
    path: Path,
    factor_ids: list[str],
    security_ids: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(path)
    required = {"symbol", "factor_id", "factor_value", "period_end", "as_of_timestamp", "quality_state", "rank_eligibility"}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ValueError(
            "WP4B_FACTOR_SCHEMA_MISSING_COLUMNS:"
            + ",".join(missing_columns)
            + ":available="
            + ",".join(map(str, frame.columns))
        )
    requested = [FACTOR_ALIASES.get(factor_id, factor_id) for factor_id in factor_ids]
    frame = frame.copy()
    frame["security_id"] = frame["symbol"].map(base.security_id)
    selected = frame[
        frame["security_id"].isin(security_ids)
        & frame["factor_id"].isin(requested)
        & frame["quality_state"].isin(["VALID", "VALID_WITH_WARNING"])
        & frame["rank_eligibility"].isin(["ELIGIBLE", "CONDITIONAL"])
    ].copy()
    selected["factor_value"] = pd.to_numeric(selected["factor_value"], errors="coerce")
    selected = selected[selected["factor_value"].notna()].copy()
    if selected.empty:
        raise ValueError(
            "WP4B_NO_VALID_CANONICAL_FACTOR_ROWS:requested=" + ",".join(requested)
        )
    selected["_as_of_sort"] = pd.to_datetime(selected["as_of_timestamp"], errors="coerce", utc=True)
    selected["_period_sort"] = pd.to_datetime(selected["period_end"], errors="coerce")
    selected = selected.sort_values(
        ["security_id", "factor_id", "_as_of_sort", "_period_sort"],
        ascending=[True, True, False, False],
        na_position="last",
    ).drop_duplicates(["security_id", "factor_id"], keep="first")
    pivot = selected.pivot_table(
        index="security_id",
        columns="factor_id",
        values="factor_value",
        aggfunc="first",
    ).reset_index()
    periods: dict[str, Any] = {}
    for sid, group in selected.groupby("security_id"):
        periods[sid] = {
            str(row["factor_id"]): {
                "period_end": None if pd.isna(row["period_end"]) else str(row["period_end"]),
                "as_of_timestamp": None if pd.isna(row["as_of_timestamp"]) else str(row["as_of_timestamp"]),
                "quality_state": str(row["quality_state"]),
                "rank_eligibility": str(row["rank_eligibility"]),
            }
            for _, row in group.iterrows()
        }
    return pivot, periods


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


base.factor_pivot = factor_pivot
base.position_fit = position_fit
base.write_json = write_json
base.digest = digest


if __name__ == "__main__":
    base.main()
