from __future__ import annotations

import json
from pathlib import Path

from pipeline.hkcu_p5e_zero_execution_reconciliation_observation import sha256_file


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "x.txt"
    path.write_text("abc\n", encoding="utf-8")
    first = sha256_file(path)
    second = sha256_file(path)
    assert first == second
    assert len(first) == 64


def test_contract_freezes_zero_execution_and_closure_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "config/hkcu_p5e_zero_execution_reconciliation_observation_contract.json").read_text(encoding="utf-8"))
    policy = contract["zero_execution_reconciliation_policy"]
    boundary = contract["phase_boundary"]
    acceptance = contract["acceptance"]
    assert policy["user_supplied_real_execution_fact_count"] == 0
    assert policy["explicit_simulation_activation_record_count"] == 0
    assert policy["zero_writeback_required"] is True
    assert policy["protected_current_hashes_must_remain_identical"] is True
    assert boundary["real_account_mutation_authorized"] is False
    assert boundary["simulation_mutation_authorized"] is False
    assert boundary["candidate_pool_mutation_authorized"] is False
    assert boundary["order_creation_authorized"] is False
    assert boundary["phase_5_closure_authorized"] is True
    assert boundary["p5f_or_later_business_gate_authorized"] is False
    assert boundary["phase_6_creation_authorized"] is False
    assert acceptance["phase_5_close_status"] == "PHASE_5_CLOSED"
    assert acceptance["post_p5e_operating_state"] == "HKCU_SPECIAL_DEVELOPMENT_COMPLETE_OPERATING_OBSERVATION"
    assert acceptance["next_business_gate"] is None
    assert acceptance["trade_authority"] == "NONE"


def test_p5e_matches_frozen_p5a_post_close_state_and_p5d_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    p5a = json.loads((root / "config/hkcu_p5a_phase5_contract_entry_freeze.json").read_text(encoding="utf-8"))
    p5d = json.loads((root / "config/hkcu_p5d_manual_staged_execution_support_contract.json").read_text(encoding="utf-8"))
    p5e = json.loads((root / "config/hkcu_p5e_zero_execution_reconciliation_observation_contract.json").read_text(encoding="utf-8"))
    assert p5e["entry_contract"]["required_p5d_next_gate"] == p5d["acceptance"]["next_gate_on_pass"]
    assert p5e["acceptance"]["post_p5e_operating_state"] == p5a["planning_governance"]["post_p5e_state_on_pass"]
    assert p5a["planning_governance"]["p5f_or_later_business_gate_authorized"] is False
    assert p5a["planning_governance"]["phase_6_creation_authorized"] is False


def test_observation_counts_match_frozen_candidate_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "config/hkcu_p5e_zero_execution_reconciliation_observation_contract.json").read_text(encoding="utf-8"))
    candidate_path = root / contract["authoritative_inputs"]["hk_candidate_current"]
    row_count = len(candidate_path.read_text(encoding="utf-8").splitlines()) - 1
    assert row_count == contract["entry_contract"]["required_candidate_count"] == 70
    assert contract["entry_contract"]["required_p5c_focus_security_count"] == 4
