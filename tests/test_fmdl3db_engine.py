from __future__ import annotations

import pandas as pd

from scripts.fmdl3db_core import (
    ROOT,
    build_symbol_result,
    load_json,
    normalize_share_history,
    shard_for_symbol,
)

CONFIG = load_json(ROOT / "config/fmdl3db_engine.json")


def security(symbol: str = "600000.SH", board: str = "SH_MAIN") -> dict:
    return {
        "as_of_date": "2026-07-17",
        "symbol": symbol,
        "name": "测试公司",
        "exchange": symbol.split(".")[-1],
        "board": board,
        "row_hash": "a" * 64,
    }


def snapshot(symbol: str = "600000.SH", status: str = "TRADED") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "as_of_date": "2026-07-17",
                "symbol": symbol,
                "close": 10.0,
                "data_status": status,
                "source_timestamp": "2026-07-17T17:40:15+08:00",
                "record_quality": "VALID",
                "row_hash": "b" * 64,
            }
        ]
    )


def share_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "变更日期": "2025-01-01",
                "总股本": 100.0,
                "已上市流通A股": 70.0,
                "限售A股": 30.0,
                "变更原因": "历史股本",
            },
            {
                "变更日期": "2026-06-30",
                "总股本": 120.0,
                "已上市流通A股": 90.0,
                "限售A股": 30.0,
                "变更原因": "已实施增发",
            },
            {
                "变更日期": "2026-08-01",
                "总股本": 130.0,
                "已上市流通A股": 100.0,
                "限售A股": 30.0,
                "变更原因": "未来生效",
            },
        ]
    )


def test_sharding_is_deterministic_and_bounded():
    symbols = ["600000.SH", "000001.SZ", "430047.BJ"]
    first = [shard_for_symbol(symbol, 16) for symbol in symbols]
    second = [shard_for_symbol(symbol, 16) for symbol in symbols]
    assert first == second
    assert all(0 <= value < 16 for value in first)


def test_normalization_selects_latest_pit_row_and_preserves_future():
    ledger, invalid_count, error = normalize_share_history(
        share_frame(),
        security(),
        "2026-07-17",
        CONFIG,
        "2026-07-19T10:00:00+08:00",
    )
    assert error is None
    assert invalid_count == 0
    assert len(ledger) == 3
    selected = [row for row in ledger if row["selected_for_current"]]
    assert len(selected) == 1
    assert selected[0]["source_effective_date"] == "2026-06-30"
    assert selected[0]["total_shares"] == 120.0
    future = [row for row in ledger if row["eligibility_state"] == "FUTURE_EFFECTIVE"]
    assert len(future) == 1
    assert not future[0]["selected_for_current"]


def test_capitalization_is_recomputed_from_price_and_effective_shares():
    current, ledger, retry = build_symbol_result(
        security(),
        snapshot(),
        CONFIG,
        "FMDL1_TEST",
        "UNIVERSE_TEST",
        "SNAPSHOT_TEST",
        provider=lambda symbol: share_frame(),
    )
    assert current["capitalization_state"] == "VALID"
    assert current["share_effective_date"] == "2026-06-30"
    assert current["total_market_cap_cny"] == 1200.0
    assert current["float_market_cap_cny"] == 900.0
    assert current["share_source_row_hash"] in {
        row["source_row_hash"] for row in ledger if row["selected_for_current"]
    }
    assert retry["attempt_count"] == 1


def test_suspended_security_uses_accepted_last_close_with_warning():
    current, _, _ = build_symbol_result(
        security(),
        snapshot(status="SUSPENDED"),
        CONFIG,
        "FMDL1_TEST",
        "UNIVERSE_TEST",
        "SNAPSHOT_TEST",
        provider=lambda symbol: share_frame(),
    )
    assert current["capitalization_state"] == "VALID_WITH_WARNING"
    assert current["state_reason"] == "SUSPENDED_SECURITY_USING_ACCEPTED_LAST_CLOSE"
    assert current["total_market_cap_cny"] == 1200.0


def test_future_only_share_history_is_never_selected():
    future = pd.DataFrame(
        [
            {
                "变更日期": "2026-08-01",
                "总股本": 130.0,
                "已上市流通A股": 100.0,
            }
        ]
    )
    current, ledger, _ = build_symbol_result(
        security(),
        snapshot(),
        CONFIG,
        "FMDL1_TEST",
        "UNIVERSE_TEST",
        "SNAPSHOT_TEST",
        provider=lambda symbol: future,
    )
    assert current["capitalization_state"] == "FUTURE_ONLY_SHARE_ROWS"
    assert current["total_market_cap_cny"] is None
    assert len(ledger) == 1
    assert ledger[0]["eligibility_state"] == "FUTURE_EFFECTIVE"
    assert not ledger[0]["selected_for_current"]


def test_empty_source_is_explicit_quarantine_not_zero_fill():
    current, ledger, retry = build_symbol_result(
        security(),
        snapshot(),
        CONFIG,
        "FMDL1_TEST",
        "UNIVERSE_TEST",
        "SNAPSHOT_TEST",
        provider=lambda symbol: pd.DataFrame(),
    )
    assert current["capitalization_state"] == "SHARE_SOURCE_UNAVAILABLE"
    assert current["total_shares"] is None
    assert current["total_market_cap_cny"] is None
    assert ledger == []
    assert retry["attempt_count"] == CONFIG["source_route"]["maximum_attempts"]


def test_duplicate_snapshot_rows_fail_closed():
    duplicate = pd.concat([snapshot(), snapshot()], ignore_index=True)
    current, _, _ = build_symbol_result(
        security(),
        duplicate,
        CONFIG,
        "FMDL1_TEST",
        "UNIVERSE_TEST",
        "SNAPSHOT_TEST",
        provider=lambda symbol: share_frame(),
    )
    assert current["capitalization_state"] == "PRICE_UNAVAILABLE"
    assert current["state_reason"] == "SNAPSHOT_ROW_COUNT_NOT_ONE"
    assert current["total_market_cap_cny"] is None
