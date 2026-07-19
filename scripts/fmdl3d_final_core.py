from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def build_unified_current(
    capitalization: pd.DataFrame,
    valuation: pd.DataFrame,
    shareholder_return: pd.DataFrame,
    component_release_ids: dict[str, str],
) -> pd.DataFrame:
    cap = capitalization.copy()
    val = valuation.copy()
    shr = shareholder_return.copy()
    for frame in [cap, val, shr]:
        frame["symbol"] = frame["symbol"].astype(str)
    cap_fields = [
        "symbol", "name", "exchange", "board", "price_as_of_date", "close",
        "total_shares", "float_a_shares", "total_market_cap_cny",
        "float_market_cap_cny", "capitalization_state", "lineage_id",
    ]
    val_fields = [
        "symbol", "sector_profile", "market_as_of_date", "pe_ttm",
        "pe_ttm_state", "earnings_yield_ttm", "earnings_yield_ttm_state",
        "pb", "pb_state", "ps_ttm", "ps_ttm_state", "fcf_yield_ttm",
        "fcf_yield_ttm_state", "ev_sales_ttm", "ev_sales_ttm_state",
        "ev_operating_income_ttm", "ev_operating_income_ttm_state",
        "valid_metric_count", "decision_grade_metric_count", "row_hash",
    ]
    shr_fields = [
        "symbol", "market_as_of_date",
        "implemented_cash_dividend_per_share_ttm",
        "implemented_cash_dividend_total_cny_ttm", "dividend_yield_ttm",
        "completed_buyback_yield_ttm",
        "completed_issuance_dilution_yield_ttm", "shareholder_yield_ttm",
        "shareholder_return_state", "complete_shareholder_yield",
        "lineage_ids_json",
    ]
    missing = {
        "capitalization": sorted(set(cap_fields) - set(cap.columns)),
        "valuation": sorted(set(val_fields) - set(val.columns)),
        "shareholder_return": sorted(set(shr_fields) - set(shr.columns)),
    }
    if any(missing.values()):
        raise ValueError(f"unified Current source columns missing: {missing}")
    cap = cap[cap_fields].rename(
        columns={
            "price_as_of_date": "market_as_of_date",
            "lineage_id": "capitalization_lineage_id",
        }
    )
    val = val[val_fields].rename(
        columns={
            "market_as_of_date": "valuation_market_as_of_date",
            "valid_metric_count": "valuation_valid_metric_count",
            "decision_grade_metric_count": "valuation_decision_grade_metric_count",
            "row_hash": "valuation_row_hash",
        }
    )
    shr = shr[shr_fields].rename(
        columns={
            "market_as_of_date": "shareholder_market_as_of_date",
            "lineage_ids_json": "shareholder_event_lineage_ids_json",
        }
    )
    out = cap.merge(val, on="symbol", how="inner", validate="one_to_one")
    out = out.merge(shr, on="symbol", how="inner", validate="one_to_one")
    out["component_release_ids_json"] = json_text(component_release_ids)
    out["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    out["trade_authority"] = "NONE"
    published_without_hash = [
        "symbol", "name", "exchange", "board", "sector_profile",
        "market_as_of_date", "close", "total_shares", "float_a_shares",
        "total_market_cap_cny", "float_market_cap_cny", "capitalization_state",
        "pe_ttm", "pe_ttm_state", "earnings_yield_ttm",
        "earnings_yield_ttm_state", "pb", "pb_state", "ps_ttm",
        "ps_ttm_state", "fcf_yield_ttm", "fcf_yield_ttm_state",
        "ev_sales_ttm", "ev_sales_ttm_state", "ev_operating_income_ttm",
        "ev_operating_income_ttm_state", "valuation_valid_metric_count",
        "valuation_decision_grade_metric_count",
        "implemented_cash_dividend_per_share_ttm",
        "implemented_cash_dividend_total_cny_ttm", "dividend_yield_ttm",
        "completed_buyback_yield_ttm",
        "completed_issuance_dilution_yield_ttm", "shareholder_yield_ttm",
        "shareholder_return_state", "complete_shareholder_yield",
        "capitalization_lineage_id", "valuation_row_hash",
        "shareholder_event_lineage_ids_json", "component_release_ids_json",
        "authority", "trade_authority",
    ]
    out = out[published_without_hash].copy()
    out["row_hash"] = [
        stable_hash(row) for row in out.to_dict(orient="records")
    ]
    ordered = published_without_hash[:-2] + [
        "row_hash", "authority", "trade_authority"
    ]
    return out[ordered].sort_values("symbol").reset_index(drop=True)


def market_cap_replay_error_count(
    capitalization: pd.DataFrame, tolerance: float
) -> tuple[int, float]:
    valid = capitalization[
        capitalization["capitalization_state"].isin(["VALID", "VALID_WITH_WARNING"])
    ].copy()
    total_replay = pd.to_numeric(valid["close"], errors="coerce") * pd.to_numeric(
        valid["total_shares"], errors="coerce"
    )
    float_replay = pd.to_numeric(valid["close"], errors="coerce") * pd.to_numeric(
        valid["float_a_shares"], errors="coerce"
    )
    total_diff = (
        total_replay - pd.to_numeric(valid["total_market_cap_cny"], errors="coerce")
    ).abs()
    float_diff = (
        float_replay - pd.to_numeric(valid["float_market_cap_cny"], errors="coerce")
    ).abs()
    errors = int((total_diff > tolerance).sum() + (float_diff > tolerance).sum())
    maximum = float(
        max(
            total_diff.max() if len(total_diff) else 0.0,
            float_diff.max() if len(float_diff) else 0.0,
        )
    )
    return errors, maximum


def shareholder_yield_replay_error_count(
    current: pd.DataFrame, tolerance: float
) -> tuple[int, float]:
    complete = current[current["complete_shareholder_yield"]].copy()
    replay = (
        pd.to_numeric(complete["dividend_yield_ttm"], errors="coerce")
        + pd.to_numeric(complete["completed_buyback_yield_ttm"], errors="coerce")
        - pd.to_numeric(
            complete["completed_issuance_dilution_yield_ttm"], errors="coerce"
        )
    )
    diff = (
        replay
        - pd.to_numeric(complete["shareholder_yield_ttm"], errors="coerce")
    ).abs()
    return int((diff > tolerance).sum()), float(diff.max() if len(diff) else 0.0)


def cross_layer_numeric_mismatch_count(
    capitalization: pd.DataFrame,
    valuation: pd.DataFrame,
    shareholder_return: pd.DataFrame,
    tolerance: float,
) -> dict[str, int]:
    cap = capitalization.set_index("symbol")
    val = valuation.set_index("symbol")
    shr = shareholder_return.set_index("symbol")
    common = cap.index.intersection(val.index).intersection(shr.index)
    cap_total = pd.to_numeric(cap.loc[common, "total_market_cap_cny"], errors="coerce")
    val_total = pd.to_numeric(val.loc[common, "total_market_cap_cny"], errors="coerce")
    shr_total = pd.to_numeric(shr.loc[common, "total_market_cap_cny"], errors="coerce")
    cap_float = pd.to_numeric(cap.loc[common, "float_market_cap_cny"], errors="coerce")
    val_float = pd.to_numeric(val.loc[common, "float_market_cap_cny"], errors="coerce")

    def mismatch(left: pd.Series, right: pd.Series) -> int:
        both_null = left.isna() & right.isna()
        one_null = left.isna() ^ right.isna()
        numeric = (~left.isna()) & (~right.isna()) & (
            (left - right).abs() > tolerance
        )
        return int((~both_null & (one_null | numeric)).sum())

    return {
        "capitalization_vs_valuation_total_market_cap": mismatch(cap_total, val_total),
        "capitalization_vs_shareholder_total_market_cap": mismatch(cap_total, shr_total),
        "capitalization_vs_valuation_float_market_cap": mismatch(cap_float, val_float),
    }


def replay_row_hashes(frame: pd.DataFrame) -> int:
    errors = 0
    for row in frame.to_dict(orient="records"):
        expected = row.get("row_hash")
        payload = {key: value for key, value in row.items() if key != "row_hash"}
        if stable_hash(payload) != expected:
            errors += 1
    return errors
