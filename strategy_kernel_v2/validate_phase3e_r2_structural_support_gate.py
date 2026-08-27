from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3e_r2_structural_support_gate import (
    build_structural_support_gate,
    load_contract,
    validate_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def validate():
    errors = list(validate_program_consistency())
    contract = load_contract()
    errors.extend(validate_contract(contract))
    result = build_structural_support_gate()
    state = json.loads((ROOT / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))
    cv = current.get("validation", {})
    closeout = state.get("phase3e_r2_structural_support_gate_complete") is True

    if result.get("status") != contract["classification"]["pass_status"]:
        errors.append("R2E_SUPPORT_GATE_NOT_PASS")
    if result.get("phase3e_r2_structurally_supported") is not True:
        errors.append("R2E_SUPPORT_NOT_STRUCTURALLY_SUPPORTED")
    if result.get("phase3e_r2_robustness_execution_authorized") is not True:
        errors.append("R2E_SUPPORT_ROBUSTNESS_NOT_AUTHORIZED")
    if result.get("result_value_reads_for_gate_decision") != 0:
        errors.append("R2E_SUPPORT_RESULT_VALUE_READ_NONZERO")
    if result.get("post_result_numeric_thresholds_created") != 0:
        errors.append("R2E_SUPPORT_POST_RESULT_THRESHOLD_CREATED")
    if len(result.get("robustness_axis_feasibility", [])) != 5:
        errors.append("R2E_SUPPORT_AXIS_COUNT_DRIFT")
    if not all(row.get("structurally_evaluable") for row in result["robustness_axis_feasibility"]):
        errors.append("R2E_SUPPORT_AXIS_NOT_EVALUABLE")
    if result.get("planned_checkpoint_jackknife_count") != 13:
        errors.append("R2E_SUPPORT_CHECKPOINT_JACKKNIFE_COUNT_DRIFT")
    if result.get("planned_security_jackknife_count") != 7:
        errors.append("R2E_SUPPORT_SECURITY_JACKKNIFE_COUNT_DRIFT")
    if result.get("planned_signature_jackknife_count") != 2:
        errors.append("R2E_SUPPORT_SIGNATURE_JACKKNIFE_COUNT_DRIFT")
    if result.get("planned_horizon_strata_count") != 3:
        errors.append("R2E_SUPPORT_HORIZON_COUNT_DRIFT")
    if result.get("planned_aggregation_weighting_scheme_count") != 3:
        errors.append("R2E_SUPPORT_WEIGHTING_COUNT_DRIFT")
    for key in (
        "economic_performance_support_claimed",
        "model_robustness_claimed",
        "phase4_promotion_claimed",
        "phase3e_r2_state_closeout_applied",
        "phase3e_r2_started",
        "repeat_phase3f_started",
        "phase3_historical_validation_complete",
        "phase4_entry_allowed",
    ):
        if result.get(key) is not False:
            errors.append("R2E_SUPPORT_FORBIDDEN_FLAG:" + key)
    if result.get("integrity_errors"):
        errors.extend("R2E_SUPPORT_INTEGRITY:" + item for item in result["integrity_errors"])

    if closeout:
        expected = {
            "phase3e_r2_structural_support_gate_frozen": True,
            "phase3e_r2_structural_support_gate_complete": True,
            "phase3e_r2_structural_support_gate_status": result["status"],
            "phase3e_r2_structural_support_gate_sha256": result["gate_sha256"],
            "phase3e_r2_structurally_supported": True,
            "phase3e_r2_result_value_reads_for_support_gate": 0,
            "phase3e_r2_post_result_numeric_thresholds_created": 0,
            "phase3e_r2_robustness_plan_frozen": True,
            "phase3e_r2_robustness_axis_count": 5,
            "phase3e_r2_checkpoint_jackknife_planned_count": 13,
            "phase3e_r2_security_jackknife_planned_count": 7,
            "phase3e_r2_signature_jackknife_planned_count": 2,
            "phase3e_r2_horizon_strata_planned_count": 3,
            "phase3e_r2_aggregation_weighting_scheme_count": 3,
            "phase3e_r2_start_allowed": True,
            "phase3e_r2_robustness_execution_start_allowed": True,
            "phase3e_r2_started": False,
            "phase3e_r2_robustness_started": False,
            "phase3e_r2_complete": False,
            "repeat_phase3f_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                errors.append("R2E_SUPPORT_CLOSEOUT_STATE_DRIFT:" + key)
            if cv.get(key) != value:
                errors.append("R2E_SUPPORT_CLOSEOUT_CURRENT_DRIFT:" + key)
        if current.get("status") != "PHASE3E_R2_STRUCTURAL_SUPPORT_PASS_ROBUSTNESS_READY_PHASE4_BLOCKED":
            errors.append("R2E_SUPPORT_CLOSEOUT_STATUS_DRIFT")
        if current.get("next_phase") != "PHASE_3E_R2_ROBUSTNESS_EXECUTION":
            errors.append("R2E_SUPPORT_CLOSEOUT_NEXT_DRIFT")

    controls = result["controls"]
    for key, value in controls.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2E_SUPPORT_TRADE_AUTHORITY_CHANGED")
        elif value != 0:
            errors.append("R2E_SUPPORT_AUTHORITY_NONZERO:" + key)

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3E_R2_STRUCTURAL_SUPPORT_ACCEPTANCE "
        f"status={result['status']} supported=true axes=5/5 "
        f"gate_sha256={result['gate_sha256']} "
        "result_value_reads=0 phase3e_started=false repeat_phase3f_started=false "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
