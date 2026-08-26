"""Strategy Kernel v2 Phase 3B competing model forms.

Shadow/research-only. Every model consumes the same immutable shared observation
packet. Missing model-specific inputs fail closed; no model may fetch additional
evidence, infer retrospective probabilities, create target weights, generate a
user decision, or authorize a trade.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any, Mapping

from strategy_kernel_v2.capital_comparator import compare_capital_uses

MODEL_ORDER = (
    "LEGACY_POLICY_BASELINE",
    "PHASE2_PROBABILISTIC_VECTOR",
    "SIMPLE_NON_PROBABILISTIC_PARETO",
)

FALSE_CONTROLS = {
    "hindsight_allowed": False,
    "model_specific_evidence_fetch_allowed": False,
    "retrospective_probability_backfill_allowed": False,
    "retrospective_scenario_backfill_allowed": False,
    "scalar_policy_score_allowed": False,
    "target_weight_generation_allowed": False,
    "candidate_mutation_allowed": False,
    "real_position_mutation_allowed": False,
    "simulation_position_mutation_allowed": False,
    "target_portfolio_writeback_allowed": False,
    "user_decision_generation_allowed": False,
    "investment_recommendation_generation_allowed": False,
    "order_authorized": False,
    "orders": 0,
    "trade_authority": "NONE",
}

SIMPLE_MAXIMIZE = ("return_proxy", "downside_resilience", "evidence_quality")
SIMPLE_MINIMIZE = ("concentration_cost", "execution_friction")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field}_MUST_BE_FINITE_NUMBER")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field}_MUST_BE_FINITE_NUMBER")
    return number


def _validate_observation_provenance(
    observation: Mapping[str, Any],
    *,
    selected_evidence_ids: set[str],
) -> None:
    provenance = observation.get("provenance_evidence_ids")
    if not isinstance(provenance, list) or not provenance:
        raise ValueError("STRUCTURED_OBSERVATION_PROVENANCE_REQUIRED")
    if len(provenance) != len(set(provenance)):
        raise ValueError("DUPLICATE_OBSERVATION_PROVENANCE")
    outside = sorted(set(provenance) - selected_evidence_ids)
    if outside:
        raise ValueError("OBSERVATION_USES_EVIDENCE_OUTSIDE_SHARED_PACKET:" + ",".join(outside))


def build_shared_observation_packet(
    snapshot: Mapping[str, Any],
    *,
    structured_observations: Mapping[str, Mapping[str, Any]] | None = None,
    reference_asset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one immutable input surface shared by all competing model forms."""
    required = {
        "decision_point_id",
        "at",
        "opportunity_security_ids",
        "selected_evidence_ids",
        "selected_evidence",
        "unavailable_required_evidence_keys",
    }
    missing = sorted(required - set(snapshot))
    if missing:
        raise ValueError("SNAPSHOT_FIELD_REQUIRED:" + ",".join(missing))

    opportunity_ids = list(snapshot["opportunity_security_ids"])
    if len(opportunity_ids) != len(set(opportunity_ids)):
        raise ValueError("DUPLICATE_OPPORTUNITY_SECURITY_ID")

    selected_ids = list(snapshot["selected_evidence_ids"])
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("DUPLICATE_SELECTED_EVIDENCE_ID")
    selected_records = list(snapshot["selected_evidence"])
    record_ids = [row.get("evidence_id") for row in selected_records]
    if sorted(record_ids) != sorted(selected_ids):
        raise ValueError("SELECTED_EVIDENCE_ID_RECORD_MISMATCH")
    selected_id_set = set(selected_ids)

    observations = {
        str(security_id): deepcopy(dict(value))
        for security_id, value in (structured_observations or {}).items()
    }
    unknown = sorted(set(observations) - set(opportunity_ids))
    if unknown:
        raise ValueError("OBSERVATION_SECURITY_OUTSIDE_OPPORTUNITY_SET:" + ",".join(unknown))
    for observation in observations.values():
        _validate_observation_provenance(observation, selected_evidence_ids=selected_id_set)

    reference = deepcopy(dict(reference_asset)) if reference_asset is not None else None
    if reference is not None:
        if not reference.get("security_id") or not reference.get("as_of"):
            raise ValueError("REFERENCE_ASSET_ID_AND_AS_OF_REQUIRED")
        _validate_observation_provenance(reference, selected_evidence_ids=selected_id_set)

    body = {
        "schema_version": "1.0.0",
        "phase": "3B",
        "mode": "SHARED_OBSERVATION_PACKET",
        "source_phase3a_decision_point_id": snapshot["decision_point_id"],
        "at": snapshot["at"],
        "opportunity_security_ids": sorted(opportunity_ids),
        "selected_evidence_ids": sorted(selected_ids),
        "selected_evidence": deepcopy(selected_records),
        "unavailable_required_evidence_keys": sorted(snapshot["unavailable_required_evidence_keys"]),
        "structured_observations": observations,
        "reference_asset": reference,
        "controls": deepcopy(FALSE_CONTROLS),
    }
    body["input_packet_sha256"] = _sha256(body)
    return body


def _base_model_output(packet: Mapping[str, Any], model_form: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "phase": "3B",
        "model_form": model_form,
        "input_packet_sha256": packet["input_packet_sha256"],
        "at": packet["at"],
        "opportunity_security_ids": list(packet["opportunity_security_ids"]),
        "reference_asset": deepcopy(packet.get("reference_asset")),
        "policy_score": None,
        "target_weights": None,
        "decision_replay_generated": False,
        "investment_recommendation_generated": False,
        "user_decision_generated": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }


def run_legacy_policy_baseline(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Passthrough only contemporaneously structured Legacy dispositions."""
    rows = []
    for security_id in packet["opportunity_security_ids"]:
        observation = packet["structured_observations"].get(security_id, {})
        disposition = observation.get("legacy_disposition")
        if not isinstance(disposition, str) or not disposition:
            rows.append({
                "security_id": security_id,
                "status": "NOT_EVALUABLE",
                "reason_codes": ["CONTEMPORANEOUS_LEGACY_DISPOSITION_NOT_STRUCTURED"],
            })
            continue
        reason_codes = observation.get("legacy_reason_codes", [])
        if not isinstance(reason_codes, list):
            raise ValueError("LEGACY_REASON_CODES_MUST_BE_LIST")
        rows.append({
            "security_id": security_id,
            "status": "EVALUABLE",
            "legacy_disposition": disposition,
            "reason_codes": list(reason_codes),
            "provenance_evidence_ids": list(observation["provenance_evidence_ids"]),
        })
    out = _base_model_output(packet, "LEGACY_POLICY_BASELINE")
    out.update({
        "model_family": "RULE_AND_STATE_PASSTHROUGH",
        "ranking_generated": False,
        "rows": rows,
        "evaluable_count": sum(row["status"] == "EVALUABLE" for row in rows),
    })
    return out


def _phase2_vector_from_observation(
    security_id: str,
    observation: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    raw = observation.get("phase2_inputs")
    if not isinstance(raw, Mapping):
        return None, ["PHASE2_INPUTS_NOT_CONTEMPORANEOUSLY_STRUCTURED"]
    required = {
        "valuation_scenarios",
        "confidence",
        "portfolio_concentration_cost",
        "execution_friction",
    }
    missing = sorted(required - set(raw))
    if missing:
        return None, ["MISSING_EXPLICIT_PHASE2_INPUT:" + field for field in missing]

    scenarios = [dict(row) for row in raw["valuation_scenarios"]]
    if len(scenarios) < 2:
        raise ValueError("PHASE2_REQUIRES_AT_LEAST_TWO_EXPLICIT_SCENARIOS")
    total_probability = 0.0
    expected = 0.0
    probability_of_loss = 0.0
    returns = []
    normalized = []
    for row in scenarios:
        if not {"name", "probability", "annualized_total_return"} <= set(row):
            raise ValueError("PHASE2_SCENARIO_FIELDS_REQUIRED")
        probability = _finite_number(row["probability"], "SCENARIO_PROBABILITY")
        annualized_return = _finite_number(row["annualized_total_return"], "SCENARIO_ANNUALIZED_TOTAL_RETURN")
        if probability < 0.0 or probability > 1.0:
            raise ValueError("SCENARIO_PROBABILITY_OUT_OF_RANGE")
        total_probability += probability
        expected += probability * annualized_return
        if annualized_return < 0.0:
            probability_of_loss += probability
        returns.append(annualized_return)
        normalized.append({
            "name": str(row["name"]),
            "probability": probability,
            "annualized_total_return": annualized_return,
        })
    if abs(total_probability - 1.0) > 1e-9:
        raise ValueError("PHASE2_SCENARIO_PROBABILITIES_MUST_SUM_TO_ONE")

    confidence = _finite_number(raw["confidence"], "CONFIDENCE")
    concentration = _finite_number(raw["portfolio_concentration_cost"], "PORTFOLIO_CONCENTRATION_COST")
    friction = _finite_number(raw["execution_friction"], "EXECUTION_FRICTION")
    for value, name in (
        (confidence, "CONFIDENCE"),
        (concentration, "PORTFOLIO_CONCENTRATION_COST"),
        (friction, "EXECUTION_FRICTION"),
    ):
        if value < 0.0 or value > 1.0:
            raise ValueError(name + "_OUT_OF_RANGE")

    return {
        "security_id": security_id,
        "security_name": observation.get("security_name", security_id),
        "gate_state": "ELIGIBLE_SHADOW_COMPARISON",
        "eligible": True,
        "reason_codes": ["EXPLICIT_CONTEMPORANEOUS_PHASE3B_OBSERVATION"],
        "vector": {
            "expected_annualized_total_return": expected,
            "worst_scenario_annualized_total_return": min(returns),
            "probability_of_loss": probability_of_loss,
            "confidence": confidence,
            "portfolio_concentration_cost": concentration,
            "execution_friction": friction,
            "scenario_count": len(normalized),
        },
        "scenarios": normalized,
        "source_decision_readiness": "HISTORICAL_REPLAY_INPUT_ONLY",
    }, []


def run_phase2_probabilistic_vector(packet: Mapping[str, Any]) -> dict[str, Any]:
    gated_items = []
    blocked = []
    for security_id in packet["opportunity_security_ids"]:
        observation = packet["structured_observations"].get(security_id, {})
        item, reasons = _phase2_vector_from_observation(security_id, observation)
        if item is None:
            blocked.append({"security_id": security_id, "status": "NOT_EVALUABLE", "reason_codes": reasons})
        else:
            gated_items.append(item)

    comparison = compare_capital_uses(gated_items)
    out = _base_model_output(packet, "PHASE2_PROBABILISTIC_VECTOR")
    out.update({
        "model_family": "PROBABILITY_WEIGHTED_VECTOR_PLUS_PARETO",
        "rows": {security_id: deepcopy(vector) for security_id, vector in comparison["vectors"].items()},
        "pareto_frontier": list(comparison["pareto_frontier"]),
        "blocked": blocked,
        "evaluable_count": len(gated_items),
        "ranking_generated": False,
    })
    return out


def _simple_dominates(a: Mapping[str, float], b: Mapping[str, float]) -> bool:
    no_worse = (
        all(a[key] >= b[key] for key in SIMPLE_MAXIMIZE)
        and all(a[key] <= b[key] for key in SIMPLE_MINIMIZE)
    )
    strictly_better = (
        any(a[key] > b[key] for key in SIMPLE_MAXIMIZE)
        or any(a[key] < b[key] for key in SIMPLE_MINIMIZE)
    )
    return no_worse and strictly_better


def run_simple_non_probabilistic_pareto(packet: Mapping[str, Any]) -> dict[str, Any]:
    vectors: dict[str, dict[str, float]] = {}
    blocked = []
    required = set(SIMPLE_MAXIMIZE + SIMPLE_MINIMIZE)
    for security_id in packet["opportunity_security_ids"]:
        observation = packet["structured_observations"].get(security_id, {})
        raw = observation.get("simple_pareto_inputs")
        if not isinstance(raw, Mapping):
            blocked.append({
                "security_id": security_id,
                "status": "NOT_EVALUABLE",
                "reason_codes": ["SIMPLE_PARETO_INPUTS_NOT_CONTEMPORANEOUSLY_STRUCTURED"],
            })
            continue
        missing = sorted(required - set(raw))
        if missing:
            blocked.append({
                "security_id": security_id,
                "status": "NOT_EVALUABLE",
                "reason_codes": ["MISSING_EXPLICIT_SIMPLE_INPUT:" + field for field in missing],
            })
            continue
        vectors[security_id] = {field: _finite_number(raw[field], field.upper()) for field in required}

    dominated_by = {security_id: [] for security_id in vectors}
    for security_id, vector in vectors.items():
        for other_id, other_vector in vectors.items():
            if security_id != other_id and _simple_dominates(other_vector, vector):
                dominated_by[security_id].append(other_id)

    frontier = sorted(security_id for security_id, dominators in dominated_by.items() if not dominators)
    rows = {}
    for security_id, vector in vectors.items():
        row = deepcopy(vector)
        row["pareto_status"] = "FRONTIER" if security_id in frontier else "DOMINATED"
        row["dominated_by"] = sorted(dominated_by[security_id])
        rows[security_id] = row

    out = _base_model_output(packet, "SIMPLE_NON_PROBABILISTIC_PARETO")
    out.update({
        "model_family": "NON_PROBABILISTIC_TRANSPARENT_PARETO",
        "dimension_contract": {"maximize": list(SIMPLE_MAXIMIZE), "minimize": list(SIMPLE_MINIMIZE)},
        "probability_inputs_used": False,
        "rows": rows,
        "pareto_frontier": frontier,
        "blocked": blocked,
        "evaluable_count": len(vectors),
        "ranking_generated": False,
    })
    return out


def run_competing_model_suite(packet: Mapping[str, Any]) -> dict[str, Any]:
    outputs = [
        run_legacy_policy_baseline(packet),
        run_phase2_probabilistic_vector(packet),
        run_simple_non_probabilistic_pareto(packet),
    ]
    fingerprints = {row["input_packet_sha256"] for row in outputs}
    if fingerprints != {packet["input_packet_sha256"]}:
        raise AssertionError("MODEL_INPUT_IDENTITY_BROKEN")
    return {
        "schema_version": "1.0.0",
        "phase": "3B",
        "mode": "COMPETING_MODEL_FORMS",
        "input_packet_sha256": packet["input_packet_sha256"],
        "model_order": list(MODEL_ORDER),
        "models": outputs,
        "model_specific_evidence_fetches": 0,
        "decision_replay_generated": False,
        "investment_recommendation_generated": False,
        "user_decision_generated": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
