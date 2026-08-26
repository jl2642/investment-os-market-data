"""Phase 2B governed refresh adapters for Strategy Kernel v2.

Pure shadow transformation. A refresh packet can update comparison evidence only when
its provenance and requirement coverage are explicit. It never changes Canonical state,
decision authority, Candidate membership, portfolio quantities/costs, target weights or orders.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, Mapping

from .capital_comparator import _validate_probability_scenarios

_ALLOWED_CLASSES = {
    "PRICE_MARK", "FX", "VALUATION", "FUNDAMENTAL_REUNDERWRITE",
    "PORTFOLIO_CONTEXT", "EXECUTION_FEASIBILITY", "GOVERNANCE_CHECK",
}
_VECTOR_FIELDS = ("confidence", "portfolio_concentration_cost", "execution_friction")


def _validate_packet(packet: Mapping[str, Any]) -> Dict[str, Any]:
    p = deepcopy(dict(packet))
    required = {"schema_version", "security_id", "as_of", "governed", "provenance",
                "evidence_classes", "satisfied_requirements", "resolved_evidence_gaps",
                "valuation_scenarios", "comparison_inputs"}
    missing = sorted(required - set(p))
    if missing:
        raise ValueError(f"missing refresh packet fields: {missing}")
    if p["schema_version"] != "1.0.0":
        raise ValueError("unsupported refresh packet schema")
    if p["governed"] is not True:
        raise ValueError("refresh packet must be governed")
    if not p["as_of"]:
        raise ValueError("refresh packet requires as_of")
    provenance = p["provenance"]
    if not isinstance(provenance, list) or not provenance:
        raise ValueError("refresh packet requires non-empty provenance")
    for row in provenance:
        if not isinstance(row, dict) or not row.get("source_type") or not row.get("locator"):
            raise ValueError("each provenance row requires source_type and locator")
    classes = set(p["evidence_classes"])
    unknown = sorted(classes - _ALLOWED_CLASSES)
    if unknown:
        raise ValueError(f"unknown evidence_classes: {unknown}")
    ci = p["comparison_inputs"]
    missing_vector = [x for x in _VECTOR_FIELDS if x not in ci]
    if missing_vector:
        raise ValueError(f"missing comparison inputs: {missing_vector}")
    for name in _VECTOR_FIELDS:
        value = float(ci[name])
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{name} must be in [0,1]")
        ci[name] = value
    p["valuation_scenarios"] = _validate_probability_scenarios(p["valuation_scenarios"])
    p["evidence_classes"] = sorted(classes)
    p["satisfied_requirements"] = list(dict.fromkeys(p["satisfied_requirements"]))
    p["resolved_evidence_gaps"] = list(dict.fromkeys(p["resolved_evidence_gaps"]))
    return p


def apply_governed_refresh(obj: Mapping[str, Any], packet: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a refreshed shadow copy or an explicit blocked result.

    `decision_readiness` and all authority controls are preserved verbatim.
    """
    original = deepcopy(dict(obj))
    p = _validate_packet(packet)
    sid = original["security_id"]
    if p["security_id"] != sid:
        raise ValueError("refresh security_id mismatch")

    readiness = original["readiness"]
    state = readiness["comparison_readiness"]
    required_refresh = list(readiness.get("refresh_requirements", []))
    evidence_gaps = list(original.get("research_quality", {}).get("evidence_gaps", []))
    missing_refresh = [x for x in required_refresh if x not in set(p["satisfied_requirements"])]
    missing_gaps = [x for x in evidence_gaps if x not in set(p["resolved_evidence_gaps"])]

    if state == "NOT_READY":
        if "FUNDAMENTAL_REUNDERWRITE" not in set(p["evidence_classes"]):
            return _blocked(sid, "BLOCKED_MATERIAL_EVIDENCE_PRICE_OR_VALUATION_ONLY",
                            missing_refresh or required_refresh,
                            ["PHASE1C_NOT_READY", "FUNDAMENTAL_REUNDERWRITE_REQUIRED"])
        if missing_refresh or missing_gaps:
            return _blocked(sid, "BLOCKED_MATERIAL_EVIDENCE_INCOMPLETE",
                            missing_refresh + missing_gaps,
                            ["MATERIAL_EVIDENCE_GAPS_NOT_FULLY_RESOLVED"])
    elif state == "READY_AFTER_REFRESH":
        if missing_refresh:
            return _blocked(sid, "BLOCKED_REFRESH_INCOMPLETE", missing_refresh,
                            ["REFRESH_REQUIREMENTS_NOT_FULLY_SATISFIED"])
    elif state != "READY_NOW":
        raise ValueError(f"unknown comparison_readiness: {state}")

    refreshed = deepcopy(original)
    refreshed["valuation"] = deepcopy(refreshed["valuation"])
    refreshed["valuation"]["scenarios"] = deepcopy(p["valuation_scenarios"])
    if refreshed["valuation"].get("status") in {"UNAVAILABLE", "PARTIAL", "AVAILABLE_STALE"}:
        refreshed["valuation"]["status"] = "AVAILABLE"
    refreshed["comparison_inputs"] = deepcopy(p["comparison_inputs"])
    refreshed["readiness"] = deepcopy(refreshed["readiness"])
    refreshed["readiness"]["comparison_readiness"] = "READY_NOW"
    refreshed["phase2b_refresh"] = {
        "as_of": p["as_of"], "governed": True,
        "provenance": deepcopy(p["provenance"]),
        "evidence_classes": deepcopy(p["evidence_classes"]),
        "satisfied_requirements": deepcopy(p["satisfied_requirements"]),
        "resolved_evidence_gaps": deepcopy(p["resolved_evidence_gaps"]),
        "source_comparison_readiness": state,
        "source_decision_readiness": original["readiness"]["decision_readiness"],
        "comparison_only": True, "canonical_state_mutated": False,
    }
    if refreshed.get("controls") != original.get("controls"):
        raise ValueError("refresh may not change authority controls")
    if refreshed["readiness"]["decision_readiness"] != original["readiness"]["decision_readiness"]:
        raise ValueError("refresh may not change decision readiness")
    if sid == "601138.SH" and refreshed.get("portfolio_context", {}).get("canonical_action") != "HOLD_600_SHARES_NO_ADD_NO_TRADE":
        raise ValueError("601138 no-trade action must be preserved")
    if sid == "HKEX:00669":
        if refreshed.get("portfolio_context", {}).get("canonical_action") != "WATCH_NO_TRADE_WAIT_FOR_PRICE_OR_POSITION_SIZING_GATE":
            raise ValueError("00669 no-trade monitoring action must be preserved")
        if refreshed.get("valuation", {}).get("price_bands_are_research_gates") is not True:
            raise ValueError("00669 price bands must remain research gates")
    if sid == "605090.SH" and refreshed.get("portfolio_context", {}).get("concentration_is_automatic_sell_signal") is not False:
        raise ValueError("605090 concentration may not become automatic sell signal")
    return {"security_id": sid, "refresh_state": "READY_FOR_SHADOW_COMPARISON",
            "eligible_for_comparator": True, "refreshed_object": refreshed,
            "user_decision_generated": False, "economic_mutation": False,
            "orders": 0, "trade_authority": "NONE"}


def _blocked(sid: str, state: str, missing: list[str], reasons: list[str]) -> Dict[str, Any]:
    return {"security_id": sid, "refresh_state": state, "eligible_for_comparator": False,
            "missing_requirements": list(dict.fromkeys(missing)), "reason_codes": reasons,
            "user_decision_generated": False, "economic_mutation": False,
            "orders": 0, "trade_authority": "NONE"}
