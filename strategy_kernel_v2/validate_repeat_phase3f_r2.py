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
