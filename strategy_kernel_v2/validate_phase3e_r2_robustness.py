from __future__ import annotations

from strategy_kernel_v2.phase3e_r2_robustness import (
    build_robustness_results,
    load_contract,
    validate_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency


def validate():
    errors = list(validate_program_consistency())
    contract = load_contract()
    errors.extend(validate_contract(contract))
    result = build_robustness_results()

    if result.get("status") != contract["completion_rule"]["status"]:
        errors.append("R2E_ROBUSTNESS_NOT_COMPLETE")
    if result.get("completed_test_count") != 5:
        errors.append("R2E_ROBUSTNESS_TEST_COUNT_DRIFT")
    if result.get("checkpoint_jackknife_count") != 13:
        errors.append("R2E_ROBUSTNESS_CHECKPOINT_JACKKNIFE_DRIFT")
    if result.get("security_jackknife_count") != 7:
        errors.append("R2E_ROBUSTNESS_SECURITY_JACKKNIFE_DRIFT")
    if result.get("signature_strata_count") != 2 or result.get("signature_jackknife_count") != 2:
        errors.append("R2E_ROBUSTNESS_SIGNATURE_COUNT_DRIFT")
    if result.get("aggregation_scheme_horizon_record_count") != 9:
        errors.append("R2E_ROBUSTNESS_WEIGHTING_COUNT_DRIFT")
    if set(result.get("horizon_stratification", {})) != {"1", "3", "5"}:
        errors.append("R2E_ROBUSTNESS_HORIZON_STRATA_DRIFT")
    for horizon in ("1", "3", "5"):
        if result["horizon_stratification"][horizon].get("distinct_edge_count") != 54:
            errors.append("R2E_ROBUSTNESS_BASELINE_EDGE_COUNT:" + horizon)

    for key in (
        "robustness_pass_fail_threshold_defined",
        "positive_robustness_claimed",
        "economic_winner_selected",
        "statistical_significance_claimed",
        "confidence_interval_computed",
        "p_value_computed",
        "repeat_phase3f_start_authorized_by_candidate",
        "phase4_promotion_claimed",
        "phase3e_r2_state_closeout_applied",
        "phase3e_r2_started",
        "phase3e_r2_complete",
        "repeat_phase3f_started",
        "phase3_historical_validation_complete",
        "phase4_entry_allowed",
    ):
        if result.get(key) is not False:
            errors.append("R2E_ROBUSTNESS_FORBIDDEN_FLAG:" + key)

    if result.get("phase3e_r2_completion_is_evidence_completion_only") is not True:
        errors.append("R2E_ROBUSTNESS_COMPLETION_BOUNDARY_DRIFT")
    if result.get("integrity_errors"):
        errors.extend("R2E_ROBUSTNESS_INTEGRITY:" + item for item in result["integrity_errors"])

    from pathlib import Path
    import json
    root = Path(__file__).resolve().parent
    state = json.loads((root / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    current = json.loads((root / "CURRENT_PHASE_STATUS.json").read_text(encoding="utf-8"))
    cv = current.get("validation", {})
    closeout = state.get("phase3e_r2_complete") is True
    if closeout:
        expected = {
            "phase3e_r2_started": True,
            "phase3e_r2_robustness_started": True,
            "phase3e_r2_robustness_complete": True,
            "phase3e_r2_complete": True,
            "phase3e_r2_robustness_status": result["status"],
            "phase3e_r2_robustness_sha256": result["robustness_sha256"],
            "phase3e_r2_robustness_test_count": 5,
            "phase3e_r2_checkpoint_jackknife_count": 13,
            "phase3e_r2_security_jackknife_count": 7,
            "phase3e_r2_signature_strata_count": 2,
            "phase3e_r2_signature_jackknife_count": 2,
            "phase3e_r2_aggregation_scheme_horizon_record_count": 9,
            "phase3e_r2_robustness_evaluation_accepted": True,
            "phase3e_r2_positive_robustness_claimed": False,
            "phase3e_r2_statistical_significance_claimed": False,
            "phase3e_r2_robustness_pass_fail_threshold_defined": False,
            "phase3e_r2_robustness_completion_evidence_only": True,
            "repeat_phase3f_start_allowed": True,
            "repeat_phase3f_started": False,
            "repeat_phase3f_complete": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                errors.append("R2E_ROBUSTNESS_CLOSEOUT_STATE_DRIFT:" + key)
            if cv.get(key) != value:
                errors.append("R2E_ROBUSTNESS_CLOSEOUT_CURRENT_DRIFT:" + key)
        if current.get("current_phase") != "PHASE_3E_R2_ROBUSTNESS_EXECUTION":
            errors.append("R2E_ROBUSTNESS_CLOSEOUT_CURRENT_PHASE_DRIFT")
        if current.get("status") != "PHASE3E_R2_COMPLETE_REPEAT_PHASE3F_REQUIRED_PHASE4_BLOCKED":
            errors.append("R2E_ROBUSTNESS_CLOSEOUT_STATUS_DRIFT")
        if current.get("next_phase") != "REPEAT_PHASE_3F_HISTORICAL_PROMOTION_GATE":
            errors.append("R2E_ROBUSTNESS_CLOSEOUT_NEXT_DRIFT")

    controls = result["controls"]
    for key, value in controls.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2E_ROBUSTNESS_TRADE_AUTHORITY_CHANGED")
        elif value != 0:
            errors.append("R2E_ROBUSTNESS_AUTHORITY_NONZERO:" + key)

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3E_R2_ROBUSTNESS_ACCEPTANCE "
        f"status={result['status']} tests=5/5 "
        f"robustness_sha256={result['robustness_sha256']} "
        "positive_robustness_claim=false repeat_phase3f_started=false "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
