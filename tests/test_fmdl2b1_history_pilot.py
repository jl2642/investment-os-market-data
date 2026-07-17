from datetime import date
import json
from pathlib import Path

import pandas as pd

from scripts.run_history_pilot import canonicalize_history, select_pilot_sample, validate_series

ROOT = Path(__file__).resolve().parents[1]


def _synthetic_universe() -> pd.DataFrame:
    rows = []
    board_suffix = {
        "SH_MAIN": "SH",
        "SZ_MAIN": "SZ",
        "STAR": "SH",
        "CHINEXT": "SZ",
        "BSE": "BJ",
    }
    counter = 0
    for board in board_suffix:
        for index in range(90):
            counter += 1
            rows.append({
                "symbol": f"{counter:06d}.{board_suffix[board]}",
                "board": board,
                "is_st": index == 0,
                "is_suspended": index == 1,
                "list_date": None if index == 2 else ("2026-06-01" if index == 3 else "2020-01-01"),
            })
    return pd.DataFrame(rows)


def test_pilot_sample_is_deterministic_and_matches_board_quotas() -> None:
    config = json.loads((ROOT / "config/fmdl2_history_store.json").read_text(encoding="utf-8"))
    universe = _synthetic_universe()
    first = select_pilot_sample(universe, config, date(2026, 7, 16))
    second = select_pilot_sample(universe, config, date(2026, 7, 16))
    assert first["symbol"].tolist() == second["symbol"].tolist()
    assert len(first) == 300
    assert first["board"].value_counts().to_dict() == config["pilot"]["board_quotas"]
    assert first["shard_id"].nunique() == 6


def test_canonical_history_preserves_null_and_provider_lineage() -> None:
    normalized = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-15", "2026-07-16"]),
        "open": [10.0, 10.2],
        "high": [10.3, 10.5],
        "low": [9.9, 10.1],
        "close": [10.2, 10.4],
        "volume": [1000.0, 1200.0],
        "amount": [10000.0, 12480.0],
    })
    sina = canonicalize_history(
        normalized, symbol="600000.SH", provider_id="sina_daily",
        retrieved_at="2026-07-16T17:30:00+08:00",
    )
    tencent = canonicalize_history(
        normalized, symbol="600000.SH", provider_id="tencent_hist",
        retrieved_at="2026-07-16T17:30:00+08:00",
    )
    assert sina["volume_shares"].notna().all()
    assert tencent["volume_shares"].isna().all()
    assert tencent["record_quality"].eq("PARTIAL_FALLBACK_PRICE_AMOUNT").all()
    assert sina["row_hash"].str.fullmatch(r"[a-f0-9]{64}").all()


def test_series_validation_blocks_future_and_impossible_ohlc() -> None:
    frame = pd.DataFrame({
        "trade_date": ["2026-07-16", "2026-07-17"],
        "open": [10.0, 10.0],
        "high": [10.2, 9.0],
        "low": [9.8, 10.1],
        "close": [10.1, 10.0],
        "volume_shares": [100.0, 100.0],
        "turnover_cny": [1000.0, 1000.0],
    })
    valid, reasons, counts = validate_series(frame, date(2026, 7, 16))
    assert not valid
    assert "FUTURE_ROWS" in reasons
    assert "IMPOSSIBLE_OHLC" in reasons
    assert counts["future_rows"] == 1


def test_contract_remains_research_only() -> None:
    config = json.loads((ROOT / "config/fmdl2_history_store.json").read_text(encoding="utf-8"))
    assert config["authority_boundary"].endswith("NO_TRADE_AUTHORITY")
    assert "CREATE_TRADE_PERMISSION" in config["prohibited_actions"]
    assert config["canonical_store"]["format"] == "PARQUET"
