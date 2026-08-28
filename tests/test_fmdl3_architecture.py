from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_fmdl3_architecture import (
    ARCHITECTURE_DOC,
    CONTRACT_PATH,
    EXPECTED_PHASES,
    PIT_DOC,
    PLAN_DOC,
    REQUIRED_DATASETS,
    REQUIRED_GATES,
    REQUIRED_PROFILES,
    REQUIRED_TEMPORAL_FIELDS,
    SCHEMA_PATH,
    validate_contract,
    validate_documents,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_and_schema_pass():
    checks, failures = validate_contract(load(CONTRACT_PATH), load(SCHEMA_PATH))
    assert not failures, checks
    assert all(row["status"] == "PASS" for row in checks)


def test_phase_sequence_is_frozen():
    contract = load(CONTRACT_PATH)
    assert [row["phase_id"] for row in contract["phase_sequence"]] == EXPECTED_PHASES
    assert contract["next_phase"] == "FMDL-3A"


def test_required_sector_profiles_are_present():
    contract = load(CONTRACT_PATH)
    profiles = {row["profile_id"] for row in contract["sector_profiles"]}
    assert REQUIRED_PROFILES.issubset(profiles)


def test_point_in_time_fields_and_zero_tolerance_gates_are_frozen():
    contract = load(CONTRACT_PATH)
    fields = set(contract["point_in_time_contract"]["required_temporal_fields"])
    gates = set(contract["global_hard_gates"])
    assert REQUIRED_TEMPORAL_FIELDS.issubset(fields)
    assert REQUIRED_GATES.issubset(gates)
    assert "FUTURE_INFORMATION_IN_POINT_IN_TIME_OUTPUT" in contract["point_in_time_contract"]["zero_tolerance_failures"]


def test_canonical_datasets_and_current_paths_are_defined():
    contract = load(CONTRACT_PATH)
    datasets = {row["dataset_id"]: row for row in contract["canonical_datasets"]}
    assert REQUIRED_DATASETS.issubset(datasets)
    assert all(row["current_path"].startswith("outputs/") for row in datasets.values())
    assert all(row["current_path"].endswith("/current/") for row in datasets.values())


def test_fail_closed_publication_and_authority_boundary():
    contract = load(CONTRACT_PATH)
    publication = contract["publication_contract"]
    assert publication["archive_is_immutable"] is True
    assert publication["last_known_good_required"] is True
    assert publication["candidate_cannot_replace_current_on_failure"] is True
    assert publication["point_in_time_replay_required_before_final_acceptance"] is True
    assert contract["authority"] == "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    assert contract["trade_authority"] == "NONE"


def test_architecture_documents_pass_content_checks():
    checks, failures = validate_documents()
    assert not failures, checks
    assert all(row["status"] == "PASS" for row in checks)
    for path in [ARCHITECTURE_DOC, PIT_DOC, PLAN_DOC]:
        assert path.exists()
        assert len(path.read_text(encoding="utf-8")) > 1000


def test_full_market_scope_not_current_longlist_only():
    architecture = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    plan = PLAN_DOC.read_text(encoding="utf-8")
    assert "must not collect fundamentals only for the current 100-name Longlist" in architecture
    assert "Full-market first" in plan


def test_no_period_end_as_availability_date():
    pit = PIT_DOC.read_text(encoding="utf-8")
    assert "`report_period_end` is never a substitute for public availability" in pit
    assert "zero use of report-period end as availability date" in pit


def test_readme_exposes_current_operating_state_and_authority_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Development Complete · Operating Observation" in readme
    assert "trade_authority = NONE" in readme
