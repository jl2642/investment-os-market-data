from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3e_ablation import build_default

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _validate_post3f_and_r2(errors: list[str], state: dict, current: dict, require_r2: bool) -> None:
    decision_path = ROOT / "PHASE3_POST3F_RESEARCH_PATH_DECISION.json"
    if not decision_path.exists():
        errors.append("LEGAL_POST3F_DOWNSTREAM_WITHOUT_DECISION")
        return
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("status") != "APPROVED_GOVERNED_DUAL_TRACK_RESEARCH_LOOPBACK":
        errors.append("LEGAL_POST3F_DOWNSTREAM_DECISION_NOT_GOVERNED")
    if decision.get("trigger", {}).get("phase3f_gate_outcome") != "CONTINUE_SHADOW_RESEARCH":
        errors.append("LEGAL_POST3F_DOWNSTREAM_PHASE3F_OUTCOME_DRIFT")
    if state.get("phase3f_started") is not True or state.get("phase3f_complete") is not True:
        errors.append("LEGAL_POST3F_DOWNSTREAM_WITHOUT_PHASE3F_COMPLETE")
    if state.get("phase3f_gate_outcome") != "CONTINUE_SHADOW_RESEARCH":
        errors.append("LEGAL_POST3F_DOWNSTREAM_GATE_OUTCOME_DRIFT")
    if state.get("phase3f_promotion_eligible") is not False:
        errors.append("LEGAL_POST3F_DOWNSTREAM_PROMOTION_ELIGIBLE")
    if state.get("phase4_entry_allowed") is not False or current["validation"].get("phase4_entry_allowed") is not False:
        errors.append("LEGAL_POST3F_DOWNSTREAM_PREMATURE_PHASE4")
    if current["validation"].get("post3f_research_path_decision_complete") is not True:
        errors.append("LEGAL_POST3F_DOWNSTREAM_DECISION_NOT_COMPLETE")

    if require_r2:
        r2_path = ROOT / "PHASE3B_R2_MODEL_CONTRACT.json"
        if not r2_path.exists():
            errors.append("LEGAL_R2_DOWNSTREAM_WITHOUT_CONTRACT")
            return
        r2 = json.loads(r2_path.read_text(encoding="utf-8"))
        if r2.get("status") != "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY":
            errors.append("LEGAL_R2_DOWNSTREAM_CONTRACT_NOT_FROZEN")
        if r2.get("model", {}).get("new_identity") is not True:
            errors.append("LEGAL_R2_DOWNSTREAM_NEW_IDENTITY_FALSE")
        if r2.get("model", {}).get("overwrites_prior_model") is not False:
            errors.append("LEGAL_R2_DOWNSTREAM_OVERWRITES_PRIOR")
        firewall = r2.get("development_corpus_firewall", {})
        if firewall.get("phase3d_realized_outcomes_may_select_fields") is not False:
            errors.append("LEGAL_R2_DOWNSTREAM_OUTCOME_TUNING_FIELDS")
        if firewall.get("phase3d_realized_outcomes_may_select_thresholds") is not False:
            errors.append("LEGAL_R2_DOWNSTREAM_OUTCOME_TUNING_THRESHOLDS")
        if firewall.get("phase3d_realized_outcomes_may_select_mappings") is not False:
            errors.append("LEGAL_R2_DOWNSTREAM_OUTCOME_TUNING_MAPPINGS")
        if state.get("r2_phase3b_contract_definition_started") is not True or state.get("r2_phase3b_contract_definition_complete") is not True:
            errors.append("LEGAL_R2_DOWNSTREAM_STATE_NOT_COMPLETE")
        r2b_downstream = state.get("r2_phase3c_r2b_complete") is True
        holdout_h1_downstream = state.get("holdout_h1_started") is True
        holdout_replay_downstream = state.get("independent_holdout_replay_complete") is True
        if r2b_downstream:
            if state.get("r2_real_historical_replay_executed") is not True or state.get("r2_phase3c_replay_started") is not True:
                errors.append("LEGAL_R2B_DOWNSTREAM_REPLAY_STATE_INVALID")
            if state.get("r2_historical_performance_claimed") is not False:
                errors.append("LEGAL_R2B_DOWNSTREAM_PERFORMANCE_DRIFT")
            if holdout_h1_downstream:
                if state.get("holdout_h1_complete") is not True or state.get("holdout_build_started") is not True:
                    errors.append("LEGAL_HOLDOUT_H1_DOWNSTREAM_STATE_INVALID")
                if holdout_replay_downstream:
                    if state.get("holdout_h2_started") is not True or state.get("phase3d_r2_started") is not False:
                        errors.append("LEGAL_HOLDOUT_REPLAY_DOWNSTREAM_STATE_INVALID")
                elif state.get("holdout_h2_started") is not False:
                    errors.append("LEGAL_HOLDOUT_H1_PREMATURE_H2")
            elif state.get("holdout_build_started") is not False:
                errors.append("LEGAL_R2B_DOWNSTREAM_PREMATURE_HOLDOUT")
        else:
            if state.get("r2_real_historical_replay_executed") is not False or state.get("r2_historical_performance_claimed") is not False:
                errors.append("LEGAL_R2_DOWNSTREAM_PREMATURE_REPLAY_OR_PERFORMANCE")
            if state.get("r2_phase3c_replay_started") is not False:
                errors.append("LEGAL_R2_DOWNSTREAM_3C_ALREADY_STARTED")
    elif state.get("r2_phase3b_contract_definition_started") is not False:
        errors.append("LEGAL_POST3F_DOWNSTREAM_R2_ALREADY_STARTED")


def validate() -> list[str]:
    errors: list[str] = []
    contract = load("PHASE3E_ABLATION_CONTRACT.json")
    validation = load("PHASE3E_VALIDATION.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    result = build_default(ROOT.parent)

    if contract.get("status") != "FROZEN_STRUCTURAL_ABLATION_NO_OUTCOME_TUNING":
        errors.append("PHASE3E_CONTRACT_NOT_FROZEN")
    corpus = contract["evaluation_corpus"]
    rules = contract["rules"]
    if corpus.get("phase3d_realized_outcomes_may_select_ablation") is not False:
        errors.append("PHASE3D_OUTCOMES_ALLOWED_TO_SELECT_ABLATION")
    if corpus.get("phase3d_returns_may_tune_requirements") is not False:
        errors.append("PHASE3D_RETURNS_ALLOWED_TO_TUNE_REQUIREMENTS")
    for key in [
        "proxy_substitution_allowed",
        "subjective_mapping_allowed",
        "retrospective_probability_creation_allowed",
        "retrospective_confidence_creation_allowed",
        "retrospective_cost_score_creation_allowed",
        "model_execution_under_revised_contract_allowed",
        "winner_selection_allowed",
        "same_seed_performance_claim_allowed",
    ]:
        if rules.get(key) is not False:
            errors.append("PHASE3E_RULE_NOT_FALSE_" + key)
    for key in [
        "one_component_at_a_time",
        "fixed_phase3b_models_are_not_overwritten",
        "material_revision_requires_new_model_identity",
        "material_revision_requires_return_to_phase3b_then_phase3c",
    ]:
        if rules.get(key) is not True:
            errors.append("PHASE3E_RULE_NOT_TRUE_" + key)

    if result.get("checkpoint_count") != 7:
        errors.append("PHASE3E_CHECKPOINT_COUNT_MISMATCH")
    if result.get("feature_security_instance_count") != 33:
        errors.append("PHASE3E_FEATURE_INSTANCE_COUNT_MISMATCH")
    if result.get("historical_source_reads") != 29:
        errors.append("PHASE3E_SOURCE_READ_COUNT_MISMATCH")
    if result.get("finding") != "NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY":
        errors.append("PHASE3E_FINDING_MISMATCH")
    if result.get("single_component_ablation_unlock_count") != 0:
        errors.append("PHASE3E_ABLATION_UNLOCK_NONZERO")

    p2 = result["phase2_ablation"]
    simple = result["simple_ablation"]
    if len(p2) != 5 or len(simple) != 6:
        errors.append("PHASE3E_VARIANT_COUNT_MISMATCH")
    if len(p2[1:]) + len(simple[1:]) != 9:
        errors.append("PHASE3E_SINGLE_COMPONENT_ABLATION_COUNT_MISMATCH")
    for row in p2 + simple:
        if row.get("evaluable_security_instance_count") != 0:
            errors.append("PHASE3E_UNEXPECTED_EVALUABLE_" + row["variant_id"])
    for row in p2[1:] + simple[1:]:
        if row.get("delta_vs_fixed_baseline") != 0:
            errors.append("PHASE3E_UNEXPECTED_COVERAGE_DELTA_" + row["variant_id"])

    expected_adjacent = {
        "scenario_context": 5,
        "return_context": 20,
        "confidence_context": 20,
        "concentration_context": 8,
        "execution_context": 8,
        "evidence_quality_context": 26,
        "downside_context": 26,
    }
    for key, expected in expected_adjacent.items():
        row = result["adjacent_observable_inventory"].get(key, {})
        if row.get("security_instance_count_with_adjacent_observable") != expected:
            errors.append("PHASE3E_ADJACENT_COUNT_MISMATCH_" + key)
        if row.get("contract_substitution_allowed") is not False:
            errors.append("PHASE3E_ADJACENT_SUBSTITUTION_ALLOWED_" + key)

    if validation.get("status") != "PASS_COMPLETE_BOUNDED_STRUCTURAL_ABLATION_NO_SINGLE_COMPONENT_RESTORES_REPLAY":
        errors.append("PHASE3E_VALIDATION_STATUS_MISMATCH")
    if validation["combined_finding"].get("single_component_ablation_count") != 9:
        errors.append("PHASE3E_VALIDATION_ABLATION_COUNT_MISMATCH")
    if validation["combined_finding"].get("single_component_ablation_unlock_count") != 0:
        errors.append("PHASE3E_VALIDATION_UNLOCK_NONZERO")
    if validation["model_revision"].get("material_revised_model_form_created") is not False:
        errors.append("PHASE3E_REVISED_MODEL_CREATED")
    if validation["model_revision"].get("same_seed_model_tuning_performed") is not False:
        errors.append("PHASE3E_SAME_SEED_TUNING_PERFORMED")
    if validation["model_revision"].get("required_loopback_for_material_revision") != "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY":
        errors.append("PHASE3E_LOOPBACK_GUARD_MISMATCH")

    if not state.get("phase3d_complete"):
        errors.append("PHASE3E_WITHOUT_PHASE3D_COMPLETE")
    if not state.get("phase3e_started") or not state.get("phase3e_complete"):
        errors.append("PHASE3E_STATE_NOT_COMPLETE")
    if state.get("phase3e_single_component_ablation_count") != 9:
        errors.append("PHASE3E_STATE_ABLATION_COUNT_MISMATCH")
    if state.get("phase3e_single_component_ablation_unlock_count") != 0:
        errors.append("PHASE3E_STATE_UNLOCK_NONZERO")
    if state.get("phase3e_fixed_models_overwritten") is not False:
        errors.append("PHASE3E_FIXED_MODEL_OVERWRITE")
    if state.get("phase3e_material_revised_model_form_created") is not False:
        errors.append("PHASE3E_STATE_REVISED_MODEL_CREATED")
    if state.get("phase3e_revised_forms_must_return_to_phase3b_phase3c") is not True:
        errors.append("PHASE3E_STATE_LOOPBACK_FALSE")
    if state.get("phase3f_start_allowed") is not True:
        errors.append("PHASE3F_START_NOT_ALLOWED_AFTER_3E")
    if state.get("phase3f_promotion_eligible") is not False:
        errors.append("PHASE3F_PREMATURE_PROMOTION_ELIGIBILITY")
    if state.get("phase3_historical_validation_complete") is not False:
        errors.append("PHASE3_PREMATURELY_COMPLETE")
    if state.get("phase4_forward_validation_complete") is not False:
        errors.append("PHASE4_PREMATURELY_COMPLETE")
    if state.get("phase5_migration_allowed") is not False:
        errors.append("PHASE5_PREMATURELY_ALLOWED")

    cv = current["validation"]
    current_phase = current.get("current_phase")
    allowed_current_phases = {
        "PHASE_3E_ABLATION_AND_ROBUSTNESS",
        "PHASE_3F_HISTORICAL_PROMOTION_GATE",
        "POST_PHASE3F_RESEARCH_PATH_DECISION",
        "PHASE_3B_R2_REVISED_MODEL_CONTRACT",
        "PHASE_3C_R2_POINT_IN_TIME_REPLAY",
        "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE",
    }
    if current_phase not in allowed_current_phases:
        errors.append("CURRENT_PHASE_NOT_3E_OR_LEGAL_DOWNSTREAM")
    if cv.get("phase3e_started") is not True or cv.get("phase3e_complete") is not True:
        errors.append("CURRENT_PHASE3E_NOT_COMPLETE")
    if cv.get("phase3e_single_component_ablation_count") != 9:
        errors.append("CURRENT_PHASE3E_ABLATION_COUNT_MISMATCH")
    if cv.get("phase3e_single_component_ablation_unlock_count") != 0:
        errors.append("CURRENT_PHASE3E_UNLOCK_NONZERO")
    if cv.get("phase3f_start_allowed") is not True:
        errors.append("CURRENT_PHASE3F_START_NOT_ALLOWED")
    if cv.get("phase3f_promotion_eligible") is not False:
        errors.append("CURRENT_PHASE3F_PREMATURELY_ELIGIBLE")

    if current_phase == "PHASE_3F_HISTORICAL_PROMOTION_GATE":
        phase3f_contract = load("PHASE3F_PROMOTION_GATE_CONTRACT.json")
        if phase3f_contract.get("status") != "FROZEN_HISTORICAL_PROMOTION_GATE":
            errors.append("LEGAL_3F_DOWNSTREAM_WITHOUT_FROZEN_GATE")
        if state.get("phase3f_started") is not True:
            errors.append("LEGAL_3F_DOWNSTREAM_WITHOUT_START")
        if state.get("phase4_entry_allowed") is not False:
            errors.append("LEGAL_3F_DOWNSTREAM_PREMATURE_PHASE4")
        if state.get("phase3f_material_revision_loopback") != "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY":
            errors.append("LEGAL_3F_DOWNSTREAM_LOOPBACK_DRIFT")
    elif current_phase == "POST_PHASE3F_RESEARCH_PATH_DECISION":
        _validate_post3f_and_r2(errors, state, current, False)
    elif current_phase in {"PHASE_3B_R2_REVISED_MODEL_CONTRACT", "PHASE_3C_R2_POINT_IN_TIME_REPLAY", "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE"}:
        _validate_post3f_and_r2(errors, state, current, True)

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
        "PHASE3E_ACCEPTANCE_PASS checkpoints=7 feature_instances=33 "
        "ablations=9 unlocks=0 phase3f_start_allowed=true "
        "phase3f_promotion_eligible=false orders=0 trade_authority=NONE"
    )
