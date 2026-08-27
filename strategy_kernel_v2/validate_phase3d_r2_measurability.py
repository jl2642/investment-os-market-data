from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

from strategy_kernel_v2.phase3d_r2_measurability import (
    build_measurability_audit,
    load_contract,
    validate_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3_r2_independent_holdout_replay import validate as validate_holdout


def validate():
    errors = list(validate_program_consistency())
    holdout_errors, holdout = validate_holdout()
    errors.extend(holdout_errors)

    contract = load_contract()
    errors.extend(validate_contract(contract))
    first = build_measurability_audit()
    second = build_measurability_audit()

    if first != second or first.get("audit_sha256") != second.get("audit_sha256"):
        errors.append("R2_3D_MEASURABILITY_NONDETERMINISTIC")
    if first.get("parent_holdout_replay_sha256") != holdout.get("replay_sha256"):
        errors.append("R2_3D_PARENT_HOLDOUT_BINDING_DRIFT")
    if first.get("checkpoint_count") != 14:
        errors.append("R2_3D_CHECKPOINT_COUNT_DRIFT")
    if first.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_3D_EDGE_COUNT_DRIFT")
    if first.get("structurally_measurable") is not True:
        errors.append("R2_3D_EXPECTED_STRUCTURAL_RELATION_MISSING")

    statuses = contract["round1_classification"]
    if first.get("audit_errors"):
        expected = statuses["fail_status"]
    elif not first.get("structurally_measurable"):
        expected = statuses["not_measurable_status"]
    elif first.get("complete_outcome_evidence_ready"):
        expected = statuses["pass_status"]
    else:
        expected = statuses["partial_status"]
    if first.get("status") != expected:
        errors.append("R2_3D_MEASURABILITY_STATUS_CLASSIFICATION_DRIFT")

    if first.get("performance_calculation_authorized") is not first.get("complete_outcome_evidence_ready"):
        errors.append("R2_3D_PERFORMANCE_GATE_DRIFT")
    if first.get("complete_evidence_edge_count", 0) > first.get("frozen_dominance_edge_count", 0):
        errors.append("R2_3D_COMPLETE_EDGE_COUNT_INVALID")

    state = json.loads((ROOT / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))
    cv = current.get("validation", {})
    evidence_complete = state.get("phase3d_r2_outcome_evidence_acquisition_complete") is True
    if state.get("phase3d_r2_round1_complete") is True:
        expected_state = {
            "phase3d_r2_started": True,
            "phase3d_r2_measurability_contract_frozen": True,
            "phase3d_r2_round1_complete": True,
            "phase3d_r2_round1_status": first["status"],
            "phase3d_r2_round1_audit_sha256": first["audit_sha256"],
            "phase3d_r2_structurally_measurable": first["structurally_measurable"],
            "phase3d_r2_frozen_dominance_edges": first["frozen_dominance_edge_count"],
            "phase3d_r2_required_edge_endpoint_instances": first["required_edge_endpoint_instances"],
            "phase3d_r2_required_edge_endpoint_security_count": first["required_edge_endpoint_security_count"],
            "phase3d_r2_preexisting_price_security_count": first["preexisting_price_observation_security_count"],
            "phase3d_r2_missing_price_security_count": first["missing_any_price_observation_security_count"],
            "phase3d_r2_exchange_session_ready_security_count": first["exchange_session_schedule_ready_security_count"],
            "phase3d_r2_corporate_action_ready_security_count": first["corporate_action_status_ready_security_count"],
            "phase3d_r2_complete_evidence_edge_count": first["complete_evidence_edge_count"],
            "phase3d_r2_outcome_evidence_acquisition_required": not evidence_complete,
            "phase3d_r2_outcome_evidence_acquisition_start_allowed": True,
            "phase3d_r2_performance_start_allowed": evidence_complete,
            "phase3d_r2_performance_started": False,
            "phase3d_r2_complete": False,
            "phase3e_r2_started": False,
            "repeat_phase3f_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, expected in expected_state.items():
            if state.get(key) != expected:
                errors.append("R2_3D_STATE_CLOSEOUT_DRIFT:" + key)
            if key in cv and cv.get(key) != expected:
                errors.append("R2_3D_CURRENT_CLOSEOUT_DRIFT:" + key)
        if current.get("current_phase") != "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED":
            errors.append("R2_3D_CURRENT_PHASE_DRIFT")
        expected_next = (
            "PHASE_3D_R2_PERFORMANCE_MEASUREMENT"
            if evidence_complete
            else "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION"
        )
        if current.get("next_phase") != expected_next:
            errors.append("R2_3D_NEXT_PHASE_DRIFT")
        if first["status"] != "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED":
            errors.append("R2_3D_CLOSEOUT_ONLY_SUPPORTS_OBSERVED_PARTIAL")

    controls = first["controls"]
    for key in (
        "return_calculation_count",
        "performance_metric_count",
        "portfolio_pnl_count",
        "regret_metric_count",
        "calibration_metric_count",
        "model_mutation_count",
        "holdout_population_mutation_count",
        "dominance_relation_mutation_count",
        "result_based_drop_count",
        "external_outcome_fetch_count",
        "orders",
    ):
        if controls.get(key) != 0:
            errors.append("R2_3D_FORBIDDEN_ACTIVITY_NONZERO:" + key)
    if controls.get("trade_authority") != "NONE":
        errors.append("R2_3D_TRADE_AUTHORITY_CHANGED")

    if first.get("phase3d_r2_governed_state_started") is not False:
        errors.append("R2_3D_ROUND1_PREMATURE_STATE_START")
    if first.get("phase3d_r2_performance_started") is not False:
        errors.append("R2_3D_ROUND1_PREMATURE_PERFORMANCE")
    if first.get("phase3e_r2_started") is not False:
        errors.append("R2_3D_ROUND1_PREMATURE_3E")
    if first.get("repeat_phase3f_started") is not False:
        errors.append("R2_3D_ROUND1_PREMATURE_REPEAT_3F")
    if first.get("phase4_entry_allowed") is not False:
        errors.append("R2_3D_ROUND1_PREMATURE_PHASE4")

    if not errors:
        write_default(first)
    return errors, first


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3D_R2_MEASURABILITY_ACCEPTANCE "
        f"status={result['status']} edges={result['frozen_dominance_edge_count']} "
        f"endpoint_securities={result['required_edge_endpoint_security_count']} "
        f"price_securities={result['preexisting_price_observation_security_count']} "
        f"complete_edges={result['complete_evidence_edge_count']} "
        f"performance_authorized={str(result['performance_calculation_authorized']).lower()} "
        "returns=0 performance=0 phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
