import json
from pathlib import Path

import pandas as pd

from scripts.benchmark_historical_sources import BOARD_QUOTAS, select_sample

ROOT = Path(__file__).resolve().parents[1]


def test_factor_registry_is_unique_and_research_only() -> None:
    registry = json.loads((ROOT / "config/fmdl2_factor_registry.json").read_text(encoding="utf-8"))
    factor_ids = [item["factor_id"] for item in registry["factors"]]
    assert len(factor_ids) == len(set(factor_ids))
    assert registry["authority_boundary"] == "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY"
    assert "BUY_PERMISSION" in registry["prohibited_actions"]
    assert "pe" in registry["deferred_to_fmdl3"]
    assert "return_20d" in factor_ids
    assert "avg_turnover_cny_60d" in factor_ids


def test_factor_windows_and_minimum_observations_are_positive() -> None:
    registry = json.loads((ROOT / "config/fmdl2_factor_registry.json").read_text(encoding="utf-8"))
    for factor in registry["factors"]:
        assert factor["window"] > 0
        assert factor["minimum_observations"] > 0
        assert factor["minimum_observations"] <= factor["window"] + 1


def test_benchmark_sample_is_deterministic_and_board_stratified() -> None:
    rows = []
    code = 0
    for board, quota in BOARD_QUOTAS.items():
        for index in range(quota + 5):
            code += 1
            suffix = "SH" if board in {"SH_MAIN", "STAR"} else "SZ" if board in {"SZ_MAIN", "CHINEXT"} else "BJ"
            rows.append({
                "symbol": f"{code:06d}.{suffix}",
                "board": board,
                "is_st": index == 0,
                "is_suspended": index == 1,
                "list_date": "2020-01-01",
            })
    universe = pd.DataFrame(rows)
    first = select_sample(universe)
    second = select_sample(universe)
    assert first["symbol"].tolist() == second["symbol"].tolist()
    assert len(first) == sum(BOARD_QUOTAS.values())
    assert first["board"].value_counts().to_dict() == BOARD_QUOTAS
