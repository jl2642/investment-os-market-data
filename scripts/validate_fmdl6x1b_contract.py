#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "fmdl6x1b_anticipated_research_universe_contract.json"

REQUIRED_VENUES = ["XNYS", "XNAS", "XASE"]
REQUIRED_RESEARCH_STATUSES = {
    "RESEARCH_ELIGIBLE_CORE",
    "RESEARCH_ELIGIBLE_SPECIAL_PROFILE",
    "RESEARCH_REVIEW_REQUIRED",
    "REFERENCE_ONLY",
    "EXCLUDED",
    "QUARANTINED",
}
REQUIRED_CORE = {
    "US_DOMESTIC_COMMON_STOCK",
    "FOREIGN_PRIVATE_ISSUER_ORDINARY_SHARE",
    "SPONSORED_EXCHANGE_LISTED_ADR",
    "EQUITY_REIT_COMMON_STOCK",
}
REQUIRED_SPECIAL = {
    "BDC_COMMON_STOCK",
    "PUBLICLY_TRADED_PARTNERSHIP_OR_MLP_COMMON_UNIT",
    "ROYALTY_TRUST_OR_PASS_THROUGH_UNIT",
    "PRE_BUSINESS_COMBINATION_SPAC_COMMON_SHARE",
}
REQUIRED_EXCLUDED = {
    "PREFERRED_STOCK", "WARRANT", "RIGHT", "OPTION", "FUTURE",
    "SPAC_UNIT", "SPAC_WARRANT", "OTC_SECURITY", "UNSPONSORED_OTC_ADR"
}
EXIT = "FMDL6X1B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY_ACCEPTED"
NEXT = "FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION"


def load(path: Path = CONTRACT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("phase_id") != "FMDL-6X1-B":
        errors.append("phase_id")
    if data.get("status") not in {"CONTRACT_CANDIDATE", "ACCEPTED"}:
        errors.append("status")
    if data.get("trade_authority") != "NONE":
        errors.append("trade_authority")

    gate = data.get("entry_gate", {})
    if gate.get("required_release_id") != "FMDL6X1A_20260722_795fcd84ed00":
        errors.append("entry_release")
    if gate.get("required_status") != "FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED":
        errors.append("entry_status")
    if gate.get("required_next_gate") != "FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY":
        errors.append("entry_next_gate")

    scope = data.get("scope", {})
    forbidden = [
        "live_security_master_build_authorized",
        "historical_backfill_authorized",
        "source_route_revalidation_authorized",
        "factor_or_screening_production_authorized",
        "candidate_pool_integration_authorized",
        "simulation_integration_authorized",
        "real_account_integration_authorized",
        "order_generation_authorized",
    ]
    if any(scope.get(key) is not False for key in forbidden):
        errors.append("scope_authority")

    venue = data.get("venue_boundary", {})
    if venue.get("included_primary_venues") != REQUIRED_VENUES:
        errors.append("venues")
    if venue.get("otc_included") is not False:
        errors.append("otc")

    layers = data.get("universe_layers", {})
    master = layers.get("security_master_universe", {})
    if master.get("price_market_cap_liquidity_or_profitability_filters_forbidden") is not True:
        errors.append("master_filters")
    if master.get("excluded_instruments_retained_as_classified_records") is not True:
        errors.append("retained_exclusions")

    states = data.get("orthogonal_status_dimensions", {})
    if set(states.get("research_statuses", [])) != REQUIRED_RESEARCH_STATUSES:
        errors.append("research_statuses")
    if states.get("channel_status_default") != "CHANNEL_ELIGIBILITY_PENDING":
        errors.append("channel_default")
    if states.get("portfolio_status_default") != "PORTFOLIO_ADMISSION_NOT_AUTHORIZED":
        errors.append("portfolio_default")
    if states.get("research_and_channel_status_must_not_be_conflated") is not True:
        errors.append("orthogonal_status")

    instruments = data.get("instrument_classification", {})
    core = {item.get("instrument_type") for item in instruments.get("core_research_eligible", [])}
    special = {item.get("instrument_type") for item in instruments.get("special_profile_research_eligible", [])}
    excluded = set(instruments.get("explicitly_excluded", []))
    if not REQUIRED_CORE.issubset(core):
        errors.append("core_instruments")
    if not REQUIRED_SPECIAL.issubset(special):
        errors.append("special_instruments")
    if not REQUIRED_EXCLUDED.issubset(excluded):
        errors.append("excluded_instruments")
    if instruments.get("unknown_instrument_policy") != "QUARANTINE_NOT_DEFAULT_INCLUDE":
        errors.append("unknown_policy")
    for item in instruments.get("special_profile_research_eligible", []):
        if item.get("standard_industrial_factor_ranking_allowed") is not False:
            errors.append("special_profile_standard_ranking")
            break

    identity = data.get("identity_and_duplicate_rules", {})
    required_true = [
        "reuse_fmdl6a_identity_model",
        "issuer_share_class_security_listing_layers_required",
        "one_issuer_multiple_share_classes_preserved",
        "one_security_multiple_effective_dated_listings_preserved",
        "adr_is_distinct_security_from_underlying",
        "adr_underlying_cross_link_required",
        "cross_market_same_issuer_group_required",
        "a_h_adr_duplicate_exposure_review_required",
    ]
    if any(identity.get(key) is not True for key in required_true):
        errors.append("identity_rules")
    if identity.get("ticker_is_identity") is not False or identity.get("exchange_is_identity") is not False:
        errors.append("ticker_exchange_identity")

    pit = data.get("point_in_time_and_survivorship_rules", {})
    required_pit = [
        "membership_effective_from_and_effective_to_required",
        "retrieval_timestamp_required",
        "source_lineage_required",
        "delisted_acquired_and_renamed_securities_retained",
        "current_constituent_only_backfill_forbidden",
        "future_information_in_historical_membership_forbidden",
        "liquidity_price_market_cap_and_financial_filters_deferred_to_fmdl6x3",
    ]
    if any(pit.get(key) is not True for key in required_pit):
        errors.append("pit_rules")

    authority = data.get("classification_authority", {})
    if authority.get("silent_source_substitution_forbidden") is not True:
        errors.append("silent_substitution")
    if authority.get("fallback_may_create_decision_grade_classification") is not False:
        errors.append("fallback_authority")
    if authority.get("unresolved_conflict_action") != "QUARANTINE":
        errors.append("conflict_action")

    zero = data.get("zero_mutation_proof", {})
    if any(zero.get(key) != 0 for key in [
        "live_security_rows_created",
        "candidate_pool_mutations",
        "simulation_mutations",
        "real_account_mutations",
        "orders",
    ]):
        errors.append("zero_mutation")

    if data.get("required_exit_status") != EXIT:
        errors.append("exit_status")
    if data.get("downstream_handoff_requirements", {}).get("next_gate") != NEXT:
        errors.append("next_gate")

    return sorted(set(errors))


def main() -> int:
    errors = validate(load())
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
