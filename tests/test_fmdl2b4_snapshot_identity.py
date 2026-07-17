import pandas as pd

from scripts.run_incremental_history_refresh_v2 import (
    canonical_incremental_row,
    continuity_passes,
    snapshot_ohlc_is_valid,
)


def config() -> dict:
    return {
        "daily_fast_path": {
            "snapshot_adjustment_mode": "qfq_current_session_equivalent",
            "snapshot_record_quality": "VALIDATED_INCREMENTAL",
            "continuity_relative_tolerance": 0.003,
            "continuity_absolute_cny_tolerance": 0.02,
        }
    }


def test_indexed_snapshot_row_preserves_symbol_identity() -> None:
    row = pd.Series(
        {
            "as_of_date": "2026-07-17",
            "open": 10.0,
            "high": 10.2,
            "low": 9.9,
            "close": 10.1,
            "volume_shares": 1000.0,
            "turnover_cny": 10100.0,
        },
        name="600000.SH",
    )
    output = canonical_incremental_row(row, "2026-07-17T18:00:00+08:00", config())
    assert output["symbol"] == "600000.SH"
    assert output["trade_date"] == "2026-07-17"
    assert output["row_hash"]


def test_impossible_snapshot_ohlc_is_rejected_before_fast_append() -> None:
    row = pd.Series({
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "close": 10.1,
        "pct_change": 1.0,
        "prev_close": 10.0,
    })
    assert snapshot_ohlc_is_valid(row) is False
    passed, expected, difference = continuity_passes(row, 10.0, config())
    assert passed is False
    assert expected is None
    assert difference is None


def test_valid_snapshot_still_uses_qfq_continuity_gate() -> None:
    row = pd.Series({
        "open": 10.0,
        "high": 10.2,
        "low": 9.9,
        "close": 10.1,
        "pct_change": 1.0,
        "prev_close": 10.0,
    })
    assert snapshot_ohlc_is_valid(row) is True
    passed, expected, difference = continuity_passes(row, 10.0, config())
    assert passed is True
    assert expected == 10.0
    assert difference == 0.0
