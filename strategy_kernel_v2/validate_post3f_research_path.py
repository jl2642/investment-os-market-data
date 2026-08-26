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
    if not state.get("r2_phase3b_contract_definition_start_allowed") or state.get("r2_phase3b_contract_definition_started"):
        errors.append("PROGRAM_STATE_R2_ENTRY_MISMATCH")
    if current.get("current_phase") != "POST_PHASE3F_RESEARCH_PATH_DECISION":
        errors.append("CURRENT_PHASE_POST3F_MISMATCH")
    if current["validation"].get("post3f_research_path_decision_complete") is not True:
        errors.append("CURRENT_POST3F_DECISION_NOT_COMPLETE")
    if current.get("next_phase") != "PHASE_3B_R2_REVISED_MODEL_CONTRACT":
        errors.append("CURRENT_NEXT_PHASE_R2_MISMATCH")

    if state.get("phase3_historical_validation_complete") or state.get("phase4_entry_allowed") or state.get("phase4_forward_validation_complete") or state.get("phase5_migration_allowed"):
        errors.append("DOWNSTREAM_PHASE_PREMATURE")
    if current["validation"].get("phase4_entry_allowed"):
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
    print("POST3F_RESEARCH_PATH_PASS path=EVIDENCE_NATIVE_R2_PLUS_HOLDOUT next=PHASE_3B_R2 phase4_entry_allowed=false orders=0 trade_authority=NONE")
