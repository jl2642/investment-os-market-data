from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6a_builder import build_candidate, load_json, sha256_file, validate_contract  # noqa: E402

CONTRACT_PATH = ROOT / "config/fmdl6a_us_market_security_identity_contract.json"


def contract() -> dict:
    return load_json(CONTRACT_PATH)


def test_contract_passes_all_gates() -> None:
    checks, errors = validate_contract(ROOT, CONTRACT_PATH)
    assert not errors
    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_identity_layers_separate_mutable_listing_keys() -> None:
    data = contract()
    identity = data["identity_model"]
    assert {row["layer"] for row in identity["layers"]} == {"ISSUER", "SHARE_CLASS", "SECURITY", "LISTING"}
    assert identity["ticker_is_identity"] is False
    assert identity["exchange_is_identity"] is False
    listing = next(row for row in identity["layers"] if row["layer"] == "LISTING")
    security = next(row for row in identity["layers"] if row["layer"] == "SECURITY")
    assert "TICKER" in listing["canonical_id_pattern"]
    assert "TICKER" not in security["canonical_id_pattern"]


def test_ticker_and_exchange_changes_preserve_security() -> None:
    rules = {row["event_type"]: row for row in contract()["lifecycle_rules"]}
    for event in ("TICKER_CHANGE", "EXCHANGE_TRANSFER"):
        row = rules[event]
        assert row["issuer_id_action"] == "PRESERVE"
        assert row["share_class_id_action"] == "PRESERVE"
        assert row["security_id_action"] == "PRESERVE"
        assert row["listing_id_action"] == "CLOSE_OLD_CREATE_NEW"


def test_unknown_and_otc_cases_are_not_included() -> None:
    data = contract()
    assert data["instrument_boundary"]["unknown_instrument_policy"] == "QUARANTINE_NOT_DEFAULT_INCLUDE"
    assert "OTC_SECURITY" in data["instrument_boundary"]["excluded"]
    rules = {row["event_type"]: row for row in data["lifecycle_rules"]}
    assert rules["DELISTING_TO_OTC"]["pilot_membership_action"] == "REMOVE_NO_OTC_FALLBACK"


def test_case_fixture_ids_are_unique_and_complete() -> None:
    rows = contract()["identity_case_fixtures"]
    ids = [row["case_id"] for row in rows]
    assert len(rows) == 12
    assert len(ids) == len(set(ids))
    assert {"CASE_MULTIPLE_SHARE_CLASSES", "CASE_ADR_WITH_UNDERLYING", "CASE_TICKER_CHANGE", "CASE_DELISTING_TO_OTC"}.issubset(ids)


def test_candidate_build_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    one = build_candidate(ROOT, CONTRACT_PATH, first)
    two = build_candidate(ROOT, CONTRACT_PATH, second)
    assert one == two
    hashes_one = {path.name: sha256_file(path) for path in first.iterdir() if path.is_file()}
    hashes_two = {path.name: sha256_file(path) for path in second.iterdir() if path.is_file()}
    assert hashes_one == hashes_two


def test_trade_authority_mutation_fails(tmp_path: Path) -> None:
    mutated = copy.deepcopy(contract())
    mutated["trade_authority"] = "BROKER"
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")
    _, errors = validate_contract(ROOT, path)
    assert "TRADE_AUTHORITY" in errors


def test_live_build_authorization_mutation_fails(tmp_path: Path) -> None:
    mutated = copy.deepcopy(contract())
    mutated["scope"]["live_security_master_build_authorized"] = True
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")
    _, errors = validate_contract(ROOT, path)
    assert "AUTHORIZATION_FALSE:live_security_master_build_authorized" in errors
