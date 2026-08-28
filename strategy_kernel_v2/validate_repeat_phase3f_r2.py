from __future__ import annotations

from strategy_kernel_v2.repeat_phase3f_r2_promotion_gate import (
    _load,
    ADAPTER_FILE,
    ORIGINAL_CONTRACT_FILE,
    evaluate_repeat_phase3f,
    validate_adapter,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency


def validate():
    errors = list(validate_program_consistency())
    adapter = _load(ADAPTER_FILE)
    original = _load(ORIGINAL_CONTRACT_FILE)
    errors.extend(validate_adapter(adapter, original))
    result = evaluate_repeat_phase3f()

    if result.get("status") != "COMPLETE_REPEAT_PHASE3F_R2_HISTORICAL_PROMOTION_GATE":
        errors.append("REPEAT3F_RESULT_NOT_COMPLETE")
    if result.get("promotion_requirement_total_count") != 4:
        errors.append("REPEAT3F_REQUIREMENT_TOTAL_DRIFT")
    expected_keys = {
        "candidate_point_in_time_historical_replay",
        "candidate_phase3d_evidence_measurable",
        "phase3e_robustness_accepted",
        "broader_historical_coverage",
    }
    if set(result.get("requirements", {})) != expected_keys:
        errors.append("REPEAT3F_REQUIREMENT_SET_DRIFT")
    if result.get("integrity_errors"):
        errors.extend("REPEAT3F_INTEGRITY:" + item for item in result["integrity_errors"])

    # The inherited contract, not a newly invented threshold, determines the outcome.
    expected_all_pass = all(row["passed"] for row in result["requirements"].values())
    if result.get("all_promotion_requirements_pass") is not expected_all_pass:
        errors.append("REPEAT3F_ALL_PASS_LOGIC_DRIFT")
    expected_outcome = (
        "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION"
        if expected_all_pass
        else (
            "REJECT_V2_FORM"
            if result.get("terminal_rejection_evidence")
            else "CONTINUE_SHADOW_RESEARCH"
        )
    )
    if result.get("gate_outcome") != expected_outcome:
        errors.append("REPEAT3F_OUTCOME_LOGIC_DRIFT")
    if result.get("phase4_entry_authorized_by_gate_result") is not (expected_outcome == "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION"):
        errors.append("REPEAT3F_PHASE4_GATE_LOGIC_DRIFT")

    if result.get("robustness_sensitivity_carry_forward_required") is not True:
        errors.append("REPEAT3F_SENSITIVITY_NOT_CARRIED_FORWARD")
    for key in (
        "economic_winner_selected",
        "statistical_significance_claimed",
        "post_result_promotion_threshold_created",
        "state_closeout_applied",
        "repeat_phase3f_started",
        "repeat_phase3f_complete",
        "phase3_historical_validation_complete",
        "phase4_started",
    ):
        if result.get(key) is not False:
            errors.append("REPEAT3F_FORBIDDEN_CANDIDATE_FLAG:" + key)
    if result.get("orders") != 0 or result.get("trade_authority") != "NONE":
        errors.append("REPEAT3F_AUTHORITY_DRIFT")

    state = _load(ADAPTER_FILE.parent / "PROGRAM_STATE.json")
    current = _load(ADAPTER_FILE.parent / "CURRENT_PHASE_STATUS.json")
    cv = current.get("validation", {})
    if state.get("repeat_phase3f_complete") is True:
        expected = {
            "repeat_phase3f_started": True,
            "repeat_phase3f_complete": True,
            "repeat_phase3f_status": "COMPLETE_REPEAT_PHASE3F_R2_HISTORICAL_PROMOTION_GATE",
            "repeat_phase3f_promotion_requirement_pass_count": 4,
            "repeat_phase3f_promotion_requirement_total_count": 4,
            "repeat_phase3f_all_promotion_requirements_pass": True,
            "repeat_phase3f_promotion_eligible": True,
            "repeat_phase3f_terminal_rejection_evidence": False,
            "repeat_phase3f_gate_outcome": "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION",
            "repeat_phase3f_gate_sha256": result["repeat_phase3f_gate_sha256"],
            "repeat_phase3f_post_result_promotion_threshold_created": False,
            "repeat_phase3f_robustness_sensitivity_carry_forward_required": True,
            "phase3_historical_validation_complete": True,
            "phase4_entry_allowed": True,
            "phase4_start_allowed": True,
            "phase4_forward_validation_complete": False,
        }
        for key, value in expected.items():
            if state.get(key) != value:
                errors.append("REPEAT3F_CLOSEOUT_STATE_DRIFT:" + key)
            if cv.get(key) != value:
                errors.append("REPEAT3F_CLOSEOUT_CURRENT_DRIFT:" + key)

        a1_supersedes_repeat3f_current = (
            state.get("program_amendment_a1_frozen") is True
            and state.get("phase4_v1_forward_execution_superseded_before_first_observation") is True
            and state.get("phase4_effective_execution_hold") is True
            and state.get("phase4_effective_forward_observation_start_allowed") is False
            and state.get("phase4_forward_observation_count") == 0
            and state.get("phase4_realized_outcome_read_count") == 0
        )
        if a1_supersedes_repeat3f_current:
            if state.get("phase4_started") is not True:
                errors.append("REPEAT3F_A1_PHASE4_NOT_ACTIVE")
            # The validation snapshot remains the immutable closeout record.
            if cv.get("phase4_started") is not False:
                errors.append("REPEAT3F_CLOSEOUT_CURRENT_DRIFT:phase4_started")
        else:
            if state.get("phase4_started") is not False:
                errors.append("REPEAT3F_CLOSEOUT_STATE_DRIFT:phase4_started")
            if current.get("current_phase") != "REPEAT_PHASE_3F_HISTORICAL_PROMOTION_GATE":
                errors.append("REPEAT3F_CLOSEOUT_CURRENT_PHASE_DRIFT")
            if current.get("status") != "REPEAT_PHASE3F_4_OF_4_PASS_PHASE4_FORWARD_VALIDATION_AUTHORIZED_NOT_STARTED":
                errors.append("REPEAT3F_CLOSEOUT_STATUS_DRIFT")
            if current.get("next_phase") != "PHASE_4_FORWARD_PARALLEL_SHADOW_VALIDATION":
                errors.append("REPEAT3F_CLOSEOUT_NEXT_DRIFT")

    if not errors:
        write_default(result)
    return errors, result


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "REPEAT_PHASE3F_R2_ACCEPTANCE "
        f"pass={result['promotion_requirement_pass_count']}/4 "
        f"outcome={result['gate_outcome']} "
        f"phase4_gate={str(result['phase4_entry_authorized_by_gate_result']).lower()} "
        "state_closeout=false phase4_started=false orders=0 trade_authority=NONE "
        f"sha256={result['repeat_phase3f_gate_sha256']}"
    )
