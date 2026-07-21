from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from fmdl5g_core import build_candidate, load_jsonl, parse_case_types, sha256_object, transition_payload  # noqa: E402


def test_parse_case_types_is_sorted_and_unique() -> None:
    assert parse_case_types("HIGH_DIVIDEND|A_H|HIGH_DIVIDEND") == ["A_H", "HIGH_DIVIDEND"]


def test_transition_payload_is_deterministic_and_non_mutating() -> None:
    row = {
        "research_id": "HK-RESEARCH-00300-test",
        "security_id": "HKEX:00300",
        "stock_code_5d": "00300",
        "official_security_name_en": "MIDEA GROUP",
        "research_decision": "GRADUATED",
        "case_types": "A_H|HIGH_DIVIDEND",
        "object_sha256": "a" * 64,
    }
    first = transition_payload(row, "HK_CANDIDATE_REENTRY_REVIEW")
    second = transition_payload(row, "HK_CANDIDATE_REENTRY_REVIEW")
    assert first == second
    assert first["cross_market_duplication_review_required"] is True
    assert first["candidate_pool_mutation_authorized"] is False
    assert first["simulation_mutation_authorized"] is False
    assert first["real_account_mutation_authorized"] is False
    assert first["order_generation_authorized"] is False
    assert first["trade_authority"] == "NONE"
    expected = sha256_object({key: value for key, value in first.items() if key != "transition_sha256"})
    assert first["transition_sha256"] == expected


def test_shadow_transition_has_shadow_route_meaning() -> None:
    row = {
        "research_id": "HK-RESEARCH-09999-test",
        "security_id": "HKEX:09999",
        "stock_code_5d": "09999",
        "official_security_name_en": "NTES",
        "research_decision": "SHADOW_TRACK",
        "case_types": "WVR_OR_INTERNET",
        "object_sha256": "b" * 64,
    }
    payload = transition_payload(row, "HK_SHADOW_TRACK_REVIEW")
    assert payload["target_route"] == "HK_SHADOW_TRACK_REVIEW"
    assert "SHADOW_TRACK" in payload["state_meaning"]


def test_real_repository_candidate_build(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    decision = build_candidate(REPO_ROOT, output)
    assert decision["status"] == "FMDL5G_INVESTMENT_OS_INTEGRATION_ACCEPTED"
    assert decision["next_gate"] == "FMDL-5-FINAL_OPERATIONAL_ACCEPTANCE"
    assert decision["metrics"]["state_transition_count"] == 6
    assert decision["metrics"]["candidate_reentry_review_count"] == 4
    assert decision["metrics"]["shadow_track_review_count"] == 2
    assert decision["metrics"]["cross_market_duplication_review_count"] >= 2
    assert decision["candidate_pool_mutation_count"] == 0
    assert decision["simulation_mutation_count"] == 0
    assert decision["real_account_mutation_count"] == 0
    assert decision["order_generation_count"] == 0
    assert decision["trade_authority"] == "NONE"
    transitions = load_jsonl(output / "FMDL5G_STATE_TRANSITIONS.jsonl")
    assert len({row["security_id"] for row in transitions}) == 6


def test_same_input_canonical_identity(tmp_path: Path) -> None:
    first = build_candidate(REPO_ROOT, tmp_path / "first")
    second = build_candidate(REPO_ROOT, tmp_path / "second")
    assert first["canonical_sha256"] == second["canonical_sha256"]
    assert first["release_id"] == second["release_id"]
