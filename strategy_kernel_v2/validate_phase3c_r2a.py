from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3b_r2_contract import load_contract as load_r2_contract, validate_contract as validate_r2_contract
from strategy_kernel_v2.phase3c_r2a_reconstruction import (
    build_default,
    load_replay_contract,
    validate_replay_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate() -> tuple[list[str], dict]:
    errors = list(validate_program_consistency())
    replay_contract = load_replay_contract()
    r2_contract = load_r2_contract()
    errors.extend(validate_replay_contract(replay_contract))
    errors.extend(validate_r2_contract(r2_contract))

    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    cv = current.get("validation", {})

    first = build_default(ROOT.parent)
    second = build_default(ROOT.parent)
    if first["reconstruction_sha256"] != second["reconstruction_sha256"]:
        errors.append("R2A_NONDETERMINISTIC_REBUILD")
    if first != second:
        errors.append("R2A_REBUILD_PAYLOAD_DRIFT")

    acceptance = replay_contract["acceptance"]
    exact_checks = {
        "checkpoint_count": acceptance["checkpoint_count_must_equal"],
        "unique_registered_historical_source_reads": acceptance[
            "unique_registered_historical_source_reads_must_equal"
        ],
        "frozen_transform_rule_count": acceptance["frozen_transform_rule_count_must_equal"],
        "model_specific_evidence_fetch_count": acceptance[
            "model_specific_evidence_fetch_count_must_equal"
        ],
        "subjective_feature_fill_count": acceptance["subjective_feature_fill_count_must_equal"],
        "later_evidence_backfill_count": acceptance["later_evidence_backfill_count_must_equal"],
        "pareto_comparison_count": acceptance["pareto_comparison_count_must_equal"],
        "historical_performance_metric_count": acceptance[
            "historical_performance_metric_count_must_equal"
        ],
        "holdout_checkpoint_count": acceptance["holdout_checkpoint_count_must_equal"],
    }
    for key, expected in exact_checks.items():
        if first.get(key) != expected:
            errors.append(f"R2A_ACCEPTANCE_MISMATCH:{key}:{first.get(key)}:{expected}")

    if first.get("r2_profile_instances", 0) <= 0:
        errors.append("R2A_NO_RECONSTRUCTED_PROFILE_INSTANCES")
    if first.get("present_dimension_instances", 0) <= 0:
        errors.append("R2A_NO_PRESENT_DIMENSIONS")
    if first.get("transform_failure_instances") != 0:
        errors.append("R2A_TRANSFORM_FAILURES_PRESENT")
    if first.get("realized_outcome_record_count") != 0:
        errors.append("R2A_REALIZED_OUTCOMES_LOADED")
    if first.get("cross_signature_comparison_count") != 0:
        errors.append("R2A_CROSS_SIGNATURE_COMPARISON_EXECUTED")
    if first.get("ranking_generated") is not False or first.get("winner_selected") is not False:
        errors.append("R2A_RANKING_OR_WINNER_GENERATED")
    if first.get("target_weights_generated") is not False:
        errors.append("R2A_TARGET_WEIGHTS_GENERATED")
    if first.get("phase4_entry_allowed") is not False:
        errors.append("R2A_PREMATURE_PHASE4")

    selected_by_checkpoint = {
        cp["decision_point_id"]: set(cp["selected_evidence_ids"])
        for cp in first["checkpoints"]
    }
    for checkpoint in first["checkpoints"]:
        selected = selected_by_checkpoint[checkpoint["decision_point_id"]]
        for profile in checkpoint["profiles"]:
            if set(profile["provenance_evidence_ids"]) - selected:
                errors.append("R2A_PROFILE_PROVENANCE_OUTSIDE_CHECKPOINT")
            for dim in profile["dimension_states"]:
                if set(dim.get("provenance_evidence_ids", [])) - selected:
                    errors.append("R2A_DIMENSION_PROVENANCE_OUTSIDE_CHECKPOINT")
                if dim["state"] == "MISSING" and dim.get("applicability_state") != "UNKNOWN_APPLICABILITY":
                    errors.append("R2A_MISSINGNESS_APPLICABILITY_DRIFT")
                if dim["state"] == "MISSING" and "value" in dim:
                    errors.append("R2A_MISSING_DIMENSION_HAS_VALUE")

    if state.get("r2_phase3b_contract_definition_complete") is not True:
        errors.append("R2A_PARENT_R2_CONTRACT_NOT_COMPLETE")
    if state.get("r2_phase3c_replay_started") is not True:
        errors.append("R2A_STATE_PHASE3C_R2_NOT_STARTED")
    if state.get("r2_phase3c_r2a_started") is not True or state.get("r2_phase3c_r2a_complete") is not True:
        errors.append("R2A_STATE_NOT_COMPLETE")
    if state.get("r2_pit_reconstruction_executed") is not True:
        errors.append("R2A_STATE_RECONSTRUCTION_NOT_EXECUTED")
    if state.get("r2_phase3c_r2b_start_allowed") is not True or state.get("r2_phase3c_r2b_started") is not False:
        errors.append("R2A_STATE_R2B_GATE_DRIFT")
    if state.get("r2_real_historical_replay_executed") is not False:
        errors.append("R2A_STATE_PREMATURE_MECHANICAL_REPLAY")
    if state.get("holdout_build_started") is not False:
        errors.append("R2A_STATE_PREMATURE_HOLDOUT")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("R2A_STATE_PREMATURE_PHASE4")

    if current.get("current_phase") != "PHASE_3C_R2A_POINT_IN_TIME_RECONSTRUCTION":
        errors.append("R2A_CURRENT_PHASE_MISMATCH")
    if current.get("next_phase") != "PHASE_3C_R2B_MECHANICAL_REPLAY_AUDIT_ACCEPTANCE":
        errors.append("R2A_NEXT_PHASE_MISMATCH")
    if cv.get("r2_phase3c_r2a_complete") is not True:
        errors.append("R2A_CURRENT_NOT_COMPLETE")
    if cv.get("r2_phase3c_r2b_start_allowed") is not True or cv.get("r2_phase3c_r2b_started") is not False:
        errors.append("R2A_CURRENT_R2B_GATE_DRIFT")
    if cv.get("r2a_pareto_executed") is not False:
        errors.append("R2A_CURRENT_PARETO_EXECUTED")
    if cv.get("r2a_realized_outcomes_loaded") is not False:
        errors.append("R2A_CURRENT_OUTCOMES_LOADED")
    if cv.get("r2a_holdout_started") is not False:
        errors.append("R2A_CURRENT_HOLDOUT_STARTED")
    if cv.get("phase4_entry_allowed") is not False:
        errors.append("R2A_CURRENT_PREMATURE_PHASE4")

    for surface_name, surface in [
        ("CONTRACT", replay_contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
        ("RESULT", first["controls"]),
    ]:
        for key in (
            "effective_core_static_changes",
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "user_decisions_generated",
            "orders",
        ):
            if key in surface and surface[key] != 0:
                errors.append(f"{surface_name}_AUTHORITY_NONZERO_{key}")
        if surface.get("trade_authority") != "NONE":
            errors.append(f"{surface_name}_TRADE_AUTHORITY_CHANGED")

    if not errors:
        write_default(first)
    return errors, first


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE3C_R2A_ACCEPTANCE_PASS "
        f"checkpoints={result['checkpoint_count']} source_reads={result['unique_registered_historical_source_reads']} "
        f"feature_instances={result['feature_security_instances']} profiles={result['r2_profile_instances']} "
        f"present_dimensions={result['present_dimension_instances']} missing_dimensions={result['missing_dimension_instances']} "
        f"comparison_contract_evaluable_profiles={result['comparison_contract_evaluable_profiles']} "
        f"distinct_signatures={result['distinct_comparison_signature_count']} transform_failures=0 "
        "pareto_comparisons=0 outcomes=0 holdout=0 r2b_start_allowed=true "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
