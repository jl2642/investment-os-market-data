import json
from pathlib import Path

import pandas as pd

from scripts.run_fmdl2d_stability import (
    concentration,
    fragility_review,
    rank_transition,
    semantic_frame_hash,
    sleeve_transition,
)

ROOT = Path(__file__).resolve().parents[1]
SCREEN_CONFIG = json.loads((ROOT / "config/fmdl2_screening_funnel.json").read_text())
STABILITY_CONFIG = json.loads((ROOT / "config/fmdl2d_replay_stability.json").read_text())


def sample_longlist(date: str, symbols: list[str]) -> pd.DataFrame:
    rows = []
    sleeves = [
        "DEFENSIVE_STABILITY",
        "TREND_PERSISTENCE",
        "LIQUID_BREAKOUT",
        "RECOVERY_WATCH",
    ]
    for rank, symbol in enumerate(symbols, start=1):
        rows.append(
            {
                "as_of_date": date,
                "overall_rank": rank,
                "research_priority": (
                    "A_IMMEDIATE_RESEARCH" if rank <= 2 else "B_WATCH_OR_TRIGGER"
                ),
                "symbol": symbol,
                "name": f"Name {symbol}",
                "board": "SH_MAIN" if rank % 2 else "SZ_MAIN",
                "primary_sleeve": sleeves[(rank - 1) % len(sleeves)],
                "sleeves": sleeves[(rank - 1) % len(sleeves)],
                "sleeve_count": 1,
                "factor_record_quality": "VALID",
                "event_flag_count": 0,
                "avg_turnover_cny_20d": 100_000_000,
                "max_drawdown_120d": -0.10,
                "return_20d": 0.05,
                "industry_name": "Industry A" if rank % 2 else "Industry B",
                "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
            }
        )
    return pd.DataFrame(rows)


def test_semantic_hash_ignores_row_order_and_excluded_hashes():
    left = pd.DataFrame(
        [
            {"symbol": "2", "value": 3.0, "row_hash": "a"},
            {"symbol": "1", "value": 2.0, "row_hash": "b"},
        ]
    )
    right = pd.DataFrame(
        [
            {"symbol": "1", "value": 2.0, "row_hash": "x"},
            {"symbol": "2", "value": 3.0, "row_hash": "y"},
        ]
    )
    assert semantic_frame_hash(left, sort_by=["symbol"], exclude={"row_hash"}) == semantic_frame_hash(
        right, sort_by=["symbol"], exclude={"row_hash"}
    )


def test_rank_transition_metrics_and_migrations():
    previous = sample_longlist("2026-07-16", ["A", "B", "C", "D"])
    current = sample_longlist("2026-07-17", ["B", "A", "C", "E"])
    summary, migrations = rank_transition(previous, current, "2026-07-16", "2026-07-17")
    assert summary["common_symbols"] == 3
    assert summary["overlap_ratio"] == 0.75
    assert summary["entrants"] == 1
    assert summary["exits"] == 1
    assert len(migrations) == 3


def test_sleeve_jaccard():
    previous = pd.DataFrame(
        [
            {"symbol": "A", "sleeve_id": "TREND_PERSISTENCE"},
            {"symbol": "B", "sleeve_id": "TREND_PERSISTENCE"},
        ]
    )
    current = pd.DataFrame(
        [
            {"symbol": "B", "sleeve_id": "TREND_PERSISTENCE"},
            {"symbol": "C", "sleeve_id": "TREND_PERSISTENCE"},
        ]
    )
    rows = sleeve_transition(
        previous,
        current,
        "2026-07-16",
        "2026-07-17",
        ["TREND_PERSISTENCE"],
    )
    assert rows[0]["jaccard"] == 1 / 3


def test_concentration_metrics():
    frame = sample_longlist("2026-07-17", ["A", "B", "C", "D"])
    metrics = concentration(frame)
    assert metrics["maximum_board_share"] == 0.5
    assert metrics["board_hhi"] == 0.5
    assert metrics["industry_identity_coverage"] == 1.0


def test_fragility_is_structural_risk_not_realized_false_positive():
    frame = sample_longlist("2026-07-17", ["A", "B", "C"])
    frame.loc[0, "overall_rank"] = 80
    frame.loc[0, "avg_turnover_cny_20d"] = 31_000_000
    review = fragility_review(frame, SCREEN_CONFIG, STABILITY_CONFIG)
    flagged = review.loc[review["symbol"] == "A"].iloc[0]
    assert flagged["structural_fragility_flag"]
    assert "BOTTOM_QUARTILE_RANK" in flagged["risk_flags"]
    assert "LIQUIDITY_NEAR_FLOOR" in flagged["risk_flags"]
