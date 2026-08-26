"""Pure shadow-only underwriting extraction.

Transforms explicit, already-reviewed extraction specifications into Underwriting
Object v1. It never fetches data, invents missing facts, or grants authority.
"""
from copy import deepcopy

CANONICAL_MAIN_SHA = "5c5df9082688f65332c79fef3b9cbfa893a06908"
FALSE_CONTROLS = {
    "candidate_membership_change_authorized": False,
    "real_position_change_authorized": False,
    "simulation_position_change_authorized": False,
    "target_portfolio_writeback_authorized": False,
    "order_authorized": False,
    "implementation_ready": False,
    "orders": 0,
    "trade_authority": "NONE",
}

def extract_underwriting(spec: dict) -> dict:
    required = {"security_id","security_name","source_paths","underwriting","valuation","portfolio_context","research_quality","readiness"}
    missing = sorted(required - set(spec))
    if missing:
        raise ValueError(f"missing extraction spec fields: {missing}")
    obj = {
        "schema_version":"1.0.0",
        "security_id":spec["security_id"],
        "security_name":spec["security_name"],
        "provenance":{"canonical_main_sha":CANONICAL_MAIN_SHA,"source_paths":list(spec["source_paths"])},
        "underwriting":deepcopy(spec["underwriting"]),
        "valuation":deepcopy(spec["valuation"]),
        "portfolio_context":deepcopy(spec["portfolio_context"]),
        "research_quality":deepcopy(spec["research_quality"]),
        "readiness":deepcopy(spec["readiness"]),
        "controls":deepcopy(FALSE_CONTROLS),
    }
    obj["valuation"].setdefault("scenarios", [])
    obj["valuation"]["research_triggers_are_orders"] = False
    _validate_semantics(obj)
    return obj

def _validate_semantics(obj: dict) -> None:
    if obj["controls"] != FALSE_CONTROLS:
        raise ValueError("authority controls may not be relaxed in Phase 1C")
    if obj["readiness"]["decision_readiness"] == "EVIDENCE_GAP" and obj["readiness"]["comparison_readiness"] != "NOT_READY":
        raise ValueError("material evidence gap cannot be shadow-comparison ready")
    if obj["valuation"]["status"] == "UNAVAILABLE" and obj["valuation"].get("scenarios"):
        raise ValueError("valuation scenarios cannot exist when valuation is unavailable")
    if obj["security_id"] == "HKEX:00669" and obj["valuation"].get("price_bands_are_research_gates") is not True:
        raise ValueError("00669 price bands must remain research gates")
    if obj["security_id"] == "601138.SH" and obj["portfolio_context"].get("canonical_action") != "HOLD_600_SHARES_NO_ADD_NO_TRADE":
        raise ValueError("601138 accepted no-trade action must be preserved")
    if obj["security_id"] == "605090.SH" and obj["portfolio_context"].get("concentration_is_automatic_sell_signal") is not False:
        raise ValueError("605090 concentration may not become an automatic sell signal")
