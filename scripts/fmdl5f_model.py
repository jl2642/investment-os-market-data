#!/usr/bin/env python3
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import pandas as pd

from fmdl5f_core import (
    PROGRAM_ID, as_bool, case_types, clean_text, context_summary, finite,
    record_hash, stable_hash,
)

def build_object(
    long_row: pd.Series,
    factor_row: pd.Series,
    financial_row: pd.Series | None,
    profile: dict[str, Any],
    public_sources: list[dict[str, Any]],
    contract: dict[str, Any],
    profile_version: str,
) -> dict[str, Any]:
    code = clean_text(long_row["stock_code_5d"]).zfill(5)
    source_ids = contract["source_release_ids"]
    seed = {
        "security_id": clean_text(long_row["security_id"]),
        "as_of_date": clean_text(long_row["as_of_date"]),
        "fmdl5e_release": source_ids["fmdl5e"],
        "longlist_row_hash": record_hash(long_row),
        "profile_version": profile_version,
    }
    research_id = f"HK-RESEARCH-{code}-{stable_hash(seed)[:12]}"
    cases = case_types(long_row, profile)
    internal_sources = [
        {
            "source_type": "FMDL5E_ACCEPTED_SCREENING_ROW",
            "source_id": f"{source_ids['fmdl5e']}:{clean_text(long_row['security_id'])}",
            "source_hash": record_hash(long_row),
        },
        {
            "source_type": "FMDL5E_ACCEPTED_FACTOR_ROW",
            "source_id": f"{source_ids['fmdl5e']}:{clean_text(factor_row['security_id'])}",
            "source_hash": record_hash(factor_row),
        },
    ]
    if financial_row is not None:
        internal_sources.append({
            "source_type": "FMDL5D_ACCEPTED_FINANCIAL_CURRENT",
            "source_id": f"{source_ids['fmdl5d']}:{clean_text(financial_row['security_id'])}",
            "source_hash": record_hash(financial_row),
        })
    obj = {
        "program_id": PROGRAM_ID,
        "research_id": research_id,
        "as_of_date": clean_text(long_row["as_of_date"]),
        "security_id": clean_text(long_row["security_id"]),
        "stock_code_5d": code,
        "official_security_name_en": clean_text(long_row.get("official_security_name_en")),
        "official_issuer_name_en": clean_text(long_row.get("official_issuer_name_en")),
        "screening_profile": clean_text(factor_row.get("profile")),
        "source_profile": clean_text(factor_row.get("source_profile")),
        "profile_basis": clean_text(factor_row.get("profile_basis")),
        "profile_override_applied": as_bool(factor_row.get("profile_override_applied")),
        "source_release_ids": source_ids,
        "screening_context": context_summary(long_row),
        "case_types": cases,
        "business_model": profile["business_model"],
        "competitive_position": profile["competitive_position"],
        "owner_quality": profile["owner_quality"],
        "earnings_drivers": profile["earnings_drivers"],
        "catalysts": profile["catalysts"],
        "risks": profile["risks"],
        "variant_perception": profile["variant_perception"],
        "why_now": profile["why_now"],
        "first_rejection": profile["first_rejection"],
        "what_would_make_investable": profile["what_would_make_investable"],
        "prove_kill_checks": profile["prove_kill_checks"],
        "public_sources": public_sources,
        "evidence_bindings": internal_sources,
        "research_decision": profile["decision"],
        "research_stage": {
            "GRADUATED": "INVESTMENT_CASE_READY",
            "SHADOW_TRACK": "SHADOW_TRACK",
            "DEFERRED": "DEFERRED",
            "REJECTED": "REJECTED",
        }[profile["decision"]],
        "decision_basis": "CURATED_RESEARCH_PROFILE_PLUS_ACCEPTED_POINT_IN_TIME_EVIDENCE",
        "raw_score_only_decision": False,
        "graduation_boundary": contract["decision_policy"]["graduated_meaning"],
        "candidate_pool_admission": False,
        "simulation_admission": False,
        "real_account_admission": False,
        "order_generation": False,
        "next_workflow": contract["next_gate"],
        "authority": contract["authority"],
        "trade_authority": "NONE",
    }
    obj["object_sha256"] = stable_hash(obj)
    return obj


def build_registry(longlist: pd.DataFrame, profiles: dict[str, Any], contract: dict[str, Any]) -> pd.DataFrame:
    active_priority = contract["research_cohort"]["active_priority"]
    rows: list[dict[str, Any]] = []
    for _, row in longlist.sort_values("overall_rank").iterrows():
        code = clean_text(row["stock_code_5d"]).zfill(5)
        active = clean_text(row["research_priority"]) == active_priority
        profile = profiles.get(code)
        if active and profile:
            decision = profile["decision"]
            stage = {"GRADUATED": "INVESTMENT_CASE_READY", "SHADOW_TRACK": "SHADOW_TRACK", "DEFERRED": "DEFERRED", "REJECTED": "REJECTED"}[decision]
            reason = "FORMAL_RESEARCH_OBJECT_REQUIRED"
        elif active:
            decision, stage, reason = "DEFERRED", "DEFERRED", "ACTIVE_PROFILE_MISSING_FAIL_CLOSED"
        else:
            decision, stage, reason = contract["decision_policy"]["non_active_decision"], contract["decision_policy"]["non_active_stage"], "NOT_IN_CURRENT_ACTIVE_RESEARCH_COHORT"
        rows.append({
            "as_of_date": clean_text(row["as_of_date"]),
            "overall_rank": int(row["overall_rank"]),
            "research_priority": clean_text(row["research_priority"]),
            "security_id": clean_text(row["security_id"]),
            "stock_code_5d": code,
            "official_security_name_en": clean_text(row.get("official_security_name_en")),
            "primary_sleeve": clean_text(row.get("primary_sleeve")),
            "active_research_cohort": active,
            "research_stage": stage,
            "research_decision": decision,
            "decision_reason": reason,
            "candidate_pool_admission": False,
            "simulation_admission": False,
            "real_account_admission": False,
            "order_generation": False,
            "trade_authority": "NONE",
        })
    return pd.DataFrame(rows)


def quality(
    registry: pd.DataFrame,
    objects: list[dict[str, Any]],
    source_ledger: pd.DataFrame,
    case_coverage: pd.DataFrame,
    contract: dict[str, Any],
    missing_profiles: list[str],
) -> dict[str, Any]:
    cohort = contract["research_cohort"]
    policy = contract["decision_policy"]
    acceptance = contract["acceptance"]
    failures: list[str] = []
    object_codes = [obj["stock_code_5d"] for obj in objects]
    duplicate_registry = int(registry["security_id"].duplicated().sum())
    duplicate_objects = len(object_codes) - len(set(object_codes))
    decision_counts = pd.Series([obj["research_decision"] for obj in objects]).value_counts().astype(int).to_dict()
    grad_shadow = decision_counts.get("GRADUATED", 0) + decision_counts.get("SHADOW_TRACK", 0)
    source_errors = 0
    future_sources = 0
    raw_score_only = 0
    missing_evidence_bindings = 0
    invalid_decisions = 0
    for obj in objects:
        official = obj["public_sources"]
        bindings = obj["evidence_bindings"]
        total = len(official) + len(bindings)
        binding_types = {binding.get("source_type") for binding in bindings}
        required_bindings = {
            "FMDL5E_ACCEPTED_SCREENING_ROW",
            "FMDL5E_ACCEPTED_FACTOR_ROW",
            "FMDL5D_ACCEPTED_FINANCIAL_CURRENT",
        }
        if not required_bindings.issubset(binding_types):
            missing_evidence_bindings += 1
        if len(official) < cohort["minimum_official_source_references"] or total < cohort["minimum_total_source_references"]:
            source_errors += 1
        if obj["research_decision"] == "GRADUATED" and len(official) < cohort["minimum_official_sources_for_graduation"]:
            source_errors += 1
        cutoff = pd.Timestamp(obj["as_of_date"]).tz_localize("Asia/Hong_Kong") + pd.Timedelta(hours=23, minutes=59)
        for source in official:
            available = pd.to_datetime(source["available_from"], errors="coerce", utc=True)
            if pd.isna(available) or available > cutoff.tz_convert("UTC"):
                future_sources += 1
            if urlparse(source["url"]).netloc != contract["source_policy"]["official_domain"]:
                source_errors += 1
        if obj.get("raw_score_only_decision"):
            raw_score_only += 1
        if obj.get("research_decision") not in policy["allowed_decisions"]:
            invalid_decisions += 1
        if len(obj.get("prove_kill_checks", [])) < cohort["minimum_prove_kill_checks"]:
            source_errors += 1
    required_case_missing = int((case_coverage["coverage_count"] <= 0).sum()) if not case_coverage.empty else len(policy["required_case_types"])
    mutation_count = int(registry[["candidate_pool_admission", "simulation_admission", "real_account_admission", "order_generation"]].astype(bool).sum().sum())
    trade_errors = int((registry["trade_authority"] != "NONE").sum()) + sum(obj["trade_authority"] != "NONE" for obj in objects)
    formal_count = len(objects)
    if len(registry) != cohort["required_registry_count"]:
        failures.append("REGISTRY_COUNT")
    if formal_count < cohort["minimum_formal_object_count"] or formal_count > cohort["maximum_formal_object_count"] or formal_count != cohort["formal_object_target"]:
        failures.append("FORMAL_OBJECT_COUNT")
    if duplicate_registry > acceptance["maximum_duplicate_registry_security_count"]:
        failures.append("DUPLICATE_REGISTRY")
    if duplicate_objects > acceptance["maximum_duplicate_research_object_security_count"]:
        failures.append("DUPLICATE_OBJECTS")
    if len(missing_profiles) > acceptance["maximum_missing_active_profile_count"]:
        failures.append("MISSING_ACTIVE_PROFILES")
    if source_errors > acceptance["maximum_source_requirement_error_count"]:
        failures.append("SOURCE_REQUIREMENTS")
    if missing_evidence_bindings > acceptance["maximum_missing_evidence_binding_count"]:
        failures.append("MISSING_EVIDENCE_BINDINGS")
    if invalid_decisions:
        failures.append("INVALID_RESEARCH_DECISION")
    if future_sources > acceptance["maximum_future_source_count"]:
        failures.append("FUTURE_SOURCES")
    if raw_score_only > acceptance["maximum_raw_score_only_decision_count"]:
        failures.append("RAW_SCORE_ONLY_DECISIONS")
    low, high = policy["graduated_or_shadow_target_range"]
    if not (low <= grad_shadow <= high):
        failures.append("GRADUATED_SHADOW_COUNT")
    if required_case_missing > acceptance["maximum_required_case_type_missing_count"]:
        failures.append("REQUIRED_CASE_COVERAGE")
    if mutation_count > acceptance["maximum_state_mutation_count"]:
        failures.append("STATE_MUTATION")
    if trade_errors > acceptance["maximum_trade_authority_error_count"]:
        failures.append("TRADE_AUTHORITY")
    metrics = {
        "registry_count": len(registry),
        "active_research_cohort_count": int(registry["active_research_cohort"].sum()),
        "formal_research_object_count": formal_count,
        "decision_counts": decision_counts,
        "graduated_or_shadow_count": grad_shadow,
        "duplicate_registry_security_count": duplicate_registry,
        "duplicate_research_object_security_count": duplicate_objects,
        "missing_active_profile_count": len(missing_profiles),
        "source_requirement_error_count": source_errors,
        "missing_evidence_binding_count": missing_evidence_bindings,
        "invalid_research_decision_count": invalid_decisions,
        "future_source_count": future_sources,
        "raw_score_only_decision_count": raw_score_only,
        "required_case_type_missing_count": required_case_missing,
        "source_ledger_row_count": len(source_ledger),
        "official_source_row_count": int((source_ledger["source_class"] == "PUBLIC_OFFICIAL").sum()) if not source_ledger.empty else 0,
        "state_mutation_count": mutation_count,
        "trade_authority_error_count": trade_errors,
    }
    return {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "controlled_warnings": [],
        "metrics": metrics,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
    }
