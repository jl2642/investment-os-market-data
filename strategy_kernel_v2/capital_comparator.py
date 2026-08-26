"""Strategy Kernel v2 Phase 2A shadow capital comparator.

Research-only: never creates a user decision, order, target weight, Candidate mutation,
or economic writeback. READY_AFTER_REFRESH stays blocked until a governed overlay
explicitly satisfies every recorded refresh requirement. Material evidence gaps remain
blocked. Comparison is a transparent vector plus a Pareto frontier; no scalar policy
score is hard-coded before Phase 3 calibration.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Optional

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

_REQUIRED_VECTOR_FIELDS = {"confidence", "portfolio_concentration_cost", "execution_friction"}


def _validate_probability_scenarios(scenarios: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [dict(x) for x in scenarios]
    if len(rows) < 2:
        raise ValueError("comparison requires at least two explicit scenarios")
    total_p = 0.0
    for row in rows:
        if not {"name", "probability", "annualized_total_return"}.issubset(row):
            raise ValueError("scenario requires name, probability and annualized_total_return")
        p = float(row["probability"])
        r = float(row["annualized_total_return"])
        if p < 0.0 or p > 1.0:
            raise ValueError("scenario probability must be in [0,1]")
        row["probability"] = p
        row["annualized_total_return"] = r
        total_p += p
    if abs(total_p - 1.0) > 1e-9:
        raise ValueError("scenario probabilities must sum to 1")
    return rows


def gate_underwriting_object(obj: Mapping[str, Any], refresh: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    sid = obj["security_id"]
    readiness = obj["readiness"]
    state = readiness["comparison_readiness"]
    required = list(readiness.get("refresh_requirements", []))

    if state == "NOT_READY":
        return {"security_id": sid, "gate_state": "BLOCKED_MATERIAL_EVIDENCE", "eligible": False,
                "missing_requirements": required, "reason_codes": ["PHASE1C_NOT_READY", "MATERIAL_EVIDENCE_GAP"]}

    if state == "READY_NOW":
        scenarios = _validate_probability_scenarios(obj["valuation"].get("scenarios", []))
        vector_meta = obj.get("comparison_inputs") or {}
        missing_vector = sorted(_REQUIRED_VECTOR_FIELDS - set(vector_meta))
        if missing_vector:
            return {"security_id": sid, "gate_state": "BLOCKED_VECTOR_INPUT", "eligible": False,
                    "missing_requirements": missing_vector, "reason_codes": ["MISSING_EXPLICIT_COMPARISON_VECTOR_INPUT"]}
        return _eligible_gate(sid, obj, scenarios, vector_meta, "PHASE1C_READY_NOW")

    if state != "READY_AFTER_REFRESH":
        raise ValueError(f"unknown comparison_readiness: {state}")

    if not refresh:
        return {"security_id": sid, "gate_state": "BLOCKED_REFRESH_REQUIRED", "eligible": False,
                "missing_requirements": required, "reason_codes": ["GOVERNED_REFRESH_REQUIRED"]}
    if refresh.get("security_id") != sid:
        raise ValueError("refresh security_id mismatch")
    if refresh.get("governed") is not True:
        raise ValueError("Phase 2 refresh must be governed")
    if not refresh.get("as_of") or not refresh.get("provenance"):
        raise ValueError("governed refresh requires as_of and provenance")

    satisfied = set(refresh.get("satisfied_requirements", []))
    missing = [x for x in required if x not in satisfied]
    if missing:
        return {"security_id": sid, "gate_state": "BLOCKED_REFRESH_INCOMPLETE", "eligible": False,
                "missing_requirements": missing, "reason_codes": ["REFRESH_REQUIREMENTS_NOT_FULLY_SATISFIED"]}

    scenarios = _validate_probability_scenarios(refresh.get("valuation_scenarios", []))
    missing_vector = sorted(_REQUIRED_VECTOR_FIELDS - set(refresh))
    if missing_vector:
        return {"security_id": sid, "gate_state": "BLOCKED_VECTOR_INPUT", "eligible": False,
                "missing_requirements": missing_vector, "reason_codes": ["MISSING_EXPLICIT_COMPARISON_VECTOR_INPUT"]}
    return _eligible_gate(sid, obj, scenarios, refresh, "GOVERNED_REFRESH_SATISFIED")


def _eligible_gate(sid: str, obj: Mapping[str, Any], scenarios: List[Dict[str, Any]], meta: Mapping[str, Any], reason: str) -> Dict[str, Any]:
    confidence = float(meta["confidence"])
    concentration_cost = float(meta["portfolio_concentration_cost"])
    execution_friction = float(meta["execution_friction"])
    for value, name in [(confidence, "confidence"), (concentration_cost, "portfolio_concentration_cost"), (execution_friction, "execution_friction")]:
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{name} must be in [0,1]")
    expected = sum(x["probability"] * x["annualized_total_return"] for x in scenarios)
    worst = min(x["annualized_total_return"] for x in scenarios)
    probability_of_loss = sum(x["probability"] for x in scenarios if x["annualized_total_return"] < 0.0)
    return {
        "security_id": sid,
        "security_name": obj.get("security_name", sid),
        "gate_state": "ELIGIBLE_SHADOW_COMPARISON",
        "eligible": True,
        "reason_codes": [reason],
        "vector": {
            "expected_annualized_total_return": expected,
            "worst_scenario_annualized_total_return": worst,
            "probability_of_loss": probability_of_loss,
            "confidence": confidence,
            "portfolio_concentration_cost": concentration_cost,
            "execution_friction": execution_friction,
            "scenario_count": len(scenarios),
        },
        "scenarios": deepcopy(scenarios),
        "source_decision_readiness": obj["readiness"]["decision_readiness"],
    }


def make_cash_baseline(*, security_id: str, annualized_return: float, as_of: str, provenance: str, confidence: float = 1.0) -> Dict[str, Any]:
    if not provenance or not as_of:
        raise ValueError("cash baseline requires as_of and provenance")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be in [0,1]")
    r = float(annualized_return)
    return {
        "security_id": security_id, "security_name": security_id,
        "gate_state": "ELIGIBLE_SHADOW_COMPARISON", "eligible": True,
        "reason_codes": ["EXPLICIT_REFERENCE_BASELINE"],
        "vector": {"expected_annualized_total_return": r, "worst_scenario_annualized_total_return": r,
                   "probability_of_loss": 1.0 if r < 0.0 else 0.0, "confidence": float(confidence),
                   "portfolio_concentration_cost": 0.0, "execution_friction": 0.0, "scenario_count": 1},
        "scenarios": [{"name": "REFERENCE", "probability": 1.0, "annualized_total_return": r}],
        "source_decision_readiness": "REFERENCE_ONLY",
        "reference": {"as_of": as_of, "provenance": provenance},
    }


def _dominates(a: Mapping[str, float], b: Mapping[str, float]) -> bool:
    maximize = ("expected_annualized_total_return", "worst_scenario_annualized_total_return", "confidence")
    minimize = ("probability_of_loss", "portfolio_concentration_cost", "execution_friction")
    no_worse = all(a[k] >= b[k] for k in maximize) and all(a[k] <= b[k] for k in minimize)
    strictly_better = any(a[k] > b[k] for k in maximize) or any(a[k] < b[k] for k in minimize)
    return no_worse and strictly_better


def compare_capital_uses(gated_items: Iterable[Mapping[str, Any]], *, cash_baseline_id: Optional[str] = None) -> Dict[str, Any]:
    items = [deepcopy(dict(x)) for x in gated_items]
    eligible = [x for x in items if x.get("eligible") is True]
    blocked = [x for x in items if x.get("eligible") is not True]
    ids = [x["security_id"] for x in eligible]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate comparison security_id")

    frontier, dominated_by = [], {x["security_id"]: [] for x in eligible}
    for candidate in eligible:
        sid = candidate["security_id"]
        for other in eligible:
            if sid != other["security_id"] and _dominates(other["vector"], candidate["vector"]):
                dominated_by[sid].append(other["security_id"])
        if not dominated_by[sid]:
            frontier.append(sid)

    cash_vector = None
    if cash_baseline_id is not None:
        matches = [x for x in eligible if x["security_id"] == cash_baseline_id]
        if len(matches) != 1:
            raise ValueError("cash_baseline_id must identify exactly one eligible item")
        cash_vector = matches[0]["vector"]

    vectors = {}
    for item in eligible:
        sid = item["security_id"]
        vector = deepcopy(item["vector"])
        if cash_vector is not None:
            vector["excess_expected_return_vs_cash"] = vector["expected_annualized_total_return"] - cash_vector["expected_annualized_total_return"]
        vector["pareto_status"] = "FRONTIER" if sid in frontier else "DOMINATED"
        vector["dominated_by"] = sorted(dominated_by[sid])
        vectors[sid] = vector

    return {
        "schema_version": "1.0.0", "phase": "2A", "mode": "TRANSPARENT_VECTOR_PLUS_PARETO",
        "policy_score": None, "eligible_count": len(eligible), "blocked_count": len(blocked),
        "pareto_frontier": sorted(frontier), "vectors": vectors, "blocked": blocked,
        "user_decision_generated": False, "economic_preference_writeback": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
