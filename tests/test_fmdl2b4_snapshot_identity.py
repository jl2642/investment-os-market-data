import pandas as pd

from scripts.run_incremental_history_refresh_v2 import canonical_incremental_row


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
    config = {
        "daily_fast_path": {
            "snapshot_adjustment_mode": "qfq_current_session_equivalent",
            "snapshot_record_quality": "VALIDATED_INCREMENTAL",
        }
    }
    output = canonical_incremental_row(row, "2026-07-17T18:00:00+08:00", config)
    assert output["symbol"] == "600000.SH"
    assert output["trade_date"] == "2026-07-17"
    assert output["row_hash"]
