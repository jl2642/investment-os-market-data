from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fmdl5_final_core import build_candidate, load_json, read_csv, validate_components

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_component_chain_is_accepted() -> None:
    contract = load_json(REPO_ROOT / "config/fmdl5_final_operational_acceptance.json")
    components, errors = validate_components(REPO_ROOT, contract)
    assert errors == []
    assert len([key for key in components if key.startswith("FMDL-5")]) == 9
    assert components["FMDL-5G"]["next_gate"] == "FMDL-5-FINAL_OPERATIONAL_ACCEPTANCE"


def test_us_next_program_scope_is_bounded() -> None:
    contract = load_json(REPO_ROOT / "config/fmdl5_final_operational_acceptance.json")
    plan = contract["next_program_policy"]
    assert plan["scope_mode"] == "INTERFACE_AND_SMALL_BENCHMARK_ONLY"
    assert plan["benchmark_security_target"] == 24
    assert plan["full_universe_development_authorized"] is False
    assert plan["candidate_pool_integration_authorized"] is False


def test_build_candidate_accepts_end_to_end_chain(tmp_path: Path) -> None:
    decision = build_candidate(REPO_ROOT, tmp_path / "candidate")
    assert decision["status"] == "FMDL5_HONG_KONG_STOCK_CONNECT_OPERATIONAL_ACCEPTANCE_ACCEPTED"
    assert decision["metrics"]["southbound_security_count"] == 644
    assert decision["metrics"]["longlist_count"] == 100
    assert decision["metrics"]["formal_research_object_count"] == 20
    assert decision["metrics"]["state_transition_count"] == 6


def test_lineage_and_state_boundaries(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    decision = build_candidate(REPO_ROOT, candidate)
    lineage = read_csv(candidate / "FMDL5_FINAL_END_TO_END_LINEAGE.csv")
    assert len(lineage) == 6
    assert all(row["lineage_status"] == "PASS" for row in lineage)
    assert len({row["security_id"] for row in lineage}) == 6
    for field in [
        "candidate_pool_mutation_count", "simulation_mutation_count",
        "real_account_mutation_count", "order_generation_count", "trade_authority_error_count"
    ]:
        assert decision["metrics"][field] == 0


def test_same_input_is_idempotent(tmp_path: Path) -> None:
    first = build_candidate(REPO_ROOT, tmp_path / "first")
    second = build_candidate(REPO_ROOT, tmp_path / "second")
    assert first["release_id"] == second["release_id"]
    assert first["canonical_sha256"] == second["canonical_sha256"]
