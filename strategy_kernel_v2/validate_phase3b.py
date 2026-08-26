"""Independent acceptance validator for Strategy Kernel v2 Phase 3B."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy_kernel_v2.build_phase3a_ledger import build as build_phase3a
from strategy_kernel_v2.competing_model_forms import (
    MODEL_ORDER,
    build_shared_observation_packet,
    run_competing_model_suite,
)

MANIFEST = ROOT / "PHASE3B_MODEL_FORMS.json"
VALIDATION = ROOT / "PHASE3B_VALIDATION.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_phase3b() -> list[str]:
    errors: list[str] = []
    manifest = load_json(MANIFEST)
    validation = load_json(VALIDATION)
    ledger = build_phase3a()

    expected_models = list(MODEL_ORDER)
    declared_models = [row.get("model_form") for row in manifest.get("model_forms", [])]
    if declared_models != expected_models:
        errors.append("MODEL_FORM_SET_OR_ORDER_MISMATCH")
    if validation.get("status") != "PASS_CONTRACT_ONLY":
        errors.append("PHASE3B_STATUS_NOT_CONTRACT_ONLY_PASS")
    if validation.get("scope", {}).get("model_forms") != expected_models:
        errors.append("VALIDATION_MODEL_FORM_SET_MISMATCH")
    if validation.get("scope", {}).get("model_form_count") != len(expected_models):
        errors.append("VALIDATION_MODEL_FORM_COUNT_MISMATCH")

    shared = manifest.get("shared_input_contract", {})
    for key in (
        "same_timestamp_required",
        "same_opportunity_set_required",
        "same_selected_evidence_required",
        "same_reference_asset_required",
        "model_specific_evidence_fetch_forbidden",
        "structured_observation_provenance_must_resolve_inside_phase3a_snapshot",
    ):
        if shared.get(key) is not True:
            errors.append("SHARED_INPUT_GUARD_MISSING_" + key)
    if shared.get("missing_model_inputs_policy") != "NOT_EVALUABLE_NO_BACKFILL":
        errors.append("MISSING_INPUT_POLICY_NOT_FAIL_CLOSED")

    boundary = manifest.get("phase_boundary", {})
    for key in (
        "phase3b_extracts_historical_features",
        "phase3b_replays_decisions",
        "phase3b_calibrates_parameters",
        "phase3b_selects_winning_model",
    ):
        if boundary.get(key) is not False:
            errors.append("PHASE3B_BOUNDARY_BROKEN_" + key)
    if boundary.get("phase3c_required_for_decision_replay") is not True:
        errors.append("PHASE3C_REPLAY_GATE_MISSING")
    if boundary.get("phase3d_required_for_calibration_and_regret") is not True:
        errors.append("PHASE3D_CALIBRATION_GATE_MISSING")

    snapshots = ledger.get("snapshots", [])
    if len(snapshots) != validation.get("scope", {}).get("phase3a_seed_checkpoints"):
        errors.append("REAL_SEED_CHECKPOINT_COUNT_MISMATCH")
    if ledger.get("evidence_record_count") != validation.get("scope", {}).get("phase3a_seed_evidence_records"):
        errors.append("REAL_SEED_EVIDENCE_COUNT_MISMATCH")

    evaluable_pairs = 0
    input_hashes: set[str] = set()
    for snapshot in snapshots:
        packet = build_shared_observation_packet(snapshot)
        first = run_competing_model_suite(packet)
        second = run_competing_model_suite(packet)
        if first != second:
            errors.append("NON_DETERMINISTIC_MODEL_SUITE_" + snapshot["decision_point_id"])
        if first.get("model_order") != expected_models:
            errors.append("RUNTIME_MODEL_ORDER_MISMATCH_" + snapshot["decision_point_id"])
        input_hashes.add(packet["input_packet_sha256"])
        if first.get("input_packet_sha256") != packet["input_packet_sha256"]:
            errors.append("SUITE_INPUT_HASH_MISMATCH_" + snapshot["decision_point_id"])
        if first.get("model_specific_evidence_fetches") != 0:
            errors.append("MODEL_SPECIFIC_EVIDENCE_FETCH_DETECTED")
        if first.get("decision_replay_generated") is not False:
            errors.append("DECISION_REPLAY_PREMATURELY_GENERATED")
        if first.get("investment_recommendation_generated") is not False:
            errors.append("INVESTMENT_RECOMMENDATION_GENERATED")
        if first.get("user_decision_generated") is not False:
            errors.append("USER_DECISION_GENERATED")
        for model in first.get("models", []):
            if model.get("input_packet_sha256") != packet["input_packet_sha256"]:
                errors.append("MODEL_INPUT_IDENTITY_BROKEN")
            if model.get("policy_score") is not None:
                errors.append("SCALAR_POLICY_SCORE_GENERATED")
            if model.get("target_weights") is not None:
                errors.append("TARGET_WEIGHT_GENERATED")
            if model.get("decision_replay_generated") is not False:
                errors.append("MODEL_DECISION_REPLAY_GENERATED")
            if model.get("investment_recommendation_generated") is not False:
                errors.append("MODEL_INVESTMENT_RECOMMENDATION_GENERATED")
            if model.get("user_decision_generated") is not False:
                errors.append("MODEL_USER_DECISION_GENERATED")
            evaluable_pairs += int(model.get("evaluable_count", 0))

    declared = validation.get("validation", {})
    if declared.get("real_seed_evaluable_model_checkpoint_pairs") != evaluable_pairs:
        errors.append("REAL_SEED_EVALUABLE_PAIR_DECLARATION_MISMATCH")
    if evaluable_pairs != 0:
        errors.append("REAL_SEED_SHOULD_FAIL_CLOSED_BEFORE_PHASE3C_FEATURE_EXTRACTION")
    if declared.get("model_specific_evidence_fetches") != 0:
        errors.append("DECLARED_MODEL_SPECIFIC_FETCH_NONZERO")
    for key in (
        "retrospective_probability_backfills",
        "retrospective_scenario_backfills",
        "scalar_policy_scores_generated",
        "target_weights_generated",
        "investment_recommendations_generated",
        "user_decisions_generated",
    ):
        if declared.get(key) != 0:
            errors.append("DECLARED_NONZERO_" + key)

    promotion = validation.get("promotion", {})
    if promotion.get("phase3c_start_allowed") is not True:
        errors.append("PHASE3C_START_NOT_ALLOWED")
    for key in (
        "phase3_historical_validation_complete",
        "phase3f_promotion_eligible",
        "phase4_entry_allowed",
        "phase5_migration_allowed",
    ):
        if promotion.get(key) is not False:
            errors.append("PREMATURE_PROMOTION_" + key)
    if promotion.get("historical_coverage_expansion_required_before_phase3f") is not True:
        errors.append("PHASE3F_COVERAGE_GUARD_MISSING")

    boundaries = validation.get("authority_boundaries", {})
    for key in (
        "effective_core_static_changes",
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "orders",
    ):
        if boundaries.get(key) != 0:
            errors.append("AUTHORITY_BOUNDARY_NONZERO_" + key)
    if boundaries.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")

    return errors


def main() -> int:
    errors = validate_phase3b()
    if errors:
        raise AssertionError(";".join(errors))
    validation = load_json(VALIDATION)
    print(
        "PHASE3B_ACCEPTANCE_PASS",
        f"model_forms={validation['scope']['model_form_count']}",
        f"checkpoints={validation['scope']['phase3a_seed_checkpoints']}",
        "real_evaluable_pairs=0",
        "decision_replay_generated=false",
        "orders=0",
        "trade_authority=NONE",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
