from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import fmdl4_architecture_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4_program_contract.json"


def load_contract():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_frozen_contract_is_valid():
    assert core.validate_contract_shape(load_contract()) == []


def test_raw_score_to_action_gate_is_required():
    cfg = load_contract()
    cfg["global_hard_gates"].remove("ZERO_RAW_SCORE_TO_PORTFOLIO_ACTION")
    assert "GLOBAL_HARD_GATES" in core.validate_contract_shape(cfg)


def test_only_investment_state_layer_may_mutate_state():
    cfg = load_contract()
    cfg["layer_model"][1]["may_mutate_investment_state"] = True
    assert "STATE_MUTATION_OWNERSHIP" in core.validate_contract_shape(cfg)


def test_real_account_chain_ends_with_user_confirmation():
    cfg = load_contract()
    cfg["role_separation"]["real_account"]["required_chain"][-1] = "AUTOMATIC_EXECUTION"
    assert "REAL_ACCOUNT_GATE_CHAIN" in core.validate_contract_shape(cfg)


def test_phase_skip_is_rejected():
    cfg = load_contract()
    cfg["phase_sequence"] = copy.deepcopy(cfg["phase_sequence"][:-1])
    errors = core.validate_contract_shape(cfg)
    assert "PHASE_SEQUENCE" in errors
    assert "PHASE_GATE_CHAIN" in errors
