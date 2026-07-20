from __future__ import annotations

import hashlib
import json

from config.fmdl4b_research_profiles import PROFILE_PAYLOAD_SHA256, load_profiles
from scripts import fmdl4b_core as core


def sample_cfg() -> dict:
    return {
        "research_cohort": {"minimum_public_source_count": 2, "required_current_source_year": 2026},
        "graduation_policy": {
            "allowed_decisions": ["GRADUATED", "DEFERRED", "REJECTED"],
            "required_pm_fields": ["why_now", "variant_perception", "first_rejection", "what_would_make_investable", "prove_kill_checks", "next_workflow"],
            "required_research_fields": ["business_model", "competitive_position", "owner_quality", "earnings_drivers", "catalysts", "risks", "public_sources"],
        },
        "stage_model": {"decision_to_stage": {"GRADUATED": "INVESTMENT_CASE_READY", "DEFERRED": "DEFERRED", "REJECTED": "REJECTED"}},
    }


def sample_profile() -> dict:
    return {
        "symbol": "600900.SH", "name": "长江电力", "decision": "GRADUATED", "research_stage": "INVESTMENT_CASE_READY",
        "business_model": "Large-scale hydropower asset owner and operator with long-lived infrastructure.",
        "competitive_position": "Scarce strategic river-basin assets with durable grid relevance.",
        "owner_quality": "State-controlled operator with audited disclosure and capital-allocation review needs.",
        "earnings_drivers": ["generation", "power price", "financing cost"], "catalysts": ["hydrology normalization"],
        "risks": ["weak hydrology", "policy changes"], "variant_perception": "Cash-yield durability may matter more than short-term momentum.",
        "why_now": "Current evidence supports a fresh research review of recurring cash flow.",
        "first_rejection": "Normalized cash flow no longer covers distributions.",
        "what_would_make_investable": "Stable cash generation and valuation downside protection.",
        "prove_kill_checks": ["generation", "cash coverage"], "decision_reason_codes": ["DURABLE_ASSET_BASE"],
        "graduation_condition": "PORTFOLIO_FIT_REQUIRED", "next_workflow": "initiating-coverage",
        "public_sources": [
            {"source_id": "s1", "title": "Annual report", "source_date": "2026-04-30", "source_type": "annual_report", "url": "https://example.com/a"},
            {"source_id": "s2", "title": "Quarterly report", "source_date": "2026-04-30", "source_type": "quarterly_report", "url": "https://example.com/q"},
        ],
    }


def sample_envelope() -> dict:
    return {
        "evidence_id": "FMDL4A-EV-600900.SH-1234567890abcdef", "as_of": "2026-07-17", "quality_state": "DECISION_GRADE",
        "financial_evidence": {"financial_score": 80}, "valuation_evidence": {"pe_ttm": 18}, "market_evidence": {"close": 30},
        "shareholder_return_evidence": {"dividend_yield_ttm": 0.03}, "screening_evidence": {"overall_rank": 1},
        "controlled_limitations": [], "source_release_ids": {"FMDL-2": "r2", "FMDL-3C-D": "r3", "FMDL-3E-FINAL": "r4"},
    }


def test_profile_payload_identity_and_counts():
    profiles = load_profiles()
    payload = json.dumps(core.canonical(profiles), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == PROFILE_PAYLOAD_SHA256
    assert len(profiles) == 20 and len({profile["symbol"] for profile in profiles}) == 20
    assert {profile["decision"] for profile in profiles} == {"GRADUATED", "DEFERRED", "REJECTED"}


def test_research_object_is_deterministic_and_valid():
    registry = {"overall_rank": 1, "research_priority": "A_IMMEDIATE_RESEARCH"}
    first = core.research_object(sample_profile(), registry, sample_envelope(), research_version="RV1", authority="PUBLIC_EQUITY_RESEARCH_AND_GRADUATION_ONLY")
    second = core.research_object(sample_profile(), registry, sample_envelope(), research_version="RV1", authority="PUBLIC_EQUITY_RESEARCH_AND_GRADUATION_ONLY")
    assert first == second and core.validate_research_object(first, sample_cfg()) == []
    assert first["trade_authority"] == "NONE" and first["state_mutation_authorized"] is False


def test_research_object_changes_when_thesis_changes():
    registry = {"overall_rank": 1, "research_priority": "A_IMMEDIATE_RESEARCH"}
    first = core.research_object(sample_profile(), registry, sample_envelope(), research_version="RV1", authority="PUBLIC_EQUITY_RESEARCH_AND_GRADUATION_ONLY")
    changed = sample_profile(); changed["why_now"] = "A different current catalyst changes the research question."
    second = core.research_object(changed, registry, sample_envelope(), research_version="RV1", authority="PUBLIC_EQUITY_RESEARCH_AND_GRADUATION_ONLY")
    assert first["research_id"] != second["research_id"] and first["semantic_hash"] != second["semantic_hash"]


def test_raw_score_only_decision_detection():
    profile = sample_profile(); assert core.raw_score_only_decision(profile) is False
    profile["why_now"] = ""; assert core.raw_score_only_decision(profile) is True


def test_stable_hash_ignores_dict_order():
    assert core.stable_hash({"a": 1, "b": 2}) == core.stable_hash({"b": 2, "a": 1})


def test_all_graduated_profiles_are_case_ready_not_trade_ready():
    graduated = [profile for profile in load_profiles() if profile["decision"] == "GRADUATED"]
    assert len(graduated) >= 5
    assert all(profile["research_stage"] == "INVESTMENT_CASE_READY" for profile in graduated)
    assert all("TRADE" not in profile["graduation_condition"] for profile in graduated)
