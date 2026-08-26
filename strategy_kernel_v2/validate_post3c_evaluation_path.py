import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate():
    errors = list(validate_program_consistency())
    decision = load("PHASE3_POST3C_EVALUATION_PATH_DECISION.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")

    if decision["phase3_subphase_sequence_unchanged"] != ["3A", "3B", "3C", "3D", "3E", "3F"]:
        errors.append("DECISION_PHASE3_SEQUENCE_CHANGED")
    if decision["macro_lifecycle_unchanged"] is not True:
        errors.append("DECISION_MACRO_LIFECYCLE_CHANGED")

    alternatives = {row["id"]: row["decision"] for row in decision["alternatives"]}
    if alternatives.get("PHASE3D_NEGATIVE_RESULT_MEASURABILITY_PATH") != "APPROVED":
        errors.append("NEGATIVE_RESULT_PATH_NOT_APPROVED")
    for rejected in [
        "RETROSPECTIVE_INPUT_SYNTHESIS",
        "SILENT_PHASE3B_CONTRACT_REWRITE",
        "SKIP_PHASE3D_TO_PHASE3E",
    ]:
        if alternatives.get(rejected) != "REJECTED":
            errors.append("UNSAFE_ALTERNATIVE_NOT_REJECTED:" + rejected)

    rules = decision["approved_path"]["phase3d_rules"]
    if rules["candidate_metrics_without_contemporaneous_outputs"] != "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS":
        errors.append("NONMEASURABLE_SENTINEL_CHANGED")
    for key in [
        "pre_register_outcome_horizons_and_reference_definitions_before_loading_realized_outcomes",
        "hypothetical_candidate_decisions_forbidden",
        "retrospective_candidate_output_generation_forbidden",
        "cross_model_winner_selection_forbidden_when_candidate_outputs_absent",
        "outcome_data_may_not_feed_back_into_replayed_inputs_or_parameters",
    ]:
        if rules.get(key) is not True:
            errors.append("PHASE3D_RULE_FALSE:" + key)

    e_rules = decision["approved_path"]["phase3e_rules"]
    for key in [
        "revised_model_forms_must_be_versioned_new_forms",
        "revised_model_forms_may_not_overwrite_phase3b_historical_forms",
        "revised_forms_require_return_to_phase3b_and_phase3c_before_any_phase3f_promotion",
        "same_seed_outcome_tuning_forbidden",
        "broader_or_holdout_historical_validation_required_for_revised_forms",
    ]:
        if e_rules.get(key) is not True:
            errors.append("PHASE3E_RULE_FALSE:" + key)

    if not state.get("post3c_evaluation_path_decision_complete"):
        errors.append("STATE_DECISION_NOT_COMPLETE")
    if not state.get("phase3d_start_allowed"):
        errors.append("STATE_PHASE3D_NOT_ALLOWED")
    if state.get("phase3d_started"):
        errors.append("STATE_PHASE3D_STARTED_TOO_EARLY")
    if state.get("phase3f_promotion_eligible"):
        errors.append("STATE_PHASE3F_PREMATURE")

    cv = current["validation"]
    if cv.get("post3c_evaluation_path_decision_complete") is not True:
        errors.append("CURRENT_DECISION_NOT_COMPLETE")
    if cv.get("phase3d_start_allowed") is not True:
        errors.append("CURRENT_PHASE3D_NOT_ALLOWED")
    if cv.get("phase3d_started") is not False:
        errors.append("CURRENT_PHASE3D_STARTED_TOO_EARLY")

    for key, expected in {
        "effective_core_static_changes": 0,
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_mutations": 0,
        "target_portfolio_writebacks": 0,
        "user_decisions_generated": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }.items():
        if state.get(key) != expected or current.get(key) != expected:
            errors.append("AUTHORITY_BOUNDARY_MISMATCH:" + key)

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print("POST3C_EVALUATION_PATH_PASS phase3d_start_allowed=true phase3d_started=false candidate_missing_outputs=NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS orders=0 trade_authority=NONE")
