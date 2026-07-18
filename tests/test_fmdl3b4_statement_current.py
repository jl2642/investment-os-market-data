from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fmdl3b4_contract_is_fail_closed() -> None:
    cfg = json.loads((ROOT / "config/fmdl3b4_statement_current.json").read_text(encoding="utf-8"))
    assert cfg["entry_gates"]["fmdl3b2_status"] == "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE"
    assert cfg["entry_gates"]["fmdl3b3_status"] == "FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED"
    assert cfg["publication"]["candidate_cannot_replace_current_on_failure"] is True
    assert cfg["publication"]["versioned_release_is_immutable"] is True
    assert cfg["trade_authority"] == "NONE"


def test_fmdl3b4_closes_statement_store_and_routes_to_factors() -> None:
    cfg = json.loads((ROOT / "config/fmdl3b4_statement_current.json").read_text(encoding="utf-8"))
    assert cfg["exit_status"] == "FMDL3B4_POINT_IN_TIME_STATEMENT_STORE_ACCEPTED"
    assert cfg["exit_gate"] == "POINT_IN_TIME_STATEMENT_STORE_ACCEPTED"
    assert cfg["next_gate"] == "FMDL-3C_FINANCIAL_QUALITY_GROWTH_AND_BALANCE_SHEET_FACTORS"


def test_release_schema_matches_contract() -> None:
    cfg = json.loads((ROOT / "config/fmdl3b4_statement_current.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/fmdl3b4_statement_current_v1.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["status"]["const"] == cfg["exit_status"]
    assert schema["properties"]["next_gate"]["const"] == cfg["next_gate"]
    assert schema["properties"]["trade_authority"]["const"] == "NONE"
