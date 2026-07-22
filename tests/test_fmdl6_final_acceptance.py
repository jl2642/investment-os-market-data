from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6_final_acceptance import (  # noqa: E402
    audit_root,
    build_candidate,
    clean_room_restore,
    failure_rollback,
    load_json,
    validate_candidate,
    write_json,
)

CONTRACT = ROOT / "config/fmdl6_final_resume_ready_operational_acceptance.json"


def test_component_chain_and_activation_gate_pass() -> None:
    contract = load_json(CONTRACT)
    checks, errors, chain = audit_root(ROOT, contract)
    assert not errors
    assert len(chain) == 6
    assert [row["release_sequence"] for row in chain] == [19, 20, 21, 22, 23, 24]
    assert all(row["trade_authority"] == "NONE" for row in chain)
    assert len(checks) >= 90


def test_clean_room_restore_and_failure_rollback_pass() -> None:
    contract = load_json(CONTRACT)
    restore = clean_room_restore(ROOT, contract)
    rollback = failure_rollback(ROOT, contract)
    assert restore["clean_room_restore"] == "PASS"
    assert restore["chat_memory_required"] is False
    assert rollback["injection_count"] == 5
    assert rollback["false_negative_count"] == 0
    assert rollback["upstream_lkg_unchanged"] is True


def test_candidate_build_validate_and_same_input_replay(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    release = build_candidate(ROOT, CONTRACT, candidate)
    assert release["status"] == "FMDL6_RESUME_READY_OPERATIONAL_ACCEPTANCE_ACCEPTED"
    assert release["activation_gate_status"] == "CLOSED"
    assert release["phase_completion_status"] == "PHASE_COMPLETE_A_SHARE_HK_OPERATIONAL_US_RESUME_READY"
    acceptance = validate_candidate(ROOT, CONTRACT, candidate, tmp_path / "acceptance.json")
    assert acceptance["validation"] == "PASS"
    assert acceptance["same_input_replay"] == "PASS"
    decision = load_json(candidate / "FMDL6FINAL_DECISION.json")
    assert decision["separate_technical_development_closeout_required"] is False
    assert decision["operating_observation_required"] is True
    assert decision["trade_authority"] == "NONE"


def test_candidate_tamper_is_rejected(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    build_candidate(ROOT, CONTRACT, candidate)
    decision_path = candidate / "FMDL6FINAL_DECISION.json"
    decision = load_json(decision_path)
    decision["candidate_pool_mutation_count"] = 1
    write_json(decision_path, decision)
    with pytest.raises(ValueError):
        validate_candidate(ROOT, CONTRACT, candidate, tmp_path / "acceptance.json")


def test_user_guide_and_library_retention_are_explicit(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    build_candidate(ROOT, CONTRACT, candidate)
    guide = (candidate / "FMDL6FINAL_USER_OPERATING_GUIDE.md").read_text(encoding="utf-8")
    retention = json.loads((candidate / "FMDL6FINAL_LIBRARY_RETENTION.json").read_text(encoding="utf-8"))
    assert "FMDL-6X1" in guide and "FMDL-6X4" in guide
    assert "新的专用窗口" in guide
    assert retention["separate_fmdl6_file_library_upload_required"] is False
    assert len(retention["keep_only"]) == 2
