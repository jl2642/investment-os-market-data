import json
import math
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_basic_factor_engine import (
    EXPECTED_FACTOR_IDS,
    add_cross_sectional_fields,
    compute_symbol_factor_values,
)

ROOT = Path(__file__).resolve().parents[1]


def registry() -> dict:
    return json.loads((ROOT / "config/fmdl2_factor_registry.json").read_text(encoding="utf-8"))


def engine_config() -> dict:
    return json.loads((ROOT / "config/fmdl2_factor_engine.json").read_text(encoding="utf-8"))


def synthetic_history(periods: int = 301, daily_return: float = 0.01) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-07-16", periods=periods)
    closes = [100.0 * ((1.0 + daily_return) ** index) for index in range(periods)]
    return pd.DataFrame({
        "trade_date": dates,
        "symbol": "600000.SH",
        "open": closes,
        "high": [value * 1.01 for value in closes],
        "low": [value * 0.99 for value in closes],
        "close": closes,
        "volume_shares": 100_000.0,
        "turnover_cny": 1_000_000.0,
        "provider_id": "sina_daily",
        "source_function": "stock_zh_a_daily",
        "adjustment_mode": "qfq",
        "retrieved_at": "2026-07-17T12:00:00+08:00",
        "record_quality": "VALID",
        "row_hash": "test",
    })


def universe_row() -> dict:
    return {
        "symbol": "600000.SH",
        "board": "SH_MAIN",
        "list_date": "2000-01-01",
        "is_st": False,
        "is_suspended": False,
    }


def status_row() -> dict:
    return {"symbol": "600000.SH", "state": "READY", "provider_id": "sina_daily"}


def detail_map(details: list[dict]) -> dict[str, dict]:
    return {row["factor_id"]: row for row in details}


def test_registry_matches_exact_implemented_factor_set_and_has_no_trade_authority() -> None:
    contract = registry()
    assert {item["factor_id"] for item in contract["factors"]} == EXPECTED_FACTOR_IDS
    assert contract["authority_boundary"] == "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY"
    assert "AUTOMATIC_PORTFOLIO_CHANGE" in contract["prohibited_actions"]
    assert "pe" in contract["deferred_to_fmdl3"]


def test_core_formulas_use_adjusted_close_and_preserve_missing_downside_volatility() -> None:
    history = synthetic_history()
    calendar = pd.DatetimeIndex(history["trade_date"])
    base, details = compute_symbol_factor_values(
        history,
        universe_row(),
        status_row(),
        registry(),
        engine_config(),
        calendar,
        "2026-07-16",
        0,
    )
    factors = detail_map(details)
    assert factors["return_20d"]["factor_value"] == pytest.approx((1.01**20) - 1.0)
    assert factors["return_250d"]["factor_value"] == pytest.approx((1.01**250) - 1.0)
    assert factors["momentum_250_20d"]["factor_value"] == pytest.approx((1.01**230) - 1.0)
    assert factors["distance_52w_high"]["factor_value"] == pytest.approx(0.0)
    assert factors["trend_consistency_60d"]["factor_value"] == pytest.approx(1.0)
    assert factors["positive_month_ratio_12m"]["factor_value"] == pytest.approx(1.0)
    assert factors["max_drawdown_250d"]["factor_value"] == pytest.approx(0.0)
    assert factors["avg_turnover_cny_60d"]["factor_value"] == pytest.approx(1_000_000.0)
    assert factors["turnover_stability_60d"]["factor_value"] == pytest.approx(1.0)
    assert factors["turnover_cv_60d"]["factor_value"] == pytest.approx(0.0)
    assert factors["volume_ratio_20_60d"]["factor_value"] == pytest.approx(1.0)
    assert factors["active_trade_ratio_60d"]["factor_value"] == pytest.approx(1.0)
    assert factors["suspension_days_60"]["factor_value"] == 0
    assert factors["zero_turnover_days_60"]["factor_value"] == 0
    assert factors["downside_volatility_60d"]["factor_value"] is None
    assert factors["downside_volatility_60d"]["missing_reason_code"] == "INSUFFICIENT_NEGATIVE_RETURNS"
    assert base["factor_record_quality"] == "PARTIAL"
    assert base["available_factor_count"] == 25


def test_future_rows_are_sliced_before_every_factor_calculation() -> None:
    history = synthetic_history()
    calendar = pd.DatetimeIndex(history["trade_date"])
    _, original_details = compute_symbol_factor_values(
        history,
        universe_row(),
        status_row(),
        registry(),
        engine_config(),
        calendar,
        "2026-07-16",
        0,
    )
    future = history.iloc[[-1]].copy()
    future["trade_date"] = pd.Timestamp("2026-07-17")
    future[["open", "high", "low", "close"]] = 1_000_000.0
    with_future = pd.concat([history, future], ignore_index=True)
    _, future_details = compute_symbol_factor_values(
        with_future,
        universe_row(),
        status_row(),
        registry(),
        engine_config(),
        calendar,
        "2026-07-16",
        0,
    )
    original = detail_map(original_details)
    sliced = detail_map(future_details)
    for factor_id in EXPECTED_FACTOR_IDS:
        left = original[factor_id]["factor_value"]
        right = sliced[factor_id]["factor_value"]
        if left is None:
            assert right is None
        else:
            assert right == pytest.approx(left)


def test_quarantined_symbol_keeps_one_blocked_record_and_26_explicit_missing_factors() -> None:
    base, details = compute_symbol_factor_values(
        None,
        universe_row(),
        {"symbol": "600000.SH", "state": "QUARANTINED", "provider_id": "NONE"},
        registry(),
        engine_config(),
        pd.bdate_range(end="2026-07-16", periods=300),
        "2026-07-16",
        2,
    )
    assert base["factor_record_quality"] == "BLOCKED"
    assert base["available_factor_count"] == 0
    assert base["missing_factor_count"] == 26
    assert len(details) == 26
    assert {item["factor_id"] for item in details} == EXPECTED_FACTOR_IDS
    assert all(item["availability_flag"] is False for item in details)
    assert all(item["missing_reason_code"] == "HISTORY_QUARANTINED" for item in details)


def test_cross_sectional_percentiles_are_direction_aware_and_missing_stays_missing() -> None:
    detail = pd.DataFrame([
        {"symbol": "A", "board": "SH_MAIN", "factor_id": "return_20d", "direction": "HIGHER_BETTER", "factor_value": 1.0, "availability_flag": True},
        {"symbol": "B", "board": "SH_MAIN", "factor_id": "return_20d", "direction": "HIGHER_BETTER", "factor_value": 2.0, "availability_flag": True},
        {"symbol": "C", "board": "SZ_MAIN", "factor_id": "return_20d", "direction": "HIGHER_BETTER", "factor_value": 3.0, "availability_flag": True},
        {"symbol": "D", "board": "SZ_MAIN", "factor_id": "return_20d", "direction": "HIGHER_BETTER", "factor_value": math.nan, "availability_flag": False},
        {"symbol": "A", "board": "SH_MAIN", "factor_id": "volatility_20d", "direction": "LOWER_BETTER", "factor_value": 1.0, "availability_flag": True},
        {"symbol": "B", "board": "SH_MAIN", "factor_id": "volatility_20d", "direction": "LOWER_BETTER", "factor_value": 2.0, "availability_flag": True},
        {"symbol": "C", "board": "SZ_MAIN", "factor_id": "volatility_20d", "direction": "LOWER_BETTER", "factor_value": 3.0, "availability_flag": True},
    ])
    output = add_cross_sectional_fields(detail, engine_config())
    momentum = output.loc[output["factor_id"] == "return_20d"].set_index("symbol")
    risk = output.loc[output["factor_id"] == "volatility_20d"].set_index("symbol")
    assert momentum.loc["A", "broad_market_percentile"] == pytest.approx(1 / 3)
    assert momentum.loc["C", "broad_market_percentile"] == pytest.approx(1.0)
    assert pd.isna(momentum.loc["D", "broad_market_percentile"])
    assert risk.loc["A", "broad_market_percentile"] == pytest.approx(1.0)
    assert risk.loc["C", "broad_market_percentile"] == pytest.approx(1 / 3)
