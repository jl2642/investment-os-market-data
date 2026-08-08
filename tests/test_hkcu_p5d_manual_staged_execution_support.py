from __future__ import annotations

import json
from pathlib import Path

from pipeline.hkcu_p5d_manual_staged_execution_support import (
    allocate_whole_lot_batches,
    floor_to_lot,
    synthetic_engine_capability,
)


def test_floor_to_lot() -> None:
    assert floor_to_lot(319.9, 100) == 300
    assert floor_to_lot(400.0, 200) == 400


def test_allocate_whole_lot_batches() -> None:
    assert allocate_whole_lot_batches(300, 100, [0.5, 0.5]) == [100, 200]
    assert allocate_whole_lot_batches(400, 200, [0.5, 0.5]) == [200, 200]


def test_synthetic_engine_uses_test_only_ids() -> None:
    contract = {
        "engine_capability_contract": {
            "required_capabilities": [
                "CAPITAL_AMOUNT_FROM_WEIGHT_AND_NAV",
                "BOARD_LOT_FLOOR_ROUNDING",
                "MULTI_BATCH_WHOLE_LOT_ALLOCATION",
                "MAX_PRICE_DRIFT_GUARD",
            ],
            "synthetic_nav_hkd": 1000000.0,
            "synthetic_securities": [
                {
                    "security_id": "TEST_ALPHA",
                    "reference_price_hkd": 50.0,
                    "board_lot": 100,
                    "target_weight": 0.015,
                    "batch_fractions": [0.5, 0.5],
                    "max_price_drift_pct": 0.03,
                }
            ],
        }
    }
    result = synthetic_engine_capability(contract)
    assert result["status"] == "PASS_SYNTHETIC_ENGINE_CAPABILITY"
    assert result["executable"] is False
    row = result["rows"][0]
    assert row["security_id"].startswith("TEST_")
    assert row["rounded_shares"] == 300
    assert sum(row["batch_shares"]) == row["rounded_shares"]
    assert row["rounded_capital_hkd"] <= row["target_capital_hkd"]


def test_contract_freezes_no_execution_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "config/hkcu_p5d_manual_staged_execution_support_contract.json").read_text(encoding="utf-8"))
    assert contract["development_mode_policy"]["continue_or_development_command_is_trade_approval"] is False
    assert contract["phase_boundary"]["production_manual_execution_checklist_authorized"] is False
    assert contract["phase_boundary"]["real_account_mutation_authorized"] is False
    assert contract["phase_boundary"]["order_creation_authorized"] is False
    assert contract["phase_boundary"]["trade_authority"] == "NONE"
    assert contract["acceptance"]["next_gate_on_pass"] == "P5E_ZERO_EXECUTION_RECONCILIATION_AND_OBSERVATION"


def test_p5d_gate_state_matches_canonical_p5c_output_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    p5d = json.loads((root / "config/hkcu_p5d_manual_staged_execution_support_contract.json").read_text(encoding="utf-8"))
    p5c = json.loads((root / "config/hkcu_p5c_user_decision_gate_contract.json").read_text(encoding="utf-8"))
    source = (root / "pipeline/hkcu_p5c_user_decision_gate.py").read_text(encoding="utf-8")
    assert p5d["entry_contract"]["required_p5c_gate_state"] == p5c["decision_policy"]["current_gate_state_on_pass"]
    assert '"gate_state"' in source
