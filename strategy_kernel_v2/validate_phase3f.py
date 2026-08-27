from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.historical_promotion_gate import evaluate_phase3f
from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _validate_post3f(errors: list[str], state: dict, current: dict) -> None:
    decision_path = ROOT / "PHASE3_POST3F_RESEARCH_PATH_DECISION.json"
    if not decision_path.exists():
        errors.append("POST3F_CURRENT_WITHOUT_DECISION_ARTIFACT")
        return
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("status") != "APPROVED_GOVERNED_DUAL_TRACK_RESEARCH_LOOPBACK":
        errors.append("POST3F_DECISION_NOT_GOVERNED")
    if decision.get("trigger", {}).get("phase3f_gate_outcome") != "CONTINUE_SHADOW_RESEARCH":
        errors.append("POST3F_DECISION_PHASE3F_OUTCOME_DRIFT")
    if current["validation"].get("post3f_research_path_decision_complete") is not True:
        errors.append("POST3F_CURRENT_DECISION_NOT_COMPLETE")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("POST3F_PREMATURE_PHASE4")


def validate() -> list[str]:
    errors = list(validate_program_consistency())
    result = evaluate_phase3f()
    validation = load("PHASE3F_VALIDATION.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    contract = load("PHASE3F_PROMOTION_GATE_CONTRACT.json")

    if contract.get("status") != "FROZEN_HISTORICAL_PROMOTION_GATE":
        errors.append("PHASE3F_CONTRACT_NOT_FROZEN")

    if result["promotion_requirement_total_count"] != 4:
        errors.append("PHASE3F_REQUIREMENT_COUNT_MISMATCH")
    if result["promotion_requirement_pass_count"] != 1:
        errors.append("PHASE3F_PASS_COUNT_MISMATCH")

    expected_vector = {
        "candidate_point_in_time_historical_replay": False,
        "candidate_phase3d_evidence_measurable": False,
        "phase3e_robustness_accepted": True,
        "broader_historical_coverage": False,
    }
    for key, expected in expected_vector.items():
        if result["requirements"][key]["passed"] is not expected:
            errors.append("PHASE3F_REQUIREMENT_VECTOR_MISMATCH_" + key)

    if result["all_promotion_requirements_pass"] is not False:
        errors.append("PHASE3F_PREMATURE_PROMOTION")
    if result["terminal_rejection_evidence"] is not False:
        errors.append("PHASE3F_UNSUPPORTED_TERMINAL_REJECTION")
    if result["gate_outcome"] != "CONTINUE_SHADOW_RESEARCH":
        errors.append("PHASE3F_GATE_OUTCOME_MISMATCH")
    if result["current_fixed_candidate_forms_status"] != "NOT_PROMOTABLE_IN_CURRENT_FORM":
        errors.append("PHASE3F_FIXED_FORM_STATUS_MISMATCH")
    if result["economic_rejection_conclusion_available"] is not False:
        errors.append("PHASE3F_UNSUPPORTED_ECONOMIC_REJECTION")
    if result["governed_redesign_path_exists"] is not True:
        errors.append("PHASE3F_REDESIGN_PATH_MISSING")
    if result["adjacent_context_count"] <= 0:
        errors.append("PHASE3F_ADJACENT_CONTEXT_MISSING")

    if validation.get("status") != "PASS_COMPLETE_HISTORICAL_PROMOTION_GATE_CONTINUE_SHADOW_RESEARCH":
        errors.append("PHASE3F_VALIDATION_STATUS_MISMATCH")
    if validation.get("gate_outcome") != result["gate_outcome"]:
        errors.append("PHASE3F_VALIDATION_OUTCOME_DRIFT")
    if validation.get("promotion_requirement_pass_count") != 1 or validation.get("promotion_requirement_total_count") != 4:
        errors.append("PHASE3F_VALIDATION_REQUIREMENT_COUNT_DRIFT")
    if validation.get("promotion_eligible") is not False or validation.get("phase4_entry_allowed") is not False:
        errors.append("PHASE3F_VALIDATION_PREMATURE_PHASE4")
    if validation.get("terminal_rejection_evidence") is not False:
        errors.append("PHASE3F_VALIDATION_TERMINAL_REJECTION_DRIFT")

    if state.get("phase3f_started") is not True or state.get("phase3f_complete") is not True:
        errors.append("PHASE3F_STATE_NOT_COMPLETE")
    if state.get("phase3f_gate_outcome") != "CONTINUE_SHADOW_RESEARCH":
        errors.append("PHASE3F_STATE_OUTCOME_MISMATCH")
    if state.get("phase3f_promotion_eligible") is not False:
        errors.append("PHASE3F_STATE_PREMATURE_PROMOTION")
    if state.get("phase3f_terminal_rejection_evidence") is not False:
        errors.append("PHASE3F_STATE_TERMINAL_REJECTION_DRIFT")
    if state.get("phase3_historical_validation_complete") is not False:
        errors.append("PHASE3_PREMATURE_COMPLETE")
    if state.get("phase4_entry_allowed") is not False or state.get("phase4_forward_validation_complete") is not False:
        errors.append("PHASE4_PREMATURE_ENTRY")
    if state.get("phase5_migration_allowed") is not False:
        errors.append("PHASE5_PREMATURE_ENTRY")
    if state.get("phase3f_material_revision_loopback") != "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY":
        errors.append("PHASE3F_STATE_LOOPBACK_MISMATCH")

    cv = current["validation"]
    current_phase = current.get("current_phase")
    if current_phase == "PHASE_3F_HISTORICAL_PROMOTION_GATE":
        pass
    elif current_phase == "POST_PHASE3F_RESEARCH_PATH_DECISION":
        _validate_post3f(errors, state, current)
        if state.get("r2_phase3b_contract_definition_started"):
            errors.append("POST3F_VALIDATOR_SEES_R2_ALREADY_STARTED")
    elif current_phase in {"PHASE_3B_R2_REVISED_MODEL_CONTRACT", "PHASE_3C_R2_POINT_IN_TIME_REPLAY", "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED", "PHASE_3E_R2_ROBUSTNESS_EXECUTION"}:
        _validate_post3f(errors, state, current)
        r2_path = ROOT / "PHASE3B_R2_MODEL_CONTRACT.json"
        if not r2_path.exists():
            errors.append("PHASE3F_R2_DOWNSTREAM_WITHOUT_CONTRACT")
        else:
            r2 = json.loads(r2_path.read_text(encoding="utf-8"))
            if r2.get("status") != "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY":
                errors.append("PHASE3F_R2_DOWNSTREAM_CONTRACT_NOT_FROZEN")
            if r2.get("model", {}).get("new_identity") is not True or r2.get("model", {}).get("overwrites_prior_model") is not False:
                errors.append("PHASE3F_R2_DOWNSTREAM_IDENTITY_GUARD_BROKEN")
            if r2.get("phase_boundary", {}).get("phase4_entry_allowed") is not False:
                errors.append("PHASE3F_R2_DOWNSTREAM_PREMATURE_PHASE4")
        if state.get("r2_phase3b_contract_definition_started") is not True or state.get("r2_phase3b_contract_definition_complete") is not True:
            errors.append("PHASE3F_R2_DOWNSTREAM_NOT_COMPLETE")
        r2b_downstream = current_phase in {"PHASE_3C_R2_POINT_IN_TIME_REPLAY", "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED", "PHASE_3E_R2_ROBUSTNESS_EXECUTION"}
        holdout_h1_downstream = current_phase in {"INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED", "PHASE_3E_R2_ROBUSTNESS_EXECUTION"}
        holdout_replay_downstream = state.get("independent_holdout_replay_complete") is True
        if r2b_downstream:
            if state.get("r2_phase3c_r2b_complete") is not True:
                errors.append("PHASE3F_R2B_DOWNSTREAM_NOT_COMPLETE")
            if state.get("r2_real_historical_replay_executed") is not True or state.get("r2_phase3c_replay_started") is not True:
                errors.append("PHASE3F_R2B_DOWNSTREAM_REPLAY_STATE_INVALID")
            if state.get("r2_historical_performance_claimed") is not False:
                errors.append("PHASE3F_R2B_DOWNSTREAM_PERFORMANCE_DRIFT")
            if holdout_h1_downstream:
                if state.get("holdout_h1_complete") is not True or state.get("holdout_build_started") is not True:
                    errors.append("PHASE3F_HOLDOUT_H1_DOWNSTREAM_STATE_INVALID")
                if holdout_replay_downstream:
                    if state.get("holdout_h2_started") is not True:
                        errors.append("PHASE3F_HOLDOUT_REPLAY_DOWNSTREAM_STATE_INVALID")
                    if state.get("phase3d_r2_started") is True:
                        if state.get("phase3d_r2_round1_complete") is not True or state.get("phase3d_r2_performance_started") is not bool(state.get("phase3d_r2_performance_measurement_complete")):
                            errors.append("PHASE3F_PHASE3D_R2_ROUND1_DOWNSTREAM_STATE_INVALID")
                    elif state.get("phase3d_r2_started") is not False:
                        errors.append("PHASE3F_PHASE3D_R2_STARTED_FLAG_INVALID")
                elif state.get("holdout_h2_started") is not False:
                    errors.append("PHASE3F_HOLDOUT_H1_PREMATURE_H2")
            elif state.get("holdout_build_started") is not False:
                errors.append("PHASE3F_R2B_DOWNSTREAM_PREMATURE_HOLDOUT")
        else:
            if state.get("r2_real_historical_replay_executed") is not False or state.get("r2_historical_performance_claimed") is not False:
                errors.append("PHASE3F_R2_DOWNSTREAM_PREMATURE_REPLAY_OR_PERFORMANCE")
            if state.get("r2_phase3c_replay_started") is not False:
                errors.append("PHASE3F_R2_DOWNSTREAM_3C_ALREADY_STARTED")
    else:
        errors.append("CURRENT_PHASE_NOT_3F_OR_GOVERNED_POST3F_R2_OR_HOLDOUT")

    if cv.get("phase3f_started") is not True or cv.get("phase3f_complete") is not True:
        errors.append("CURRENT_PHASE3F_NOT_COMPLETE")
    if cv.get("phase3f_gate_outcome") != "CONTINUE_SHADOW_RESEARCH":
        errors.append("CURRENT_PHASE3F_OUTCOME_MISMATCH")
    if cv.get("phase3f_promotion_eligible") is not False or cv.get("phase4_entry_allowed") is not False:
        errors.append("CURRENT_PHASE3F_PREMATURE_PHASE4")
    if cv.get("phase3_historical_validation_complete") is not False:
        errors.append("CURRENT_PHASE3_PREMATURE_COMPLETE")

    if result["required_research_path"]["loopback"] != "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY":
        errors.append("PHASE3F_RESULT_LOOPBACK_MISMATCH")
    if result["required_research_path"]["phase4_entry_allowed"] is not False:
        errors.append("PHASE3F_RESULT_PHASE4_ALLOWED")

    for surface_name, surface in [
        ("CONTRACT", contract["authority_boundaries"]),
        ("VALIDATION", validation["authority_boundaries"]),
        ("RESULT", result["controls"]),
        ("STATE", state),
        ("CURRENT", current),
    ]:
        for key in [
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "orders",
        ]:
            if key in surface and surface[key] != 0:
                errors.append(f"{surface_name}_AUTHORITY_NONZERO_{key}")
        if surface.get("trade_authority") != "NONE":
            errors.append(f"{surface_name}_TRADE_AUTHORITY_CHANGED")

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3F_ACCEPTANCE_PASS requirements=1/4 outcome=CONTINUE_SHADOW_RESEARCH "
        "fixed_forms=NOT_PROMOTABLE_IN_CURRENT_FORM phase4_entry_allowed=false "
        "terminal_rejection=false orders=0 trade_authority=NONE"
    )
