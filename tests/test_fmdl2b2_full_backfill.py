import json
from pathlib import Path

from scripts.run_full_backfill_shard import shard_for_symbol

ROOT = Path(__file__).resolve().parents[1]


def test_full_backfill_plan_is_authorized_and_research_only() -> None:
    plan = json.loads((ROOT / "config/fmdl2_full_backfill_plan.json").read_text(encoding="utf-8"))
    assert plan["status"] == "AUTHORIZED_FOR_FMDL_2B_2_IMPLEMENTATION"
    assert plan["sharding"]["logical_shards"] == 24
    assert plan["execution"]["initial_max_parallel_shards"] == 3
    assert "CREATE_CANDIDATE_BUY_PERMISSION" in plan["prohibited_actions"]
    assert plan["authority_boundary"].endswith("NO_TRADE_AUTHORITY")


def test_stable_shard_assignment_is_deterministic_and_bounded() -> None:
    symbols = ["600000.SH", "000001.SZ", "688001.SH", "300750.SZ", "920001.BJ"]
    first = [shard_for_symbol(symbol, 24) for symbol in symbols]
    second = [shard_for_symbol(symbol, 24) for symbol in symbols]
    assert first == second
    assert all(0 <= value < 24 for value in first)


def test_history_store_contract_preserves_missingness_and_provider_boundaries() -> None:
    contract = json.loads((ROOT / "config/fmdl2_history_store.json").read_text(encoding="utf-8"))
    assert contract["history_policy"]["missing_value_policy"] == "PRESERVE_NULL_NEVER_FILL_ZERO"
    assert contract["history_policy"]["provider_series_mixing"] == "FORBIDDEN"
    assert contract["canonical_store"]["format"] == "PARQUET"
    assert contract["canonical_store"]["compression"] == "zstd"
