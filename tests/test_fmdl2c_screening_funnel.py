import json
from pathlib import Path

import pandas as pd

from scripts.run_screening_funnel import build_longlist, classify_investability, evaluate_sleeve

CONFIG = json.loads(
    (Path(__file__).resolve().parents[1] / "config/fmdl2_screening_funnel.json").read_text()
)


def base_row():
    row = {
        "as_of_date": "2026-07-17",
        "symbol": "600000.SH",
        "board": "SH_MAIN",
        "is_st": False,
        "is_suspended": False,
        "factor_record_quality": "VALID",
        "confidence_grade": "A",
        "event_flag_count": 0,
        "history_coverage_ratio_250": 1.0,
        "avg_turnover_cny_20d": 100_000_000,
        "active_trade_ratio_60d": 1.0,
        "suspension_days_20": 0,
        "zero_turnover_days_20": 0,
    }
    factors = set()
    for sleeve in CONFIG["sleeves"].values():
        factors.update(sleeve.get("weights", {}))
        factors.update(sleeve.get("minimum_percentiles", {}))
        factors.update(sleeve.get("maximum_any_percentiles", {}))
        factors.update(sleeve.get("raw_conditions", {}))
    for factor in factors:
        row[factor] = 1.2 if factor == "volume_ratio_20_60d" else 0.1
        row[factor + "__board_pct"] = 0.8
    row["return_250d__board_pct"] = 0.3
    row["momentum_250_20d__board_pct"] = 0.3
    row["avg_turnover_cny_20d"] = 100_000_000
    row["active_trade_ratio_60d"] = 1.0
    row["suspension_days_20"] = 0
    row["zero_turnover_days_20"] = 0
    return row


def test_core_investability():
    status, reasons = classify_investability(pd.Series(base_row()), CONFIG)
    assert status == "ELIGIBLE_CORE"
    assert reasons == []


def test_blocked_is_excluded():
    row = base_row()
    row["factor_record_quality"] = "BLOCKED"
    status, _ = classify_investability(pd.Series(row), CONFIG)
    assert status == "EXCLUDED"


def test_st_is_review_only():
    row = base_row()
    row["is_st"] = True
    status, _ = classify_investability(pd.Series(row), CONFIG)
    assert status == "REVIEW_ONLY"


def test_missing_component_never_neutralized():
    row = base_row()
    row["return_120d__board_pct"] = None
    row["investability_status"] = "ELIGIBLE_CORE"
    row["investability_reason_codes"] = "NONE"
    row["screen_row_hash"] = "x"
    result = evaluate_sleeve(
        pd.DataFrame([row]),
        "TREND_PERSISTENCE",
        CONFIG["sleeves"]["TREND_PERSISTENCE"],
        CONFIG,
    )
    assert result.empty


def test_longlist_cross_sleeve_bonus_and_rank():
    screen = pd.DataFrame(
        [
            {
                **base_row(),
                "investability_status": "ELIGIBLE_CORE",
                "investability_reason_codes": "NONE",
                "screen_row_hash": "abc",
            }
        ]
    )
    detail = pd.DataFrame(
        [
            {
                "as_of_date": "2026-07-17",
                "symbol": "600000.SH",
                "board": "SH_MAIN",
                "sleeve_id": "A",
                "sleeve_score": 0.8,
                "investability_status": "ELIGIBLE_CORE",
                "factor_record_quality": "VALID",
                "confidence_grade": "A",
                "event_flag_count": 0,
                "avg_turnover_cny_20d": 100_000_000,
            },
            {
                "as_of_date": "2026-07-17",
                "symbol": "600000.SH",
                "board": "SH_MAIN",
                "sleeve_id": "B",
                "sleeve_score": 0.75,
                "investability_status": "ELIGIBLE_CORE",
                "factor_record_quality": "VALID",
                "confidence_grade": "A",
                "event_flag_count": 0,
                "avg_turnover_cny_20d": 100_000_000,
            },
        ]
    )
    result = build_longlist(detail, screen, CONFIG)
    assert len(result) == 1
    assert result.iloc[0]["aggregate_score"] == 0.82
    assert result.iloc[0]["overall_rank"] == 1
