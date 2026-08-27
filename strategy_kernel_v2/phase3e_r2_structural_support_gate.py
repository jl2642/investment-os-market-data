"""Phase 3E-R2 result-value-blind structural support gate.

This gate decides only whether accepted R2 historical evidence is structurally
complete and multi-level enough to execute a predeclared robustness program.
It deliberately does not read endpoint returns, edge spreads, concordance rates,
or horizon performance ordering.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT.json"
STATE_FILE = ROOT / "PROGRAM_STATE.json"
CURRENT_FILE = ROOT / "CURRENT_PHASE_STATUS.json"
PERFORMANCE_CONTRACT_FILE = ROOT / "PHASE3D_R2_PERFORMANCE_MEASUREMENT_CONTRACT.json"
FROZEN_EVIDENCE_FILE = ROOT / "PHASE3D_R2_OUTCOME_EVIDENCE_FROZEN_COMPACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3E_R2_STRUCTURAL_SUPPORT_GATE.json"

CONTROLS = {
    "model_mutations": 0,
    "transform_mutations": 0,
    "comparison_signature_mutations": 0,
    "holdout_population_mutations": 0,
    "dominance_relation_mutations": 0,
    "outcome_value_reads_for_gate_decision": 0,
    "outcome_refetches": 0,
    "candidate_membership_mutations": 0,
    "real_account_mutations": 0,
    "simulation_mutations": 0,
    "target_portfolio_writebacks": 0,
    "investment_recommendations_generated": 0,
    "orders": 0,
    "trade_authority": "NONE",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_contract() -> dict[str, Any]:
    return _load(CONTRACT_FILE)


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_RESULT_VALUE_BLIND_BEFORE_R2_ROBUSTNESS_EXECUTION":
        errors.append("R2E_SUPPORT_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_phase3d_r2", {})
    expected = {
        "final_head": "fdd638bd100ee6ecf60eac938e852b00052c0e33",
        "measurement_status": "COMPLETE_R2_DETERMINISTIC_PERFORMANCE_MEASUREMENT_DESCRIPTIVE_ONLY",
        "measurement_sha256": "a3e474745dc8074be363f3d9b8e7082923bd67adeff6c6e42431e1f6a406edad",
        "outcome_evidence_status": "PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE",
        "outcome_evidence_ledger_sha256": "300db34b408e7ca2cfeb188b8c6177b62bdff70743a2cf6fb2c833bf3bda1d1b",
        "frozen_dominance_edge_count": 54,
        "checkpoint_security_endpoint_instances": 55,
        "endpoint_return_record_count": 165,
        "edge_horizon_record_count": 162,
        "edge_bearing_checkpoint_count": 13,
        "exact_signature_count": 2,
        "fixed_horizon_sessions": [1, 3, 5],
    }
    for key, value in expected.items():
        if parent.get(key) != value:
            errors.append("R2E_SUPPORT_PARENT_CONTRACT_DRIFT:" + key)

    firewall = contract.get("result_value_firewall", {})
    for key in (
        "concordance_rates_may_be_read_by_gate",
        "edge_spread_values_may_be_read_by_gate",
        "endpoint_return_values_may_be_read_by_gate",
        "horizon_performance_ordering_may_be_read_by_gate",
        "post_result_numeric_threshold_may_be_created",
        "winner_or_promotion_decision_may_be_made",
    ):
        if firewall.get(key) is not False:
            errors.append("R2E_SUPPORT_RESULT_VALUE_FIREWALL_OPEN:" + key)

    criteria = contract.get("structural_support_criteria", {})
    if criteria.get("minimum_distinct_levels_per_robustness_axis") != 2:
        errors.append("R2E_SUPPORT_MIN_LEVEL_DRIFT")
    if criteria.get("all_required_axes_must_be_structurally_evaluable") is not True:
        errors.append("R2E_SUPPORT_AXIS_REQUIREMENT_WEAKENED")

    plan = contract.get("predefined_robustness_plan", {})
    if plan.get("one_axis_at_a_time") is not True:
        errors.append("R2E_SUPPORT_ONE_AXIS_RULE_FALSE")
    for key in (
        "simultaneous_multi_axis_search_allowed",
        "result_driven_subset_selection_allowed",
        "model_or_transform_mutation_allowed",
        "dominance_relation_recomputation_allowed",
        "outcome_refetch_allowed",
        "outcome_value_mutation_allowed",
    ):
        if plan.get(key) is not False:
            errors.append("R2E_SUPPORT_PLAN_FIREWALL_OPEN:" + key)
    tests = plan.get("tests", [])
    expected_ids = {
        "R2E_HORIZON_STRATIFICATION",
        "R2E_CHECKPOINT_JACKKNIFE",
        "R2E_SECURITY_JACKKNIFE",
        "R2E_SIGNATURE_STRATIFICATION_AND_JACKKNIFE",
        "R2E_AGGREGATION_WEIGHTING_SENSITIVITY",
    }
    if {row.get("test_id") for row in tests} != expected_ids:
        errors.append("R2E_SUPPORT_TEST_PLAN_DRIFT")

    auth = contract.get("authority_boundaries", {})
    for key, value in auth.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2E_SUPPORT_TRADE_AUTHORITY_DRIFT")
        elif value != 0:
            errors.append("R2E_SUPPORT_AUTHORITY_NONZERO:" + key)
    return errors


def build_structural_support_gate() -> dict[str, Any]:
    contract = load_contract()
    errors = validate_contract(contract)
    state = _load(STATE_FILE)
    current = _load(CURRENT_FILE)
    perf_contract = _load(PERFORMANCE_CONTRACT_FILE)
    evidence = _load(FROZEN_EVIDENCE_FILE)

    parent_errors: list[str] = []
    if state.get("phase3d_r2_complete") is not True:
        parent_errors.append("PHASE3D_R2_NOT_COMPLETE")
    if state.get("phase3d_r2_performance_measurement_complete") is not True:
        parent_errors.append("R2_PERFORMANCE_MEASUREMENT_NOT_COMPLETE")
    if state.get("phase3d_r2_performance_measurement_status") != contract["parent_phase3d_r2"]["measurement_status"]:
        parent_errors.append("R2_PERFORMANCE_STATUS_DRIFT")
    if state.get("phase3d_r2_performance_measurement_sha256") != contract["parent_phase3d_r2"]["measurement_sha256"]:
        parent_errors.append("R2_PERFORMANCE_SHA_DRIFT")
    if state.get("phase3d_r2_endpoint_return_record_count") != 165:
        parent_errors.append("R2_ENDPOINT_RECORD_COUNT_DRIFT")
    if state.get("phase3d_r2_edge_horizon_record_count") != 162:
        parent_errors.append("R2_EDGE_HORIZON_RECORD_COUNT_DRIFT")
    if state.get("phase3d_r2_edge_checkpoint_count") != 13:
        parent_errors.append("R2_EDGE_CHECKPOINT_COUNT_DRIFT")
    if state.get("phase3d_r2_edge_signature_count") != 2:
        parent_errors.append("R2_SIGNATURE_COUNT_DRIFT")
    if state.get("phase3d_r2_performance_descriptive_only") is not True:
        parent_errors.append("R2_PERFORMANCE_NOT_DESCRIPTIVE_ONLY")
    if state.get("phase3d_r2_statistical_significance_claimed") is not False:
        parent_errors.append("R2_STATISTICAL_SIGNIFICANCE_ALREADY_CLAIMED")
    if state.get("phase3d_r2_phase3e_support_decision_made") is not False:
        parent_errors.append("R2_SUPPORT_DECISION_ALREADY_MADE")
    if state.get("phase3e_r2_started") is not False:
        parent_errors.append("PHASE3E_R2_ALREADY_STARTED")
    expected_next = (
        "PHASE_3E_R2_ROBUSTNESS_EXECUTION"
        if state.get("phase3e_r2_structural_support_gate_complete") is True
        else "PHASE_3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT"
    )
    if current.get("next_phase") != expected_next:
        parent_errors.append("R2E_SUPPORT_CURRENT_NEXT_PHASE_DRIFT")

    measurement_population = perf_contract.get("measurement_population", {})
    if measurement_population.get("expected_endpoint_return_records") != 165:
        parent_errors.append("R2E_SUPPORT_PERF_CONTRACT_ENDPOINT_DRIFT")
    if measurement_population.get("expected_edge_horizon_records") != 162:
        parent_errors.append("R2E_SUPPORT_PERF_CONTRACT_EDGE_DRIFT")
    if measurement_population.get("fixed_horizon_sessions") != [1, 3, 5]:
        parent_errors.append("R2E_SUPPORT_PERF_CONTRACT_HORIZON_DRIFT")

    if evidence.get("frozen_dominance_edge_count") != 54:
        parent_errors.append("R2E_SUPPORT_EVIDENCE_EDGE_DRIFT")
    if evidence.get("required_edge_endpoint_instances") != 55:
        parent_errors.append("R2E_SUPPORT_EVIDENCE_ENDPOINT_DRIFT")
    if evidence.get("complete_evidence_edge_count") != 54:
        parent_errors.append("R2E_SUPPORT_EVIDENCE_NOT_COMPLETE")
    security_count = len(evidence.get("security_evidence", {}))
    if security_count != 7:
        parent_errors.append("R2E_SUPPORT_SECURITY_COUNT_DRIFT")

    levels = {
        "HORIZON_STRATIFICATION": len(measurement_population.get("fixed_horizon_sessions", [])),
        "CHECKPOINT_JACKKNIFE": int(state.get("phase3d_r2_edge_checkpoint_count", 0)),
        "SECURITY_JACKKNIFE": security_count,
        "SIGNATURE_STRATIFICATION_AND_JACKKNIFE": int(state.get("phase3d_r2_edge_signature_count", 0)),
        "AGGREGATION_WEIGHTING_SENSITIVITY": 3,
    }
    min_levels = int(contract["structural_support_criteria"]["minimum_distinct_levels_per_robustness_axis"])
    axis_rows = [
        {
            "axis": axis,
            "distinct_structural_levels": count,
            "minimum_required": min_levels,
            "structurally_evaluable": count >= min_levels,
        }
        for axis, count in levels.items()
    ]
    all_axes = all(row["structurally_evaluable"] for row in axis_rows)

    all_errors = sorted(set(errors + parent_errors))
    if all_errors:
        status = contract["classification"]["fail_status"]
        supported = False
    elif not all_axes:
        status = contract["classification"]["partial_status"]
        supported = False
    else:
        status = contract["classification"]["pass_status"]
        supported = True

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3E_R2",
        "round": "R0_STRUCTURAL_SUPPORT_GATE",
        "status": status,
        "parent_phase3d_r2_complete": state.get("phase3d_r2_complete"),
        "parent_measurement_sha256": state.get("phase3d_r2_performance_measurement_sha256"),
        "parent_measurement_record_counts": {
            "endpoint_returns": state.get("phase3d_r2_endpoint_return_record_count"),
            "edge_horizons": state.get("phase3d_r2_edge_horizon_record_count"),
        },
        "frozen_population_counts": {
            "dominance_edges": evidence.get("frozen_dominance_edge_count"),
            "endpoint_instances": evidence.get("required_edge_endpoint_instances"),
            "endpoint_securities": security_count,
            "edge_bearing_checkpoints": state.get("phase3d_r2_edge_checkpoint_count"),
            "exact_signatures": state.get("phase3d_r2_edge_signature_count"),
            "fixed_horizons": len(measurement_population.get("fixed_horizon_sessions", [])),
        },
        "robustness_axis_feasibility": axis_rows,
        "planned_checkpoint_jackknife_count": int(state.get("phase3d_r2_edge_checkpoint_count", 0)),
        "planned_security_jackknife_count": security_count,
        "planned_signature_jackknife_count": int(state.get("phase3d_r2_edge_signature_count", 0)),
        "planned_horizon_strata_count": len(measurement_population.get("fixed_horizon_sessions", [])),
        "planned_aggregation_weighting_scheme_count": 3,
        "phase3e_r2_structurally_supported": supported,
        "phase3e_r2_robustness_execution_authorized": supported,
        "economic_performance_support_claimed": False,
        "model_robustness_claimed": False,
        "phase4_promotion_claimed": False,
        "result_value_reads_for_gate_decision": 0,
        "post_result_numeric_thresholds_created": 0,
        "integrity_errors": all_errors,
        "controls": dict(CONTROLS),
        "phase3e_r2_state_closeout_applied": False,
        "phase3e_r2_started": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    result["gate_sha256"] = _sha256({k: v for k, v in result.items() if k != "gate_sha256"})
    return result


def write_default(result: Mapping[str, Any]) -> Path:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUTPUT_FILE


if __name__ == "__main__":
    result = build_structural_support_gate()
    path = write_default(result)
    print(
        "PHASE3E_R2_STRUCTURAL_SUPPORT_GATE "
        f"status={result['status']} supported={str(result['phase3e_r2_structurally_supported']).lower()} "
        f"axes={sum(x['structurally_evaluable'] for x in result['robustness_axis_feasibility'])}/5 "
        f"result_value_reads={result['result_value_reads_for_gate_decision']} "
        "phase3e_started=false repeat_phase3f_started=false phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE "
        f"sha256={result['gate_sha256']} path={path}"
    )
