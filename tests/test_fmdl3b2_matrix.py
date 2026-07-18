import json
from pathlib import Path

import jsonschema

from scripts import fmdl3b2_matrix_core as matrix

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
SCHEMA = ROOT / "schemas/fmdl3b2_matrix_v2.schema.json"
UNIVERSE = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
CANARY_RELEASE = ROOT / "outputs/financials/full_build/canary/current/FMDL3B2_CANARY_RELEASE.json"
WORKFLOW = ROOT / ".github/workflows/fmdl-3b2-full-universe-matrix.yml"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_matrix_contract_schema():
    jsonschema.validate(load(CONFIG), load(SCHEMA))


def test_canary_entry_gate_is_published_and_accepted():
    cfg = load(CONFIG)
    release = load(CANARY_RELEASE)
    assert release["status"] == cfg["entry_gate"]
    assert release["trade_authority"] == "NONE"


def test_full_universe_sharding_is_exact_deterministic_and_bounded():
    cfg = load(CONFIG)
    symbols = matrix.load_universe(UNIVERSE)
    first = matrix.assign_shards(symbols, cfg["sharding"]["shard_count"])
    second = matrix.assign_shards(symbols, cfg["sharding"]["shard_count"])
    assert first == second
    flattened = [symbol for shard_id in sorted(first) for symbol in first[shard_id]]
    assert len(flattened) == len(symbols)
    assert len(set(flattened)) == len(symbols)
    assert set(flattened) == set(symbols)
    assert max(map(len, first.values())) <= cfg["sharding"]["maximum_symbols_per_shard"]
    assert max(map(len, first.values())) - min(map(len, first.values())) <= 1


def test_membership_hash_is_order_independent():
    symbols = ["600519.SH", "000333.SZ", "688981.SH"]
    assert matrix.shard_membership_hash(symbols) == matrix.shard_membership_hash(list(reversed(symbols)))


def test_storage_separates_raw_artifacts_from_versioned_normalized_release():
    cfg = load(CONFIG)
    assert cfg["storage"]["raw"] == "IMMUTABLE_GITHUB_ACTIONS_ARTIFACT_SHARD"
    assert cfg["storage"]["normalized"] == "VERSIONED_GIT_PARQUET_SHARDS"
    assert cfg["storage"]["release_root"] != cfg["storage"]["current_root"]
    assert cfg["storage"]["maximum_git_file_mib"] < 100
    assert cfg["storage"]["candidate_cannot_replace_current_on_failure"] is True
    assert cfg["storage"]["versioned_release_is_immutable"] is True


def test_zero_tolerance_controlled_exclusion_and_no_trade_authority():
    cfg = load(CONFIG)
    for policy_name in ["shard_acceptance_policy", "aggregate_acceptance_policy"]:
        policy = cfg[policy_name]
        assert policy["maximum_ambiguous_mapping_group_count"] == 0
        assert policy["maximum_future_fact_count"] == 0
        assert policy["maximum_source_less_decision_grade_fact_count"] == 0
        assert policy["maximum_duplicate_effective_interval_count"] == 0
        assert policy["maximum_unclassified_conflict_count"] == 0
        assert policy["maximum_performed_validation_failure_count"] == 0
        assert policy["require_controlled_validation_exclusions_classified"] is True
        assert policy["require_affected_controlled_facts_removed_from_decision_grade"] is True
        assert policy["require_bse_official_query_resolution"] is True
        assert policy["trade_authority"] == "NONE"
    assert cfg["trade_authority"] == "NONE"


def test_workflow_declares_all_32_zero_padded_shards_hardened_execution_and_publication():
    text = WORKFLOW.read_text(encoding="utf-8")
    for shard_id in range(32):
        assert f'"{shard_id:02d}"' in text
    assert "max-parallel: 8" in text
    assert "run_fmdl3b2_shard_v2" in text
    assert "validate_fmdl3b2_shard_v2" in text
    assert "aggregate_fmdl3b2_matrix_v2" in text
    assert "validate_fmdl3b2_matrix_v2" in text
    assert "publish_fmdl3b2_matrix" in text
    assert "fmdl3b2-raw-shard-${{ matrix.shard_id }}" in text
