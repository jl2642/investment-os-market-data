from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fmdl6c_benchmark_pool import (  # noqa: E402
    build_candidate,
    independent_validate,
    load_json,
    sha256_file,
    stable_json,
    validate_contract,
    validate_directory_capture,
    write_json,
)

CONTRACT_PATH = ROOT / "config/fmdl6c_24_security_benchmark_pool_contract.json"


def synthetic_capture(missing: set[str] | None = None, etf: set[str] | None = None) -> dict:
    missing = missing or set()
    etf = etf or set()
    contract = load_json(CONTRACT_PATH)
    selected = []
    for row in contract["pool"]:
        found = row["ticker"] not in missing
        exchange_code = "Q" if row["mic"] == "XNAS" else "N" if row["mic"] == "XNYS" else "A"
        selected.append({
            "ticker": row["ticker"],
            "directory_symbol": row["directory_symbol"],
            "expected_mic": row["mic"],
            "found": found,
            "directory_row": None if not found else {
                "source_id": "NASDAQ_LISTED" if row["mic"] == "XNAS" else "OTHER_LISTED",
                "directory_symbol": row["directory_symbol"],
                "security_name": row["name"],
                "exchange_code": exchange_code,
                "etf": "Y" if row["ticker"] in etf else "N",
                "test_issue": "N",
                "financial_status": None,
            },
        })
    return {
        "program_id": "FMDL-6C",
        "captured_at_utc": "2026-07-22T00:00:00Z",
        "environment": "GITHUB_ACTIONS",
        "source_observations": [
            {"source_id": "NASDAQ_LISTED", "payload_sha256": "a" * 64, "row_count": 5000, "github_actions_compatible": True},
            {"source_id": "OTHER_LISTED", "payload_sha256": "b" * 64, "row_count": 7000, "github_actions_compatible": True},
        ],
        "selected_rows": selected,
        "trade_authority": "NONE",
    }


def test_contract_and_snapshot_pass() -> None:
    checks, errors = validate_contract(ROOT, CONTRACT_PATH)
    assert not errors
    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_pool_is_exactly_24_and_not_investment_state() -> None:
    contract = load_json(CONTRACT_PATH)
    assert len(contract["pool"]) == 24
    assert len({row["ticker"] for row in contract["pool"]}) == 24
    assert len({row["issuer_key"] for row in contract["pool"]}) >= 20
    assert all(row["benchmark_only"] for row in contract["pool"])
    assert all(not row["investment_eligible"] and not row["research_candidate"] for row in contract["pool"])
    assert all(row["trade_authority"] == "NONE" for row in contract["pool"])


def test_listing_effective_dates_are_not_invented() -> None:
    contract = load_json(CONTRACT_PATH)
    assert all(row["canonical_listing_key"] is None for row in contract["pool"])
    assert all(row["listing_effective_from"] is None for row in contract["pool"])
    assert all(row["listing_history_status"] == "CURRENT_SNAPSHOT_ONLY" for row in contract["pool"])
    assert all(row["listing_observed_active_on"] == "2026-07-22" for row in contract["pool"])


def test_case_coverage_contains_required_technical_cases() -> None:
    contract = load_json(CONTRACT_PATH)
    tags = {tag for row in contract["pool"] for tag in row["case_tags"]}
    assert set(contract["pool_requirements"]["required_case_tags"]) <= tags
    venue_counts = {mic: sum(row["mic"] == mic for row in contract["pool"]) for mic in ("XNAS", "XNYS", "XASE")}
    assert all(venue_counts.values())
    instrument_types = {row["instrument_type"] for row in contract["pool"]}
    assert instrument_types == {"COMMON_STOCK", "ADR", "FOREIGN_PRIVATE_ISSUER_ORDINARY", "EQUITY_REIT_COMMON"}


def test_synthetic_listing_capture_passes() -> None:
    contract = load_json(CONTRACT_PATH)
    checks, errors = validate_directory_capture(contract, synthetic_capture())
    assert not errors
    assert all(row["status"] == "PASS" for row in checks)


def test_missing_or_etf_listing_fails() -> None:
    contract = load_json(CONTRACT_PATH)
    _, missing_errors = validate_directory_capture(contract, synthetic_capture(missing={"AAPL"}))
    assert "LISTING_FOUND:AAPL" in missing_errors
    _, etf_errors = validate_directory_capture(contract, synthetic_capture(etf={"AAPL"}))
    assert "ETF_FALSE:AAPL" in etf_errors


def test_candidate_and_replay_are_deterministic(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    write_json(capture, synthetic_capture())
    candidate = tmp_path / "candidate"
    release = build_candidate(ROOT, CONTRACT_PATH, capture, candidate)
    assert release["status"] == "FMDL6C_24_SECURITY_BENCHMARK_POOL_ACCEPTED"
    assert release["security_count"] == 24
    assert release["benchmark_pool_is_not_candidate_pool"] is True
    assert release["historical_listing_effective_dates_resolved"] is False
    acceptance = independent_validate(ROOT, CONTRACT_PATH, capture, candidate)
    assert acceptance["validation"] == "PASS"
    assert acceptance["same_input_replay"] == "PASS"


def test_failed_listing_capture_cannot_publish(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    write_json(capture, synthetic_capture(missing={"UEC"}))
    with pytest.raises(ValueError):
        build_candidate(ROOT, CONTRACT_PATH, capture, tmp_path / "candidate")
