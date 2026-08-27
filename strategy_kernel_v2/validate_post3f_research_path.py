import json
from pathlib import Path

from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate():
    errors = list(validate_program_consistency())
    decision = load("PHASE3_POST3F_RESEARCH_PATH_DECISION.json")
    phase3f = load("PHASE3F_VALIDATION.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")

    if phase3f["gate_outcome"] != "CONTINUE_SHADOW_RESEARCH":
        errors.append("PARENT_PHASE3F_OUTCOME_DRIFT")
    if phase3f["promotion_requirement_pass_count"] != 1 or phase3f["promotion_requirement_total_count"] != 4:
        errors.append("PARENT_PHASE3F_GATE_VECTOR_DRIFT")
    if phase3f["promotion_eligible"] or phase3f["phase4_entry_allowed"]:
        errors.append("PARENT_PHASE3F_PROMOTION_DRIFT")

    if decision["status"] != "APPROVED_GOVERNED_DUAL_TRACK_RESEARCH_LOOPBACK":
        errors.append("POST3F_DECISION_STATUS_MISMATCH")
    approved = {row["id"]: row["decision"] for row in decision["alternatives"]}
    if approved.get("NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION") != "APPROVED":
        errors.append("POST3F_APPROVED_PATH_MISSING")
    if approved.get("RETROSPECTIVE_PROXY_SUBSTITUTION_OR_OUTCOME_TUNING") != "REJECTED":
        errors.append("POST3F_UNSAFE_PATH_NOT_REJECTED")

    r2 = decision["r2_architecture_direction"]
    if not r2["new_model_identity_required_before_execution"]:
        errors.append("R2_NEW_IDENTITY_GUARD_MISSING")
    for key in ["scalar_policy_score_allowed", "silent_proxy_substitution_allowed", "subjective_mapping_allowed", "retrospective_probability_creation_allowed", "realized_outcome_tuning_allowed"]:
        if r2[key] is not False:
            errors.append("R2_UNSAFE_TRUE_" + key)
    if not r2["missingness_must_remain_explicit"]:
        errors.append("R2_MISSINGNESS_GUARD_MISSING")
    if not r2["fixed_phase3b_forms_preserved_for_audit"]:
        errors.append("R2_OVERWRITES_FIXED_3B")

    firewall = decision["development_corpus_firewall"]
    if firewall["phase3d_realized_outcomes_may_inform_contract_design"]:
        errors.append("R2_OUTCOME_TUNING_ALLOWED")
    if firewall["seven_seed_checkpoints_may_count_as_independent_holdout"]:
        errors.append("SEED_RELABELED_AS_HOLDOUT")
    if firewall["same_seed_tuning_may_count_as_validation"]:
        errors.append("SAME_SEED_TUNING_COUNTS_AS_VALIDATION")

    holdout = decision["holdout_coverage_contract_requirements"]
    for key in ["disjoint_from_seven_seed_checkpoints", "point_in_time_availability_provenance_required", "exact_source_identity_required", "later_evidence_backfill_forbidden", "coverage_must_expand_dates_or_regimes_beyond_current_seed", "quantitative_sufficiency_threshold_must_be_frozen_before_holdout_results"]:
        if holdout[key] is not True:
            errors.append("HOLDOUT_GUARD_FALSE_" + key)
    if holdout["checkpoint_selection_may_use_realized_outcomes"]:
        errors.append("HOLDOUT_SELECTION_USES_OUTCOMES")

    if not state.get("post3f_research_path_decision_complete"):
        errors.append("PROGRAM_STATE_POST3F_DECISION_NOT_COMPLETE")
    if state.get("post3f_research_path") != "NEW_IDENTITY_EVIDENCE_NATIVE_R2_PLUS_INDEPENDENT_HOLDOUT_EXPANSION":
        errors.append("PROGRAM_STATE_POST3F_PATH_MISMATCH")
    if not state.get("r2_phase3b_contract_definition_start_allowed"):
        errors.append("PROGRAM_STATE_R2_ENTRY_NOT_ALLOWED")

    current_phase = current.get("current_phase")
    cv = current["validation"]
    if current_phase == "POST_PHASE3F_RESEARCH_PATH_DECISION":
        if state.get("r2_phase3b_contract_definition_started"):
            errors.append("PROGRAM_STATE_R2_PREMATURE_START_IN_POST3F")
        if current.get("next_phase") != "PHASE_3B_R2_REVISED_MODEL_CONTRACT":
            errors.append("CURRENT_NEXT_PHASE_R2_MISMATCH")
    elif current_phase in {"PHASE_3B_R2_REVISED_MODEL_CONTRACT", "PHASE_3C_R2_POINT_IN_TIME_REPLAY", "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"}:
        contract_path = ROOT / "PHASE3B_R2_MODEL_CONTRACT.json"
        if not contract_path.exists():
            errors.append("R2_CURRENT_WITHOUT_FROZEN_CONTRACT")
        else:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            if contract.get("status") != "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY":
                errors.append("R2_CURRENT_CONTRACT_NOT_FROZEN")
            if contract.get("model", {}).get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
                errors.append("R2_CURRENT_MODEL_IDENTITY_DRIFT")
        if state.get("r2_phase3b_contract_definition_started") is not True or state.get("r2_phase3b_contract_definition_complete") is not True:
            errors.append("R2_CURRENT_STATE_NOT_COMPLETE")
        if cv.get("r2_phase3b_contract_definition_started") is not True or cv.get("r2_phase3b_contract_definition_complete") is not True:
            errors.append("R2_CURRENT_STATUS_NOT_COMPLETE")
        if state.get("r2_phase3c_replay_start_allowed") is not True:
            errors.append("R2_CURRENT_PHASE3C_START_NOT_ALLOWED")
        r2b_downstream = current_phase in {"PHASE_3C_R2_POINT_IN_TIME_REPLAY", "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"}
        holdout_h1_downstream = current_phase in {"INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE", "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"}
        holdout_replay_downstream = state.get("independent_holdout_replay_complete") is True
        if r2b_downstream:
            if state.get("r2_phase3c_replay_started") is not True or state.get("r2_phase3c_r2b_complete") is not True:
                errors.append("R2B_CURRENT_REPLAY_STATE_INVALID")
            if cv.get("r2_real_historical_replay_executed") is not True:
                errors.append("R2B_CURRENT_REPLAY_NOT_EXECUTED")
            if cv.get("r2_historical_performance_claimed") is not False:
                errors.append("R2B_CURRENT_PERFORMANCE_DRIFT")
            if holdout_h1_downstream:
                if state.get("holdout_h1_complete") is not True or cv.get("holdout_build_started") is not True:
                    errors.append("HOLDOUT_H1_CURRENT_STATE_INVALID")
                if holdout_replay_downstream:
                    if cv.get("holdout_h2_started") is not True:
                        errors.append("HOLDOUT_REPLAY_H2_NOT_STARTED")
                    if cv.get("phase3d_r2_started") is True:
                        if cv.get("phase3d_r2_round1_complete") is not True:
                            errors.append("PHASE3D_R2_ROUND1_NOT_COMPLETE")
                        if cv.get("phase3d_r2_round1_status") != "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED":
                            errors.append("PHASE3D_R2_ROUND1_STATUS_DRIFT")
                        if cv.get("phase3d_r2_performance_started") is not bool(cv.get("phase3d_r2_performance_measurement_complete")):
                            errors.append("PHASE3D_R2_PREMATURE_PERFORMANCE")
                    elif cv.get("phase3d_r2_started") is not False:
                        errors.append("PHASE3D_R2_STARTED_FLAG_INVALID")
                elif cv.get("holdout_h2_started") is not False:
                    errors.append("HOLDOUT_H1_PREMATURE_H2")
                holdout_v2_pass = (
                    state.get("holdout_v2_selection_complete") is True
                    and state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
                )
                expected_next = (
                    (
                        (
                            "PHASE_3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT"
                            if cv.get("phase3d_r2_performance_measurement_complete") is True
                            else "PHASE_3D_R2_PERFORMANCE_MEASUREMENT"
                        )
                        if cv.get("phase3d_r2_outcome_evidence_acquisition_complete") is True
                        else "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION"
                    )
                    if cv.get("phase3d_r2_started") is True
                    else (
                        "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"
                        if holdout_replay_downstream
                        else (
                            "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
                            if holdout_v2_pass
                            else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
                        )
                    )
                )
                if current.get("next_phase") != expected_next:
                    errors.append("HOLDOUT_CURRENT_NEXT_PHASE_DRIFT")
            else:
                if cv.get("holdout_build_started") is not False:
                    errors.append("R2B_CURRENT_PREMATURE_HOLDOUT")
                if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
                    errors.append("R2B_CURRENT_NEXT_PHASE_NOT_HOLDOUT")
        else:
            if state.get("r2_phase3c_replay_started") is not False:
                errors.append("R2_CURRENT_PHASE3C_BOUNDARY_DRIFT")
            if cv.get("r2_real_historical_replay_executed") is not False or cv.get("r2_historical_performance_claimed") is not False:
                errors.append("R2_CURRENT_PREMATURE_REPLAY_OR_PERFORMANCE")
            if current.get("next_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
                errors.append("R2_CURRENT_NEXT_PHASE_NOT_3C_R2")
    else:
        errors.append("CURRENT_PHASE_NOT_POST3F_OR_GOVERNED_R2")

    if cv.get("post3f_research_path_decision_complete") is not True:
        errors.append("CURRENT_POST3F_DECISION_NOT_COMPLETE")
    if state.get("phase3_historical_validation_complete") or state.get("phase4_entry_allowed") or state.get("phase4_forward_validation_complete") or state.get("phase5_migration_allowed"):
        errors.append("DOWNSTREAM_PHASE_PREMATURE")
    if cv.get("phase4_entry_allowed"):
        errors.append("CURRENT_PHASE4_PREMATURE")

    controls = decision["authority_boundaries"]
    for key in ["effective_core_static_changes", "candidate_membership_mutations", "real_account_mutations", "simulation_mutations", "target_portfolio_writebacks", "user_decisions_generated", "investment_recommendations_generated", "orders"]:
        if controls[key] != 0:
            errors.append("POST3F_AUTHORITY_NONZERO_" + key)
    if controls["trade_authority"] != "NONE" or state["trade_authority"] != "NONE" or current["trade_authority"] != "NONE":
        errors.append("POST3F_TRADE_AUTHORITY_CHANGED")

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print("POST3F_RESEARCH_PATH_PASS path=EVIDENCE_NATIVE_R2_PLUS_HOLDOUT phase3b_r2_contract_complete=true phase4_entry_allowed=false orders=0 trade_authority=NONE")
