from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3d_r2_performance_measurement import (
    build_performance_measurement,
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

    state = json.loads((ROOT / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    current = json.loads((ROOT / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))
    cv = current.get("validation", {})

    if state.get("phase3d_r2_outcome_evidence_acquisition_complete") is not True:
        errors.append("R2_PERF_OUTCOME_EVIDENCE_NOT_COMPLETE")
    if state.get("phase3d_r2_performance_start_allowed") is not True:
        errors.append("R2_PERF_START_NOT_ALLOWED")
    closeout = state.get("phase3d_r2_performance_measurement_complete") is True
    if closeout:
        if state.get("phase3d_r2_performance_started") is not True:
            errors.append("R2_PERF_CLOSEOUT_NOT_STARTED")
        expected_next = (
            "PHASE_3E_R2_ROBUSTNESS_EXECUTION"
            if state.get("phase3e_r2_structural_support_gate_complete") is True
            else "PHASE_3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT"
        )
        if current.get("next_phase") != expected_next:
            errors.append("R2_PERF_CLOSEOUT_NEXT_PHASE_DRIFT")
        if cv.get("phase3d_r2_performance_started") is not True:
            errors.append("R2_PERF_CURRENT_CLOSEOUT_NOT_STARTED")
    else:
        if state.get("phase3d_r2_performance_started") is not False:
            errors.append("R2_PERF_PRE_RESULT_STATE_ALREADY_STARTED")
        if current.get("next_phase") != "PHASE_3D_R2_PERFORMANCE_MEASUREMENT":
            errors.append("R2_PERF_CURRENT_NEXT_PHASE_DRIFT")
        if cv.get("phase3d_r2_performance_started") is not False:
            errors.append("R2_PERF_CURRENT_PRE_RESULT_STARTED")
    if cv.get("phase3d_r2_performance_start_allowed") is not True:
        errors.append("R2_PERF_CURRENT_START_NOT_ALLOWED")

    result = build_performance_measurement()
    if result.get("status") != contract["classification"]["complete_status"]:
        errors.append("R2_PERF_MEASUREMENT_NOT_COMPLETE")
    if result.get("endpoint_return_record_count") != 165:
        errors.append("R2_PERF_ENDPOINT_RECORD_COUNT_DRIFT")
    if result.get("edge_horizon_record_count") != 162:
        errors.append("R2_PERF_EDGE_HORIZON_RECORD_COUNT_DRIFT")
    if result.get("endpoint_return_calculation_count") != 165:
        errors.append("R2_PERF_ENDPOINT_CALC_COUNT_DRIFT")
    if result.get("edge_spread_calculation_count") != 162:
        errors.append("R2_PERF_SPREAD_CALC_COUNT_DRIFT")
    if result.get("concordance_calculation_count") != 162:
        errors.append("R2_PERF_CONCORDANCE_CALC_COUNT_DRIFT")
    if set(result.get("horizon_summary", {})) != {"1", "3", "5"}:
        errors.append("R2_PERF_HORIZON_SUMMARY_DRIFT")
    for horizon in ("1", "3", "5"):
        if result["horizon_summary"][horizon].get("edge_count") != 54:
            errors.append("R2_PERF_HORIZON_EDGE_COUNT_DRIFT:" + horizon)

    for key in (
        "statistical_significance_claimed",
        "confidence_interval_computed",
        "p_value_computed",
        "portfolio_pnl_computed",
        "sharpe_computed",
        "scalar_model_score_computed",
        "global_winner_selected",
        "phase3e_r2_support_threshold_defined",
        "phase3e_r2_support_decision_made",
        "phase3e_r2_start_authorized",
        "phase3d_r2_state_closeout_applied",
        "phase3e_r2_started",
        "repeat_phase3f_started",
        "phase3_historical_validation_complete",
        "phase4_entry_allowed",
    ):
        if result.get(key) is not False:
            errors.append("R2_PERF_FORBIDDEN_RESULT_FLAG:" + key)

    controls = result["controls"]
    for key, value in controls.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2_PERF_TRADE_AUTHORITY_CHANGED")
        elif value != 0:
            errors.append("R2_PERF_AUTHORITY_NONZERO:" + key)

    if result.get("integrity_errors"):
        errors.extend("R2_PERF_INTEGRITY:" + item for item in result["integrity_errors"])

    if closeout:
        expected = {
            "phase3d_r2_performance_measurement_status": result["status"],
            "phase3d_r2_performance_measurement_sha256": result["measurement_sha256"],
            "phase3d_r2_endpoint_return_record_count": 165,
            "phase3d_r2_edge_horizon_record_count": 162,
            "phase3d_r2_edge_checkpoint_count": 13,
            "phase3d_r2_edge_signature_count": 2,
            "phase3d_r2_h1_concordant_edge_count": 34,
            "phase3d_r2_h1_concordance_rate": "0.629629629630",
            "phase3d_r2_h1_mean_edge_return_spread": "0.000276359547",
            "phase3d_r2_h3_concordant_edge_count": 29,
            "phase3d_r2_h3_concordance_rate": "0.537037037037",
            "phase3d_r2_h3_mean_edge_return_spread": "0.001040897221",
            "phase3d_r2_h5_concordant_edge_count": 27,
            "phase3d_r2_h5_concordance_rate": "0.500000000000",
            "phase3d_r2_h5_mean_edge_return_spread": "-0.000638182257",
            "phase3d_r2_pooled_concordant_edge_horizon_count": 90,
            "phase3d_r2_pooled_concordance_rate": "0.555555555556",
            "phase3d_r2_pooled_mean_edge_return_spread": "0.000226358170",
            "phase3d_r2_performance_descriptive_only": True,
            "phase3d_r2_statistical_significance_claimed": False,
            "phase3d_r2_phase3e_support_decision_made": False,
            "phase3d_r2_complete": True,
            "phase3e_r2_structural_support_gate_required": True,
            "phase3e_r2_structural_support_gate_frozen": state.get("phase3e_r2_structural_support_gate_complete") is True,
            "phase3e_r2_start_allowed": state.get("phase3e_r2_structural_support_gate_complete") is True,
            "phase3e_r2_started": False,
            "repeat_phase3f_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                errors.append("R2_PERF_CLOSEOUT_STATE_DRIFT:" + key)
            if cv.get(key) != value:
                errors.append("R2_PERF_CLOSEOUT_CURRENT_DRIFT:" + key)
        expected_status = (
            "PHASE3E_R2_STRUCTURAL_SUPPORT_PASS_ROBUSTNESS_READY_PHASE4_BLOCKED"
            if state.get("phase3e_r2_structural_support_gate_complete") is True
            else "PHASE3D_R2_PERFORMANCE_COMPLETE_3E_SUPPORT_GATE_REQUIRED_PHASE4_BLOCKED"
        )
        if current.get("status") != expected_status:
            errors.append("R2_PERF_CLOSEOUT_STATUS_DRIFT")

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3D_R2_PERFORMANCE_ACCEPTANCE "
        f"status={result['status']} endpoints=165/165 edge_horizons=162/162 "
        f"measurement_sha256={result['measurement_sha256']} "
        "phase3e_support_decision=false phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
