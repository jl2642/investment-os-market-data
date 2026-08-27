from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3b_r2_contract import load_contract as load_r2_contract, validate_contract as validate_r2_contract
from strategy_kernel_v2.phase3c_r2a_reconstruction import build_default, load_replay_contract, validate_replay_contract, write_default
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

    first = build_default(ROOT.parent)
    second = build_default(ROOT.parent)
    if first != second or first["reconstruction_sha256"] != second["reconstruction_sha256"]:
        errors.append("R2A_NONDETERMINISTIC_REBUILD")

    acceptance = replay_contract["acceptance"]
    exact = {
        "checkpoint_count": acceptance["checkpoint_count_must_equal"],
        "unique_registered_historical_source_reads": acceptance["unique_registered_historical_source_reads_must_equal"],
        "frozen_transform_rule_count": acceptance["frozen_transform_rule_count_must_equal"],
        "model_specific_evidence_fetch_count": 0,
        "subjective_feature_fill_count": 0,
        "later_evidence_backfill_count": 0,
        "pareto_comparison_count": 0,
        "historical_performance_metric_count": 0,
        "holdout_checkpoint_count": 0,
        "realized_outcome_record_count": 0,
        "cross_signature_comparison_count": 0,
    }
    for key, expected in exact.items():
        if first.get(key) != expected:
            errors.append(f"R2A_ACCEPTANCE_MISMATCH:{key}:{first.get(key)}:{expected}")

    if first.get("r2_profile_instances", 0) <= 0:
        errors.append("R2A_NO_RECONSTRUCTED_PROFILE_INSTANCES")
    if first.get("present_dimension_instances", 0) <= 0:
        errors.append("R2A_NO_PRESENT_DIMENSIONS")
    if first.get("transform_failure_instances") != 0:
        failure_details = []
        for checkpoint in first.get("checkpoints", []):
            for profile in checkpoint.get("profiles", []):
                for dim in profile.get("dimension_states", []):
                    if dim.get("state") == "TRANSFORM_FAILURE":
                        failure_details.append({
                            "decision_point_id": checkpoint.get("decision_point_id"),
                            "security_id": profile.get("security_id"),
                            "rule_id": dim.get("rule_id"),
                            "reason": dim.get("reason"),
                            "source_feature_key": dim.get("source_feature_key"),
                        })
        errors.append(
            "R2A_TRANSFORM_FAILURES_PRESENT:"
            + json.dumps(failure_details, ensure_ascii=False, sort_keys=True)
        )
    if first.get("ranking_generated") is not False or first.get("winner_selected") is not False:
        errors.append("R2A_RANKING_OR_WINNER_GENERATED")
    if first.get("target_weights_generated") is not False or first.get("phase4_entry_allowed") is not False:
        errors.append("R2A_TARGET_WEIGHT_OR_PHASE4_DRIFT")

    for checkpoint in first["checkpoints"]:
        selected = set(checkpoint["selected_evidence_ids"])
        for profile in checkpoint["profiles"]:
            if set(profile["provenance_evidence_ids"]) - selected:
                errors.append("R2A_PROFILE_PROVENANCE_OUTSIDE_CHECKPOINT")
            for dim in profile["dimension_states"]:
                if set(dim.get("provenance_evidence_ids", [])) - selected:
                    errors.append("R2A_DIMENSION_PROVENANCE_OUTSIDE_CHECKPOINT")
                if dim["state"] == "MISSING":
                    if dim.get("applicability_state") != "UNKNOWN_APPLICABILITY":
                        errors.append("R2A_MISSINGNESS_APPLICABILITY_DRIFT")
                    if "value" in dim:
                        errors.append("R2A_MISSING_DIMENSION_HAS_VALUE")

    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    cv = current["validation"]
    if state.get("r2_phase3b_contract_definition_complete") is not True:
        errors.append("R2A_PARENT_R2_CONTRACT_NOT_COMPLETE")
    if state.get("r2_phase3c_replay_start_allowed") is not True:
        errors.append("R2A_MECHANICAL_REPLAY_NOT_AUTHORIZED")
    # R2A remains immutable even after governed R2B starts.
    r2b_downstream = state.get("r2_phase3c_r2b_complete") is True
    if r2b_downstream:
        if state.get("r2_phase3c_replay_started") is not True:
            errors.append("R2A_LEGAL_R2B_DOWNSTREAM_REPLAY_NOT_STARTED")
    elif state.get("r2_phase3c_replay_started") is not False:
        errors.append("R2A_PREMATURE_MECHANICAL_REPLAY_START")
    if state.get("r2_phase3c_r2a_started") is not True or state.get("r2_phase3c_r2a_complete") is not True:
        errors.append("R2A_STATE_NOT_COMPLETE")
    if state.get("r2_pit_reconstruction_executed") is not True:
        errors.append("R2A_STATE_RECONSTRUCTION_NOT_EXECUTED")
    if state.get("r2_phase3c_r2b_start_allowed") is not True:
        errors.append("R2A_STATE_R2B_GATE_DRIFT")
    if r2b_downstream:
        if state.get("r2_phase3c_r2b_started") is not True or state.get("r2_real_historical_replay_executed") is not True:
            errors.append("R2A_LEGAL_R2B_DOWNSTREAM_STATE_INVALID")
    else:
        if state.get("r2_phase3c_r2b_started") is not False or state.get("r2_real_historical_replay_executed") is not False:
            errors.append("R2A_PREMATURE_REPLAY")
    holdout_h1_downstream = state.get("holdout_h1_started") is True
    holdout_replay_downstream = state.get("independent_holdout_replay_complete") is True
    if holdout_h1_downstream:
        if state.get("holdout_h1_complete") is not True or state.get("holdout_build_started") is not True:
            errors.append("R2A_LEGAL_HOLDOUT_H1_STATE_INVALID")
        if holdout_replay_downstream:
            if state.get("holdout_h2_started") is not True:
                errors.append("R2A_LEGAL_HOLDOUT_REPLAY_H2_NOT_STARTED")
            if state.get("phase3d_r2_started") is not False:
                errors.append("R2A_LEGAL_HOLDOUT_REPLAY_PREMATURE_3D_R2")
        elif state.get("holdout_h2_started") is not False:
            errors.append("R2A_LEGAL_HOLDOUT_H1_PREMATURE_H2")
    elif state.get("holdout_build_started") is not False:
        errors.append("R2A_PREMATURE_HOLDOUT")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("R2A_STATE_PREMATURE_PHASE4")

    if r2b_downstream:
        if holdout_h1_downstream:
            if current.get("current_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
                errors.append("R2A_LEGAL_HOLDOUT_H1_CURRENT_PHASE_DRIFT")
            holdout_v2_pass = (
                state.get("holdout_v2_selection_complete") is True
                and state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
            )
            expected_next = (
                "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"
                if holdout_replay_downstream
                else (
                    "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
                    if holdout_v2_pass
                    else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
                )
            )
            if current.get("next_phase") != expected_next:
                errors.append("R2A_LEGAL_HOLDOUT_NEXT_PHASE_DRIFT")
        else:
            if current.get("current_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
                errors.append("R2A_LEGAL_R2B_CURRENT_PHASE_DRIFT")
            if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
                errors.append("R2A_LEGAL_R2B_NEXT_PHASE_DRIFT")
    else:
        if current.get("current_phase") != "PHASE_3B_R2_REVISED_MODEL_CONTRACT":
            errors.append("R2A_GOVERNED_PRE_REPLAY_PHASE_DRIFT")
        if current.get("next_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
            errors.append("R2A_NEXT_PHASE_MISMATCH")
    expected_current = [
        ("r2_phase3c_r2a_complete", True),
        ("r2_pit_reconstruction_executed", True),
        ("r2a_pareto_executed", False),
        ("r2a_realized_outcomes_loaded", False),
        ("r2a_holdout_started", False),
        ("r2_phase3c_r2b_start_allowed", True),
        ("r2_phase3c_r2b_started", True if r2b_downstream else False),
        ("phase4_entry_allowed", False),
    ]
    for key, expected in expected_current:
        if cv.get(key) is not expected:
            errors.append("R2A_CURRENT_STATUS_DRIFT:" + key)

    for surface_name, surface in [
        ("CONTRACT", replay_contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
        ("RESULT", first["controls"]),
    ]:
        for key in ("effective_core_static_changes", "candidate_membership_mutations", "real_account_mutations", "simulation_mutations", "target_portfolio_writebacks", "user_decisions_generated", "orders"):
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
