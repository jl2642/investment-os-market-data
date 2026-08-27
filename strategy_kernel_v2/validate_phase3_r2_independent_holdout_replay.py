from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3_r2_independent_holdout_replay import (
    OUTPUT_FILE,
    build_holdout_replay,
    load_replay_contract,
    validate_replay_contract,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3_r2_holdout_v2_selection import (
    validate as validate_v2_selection,
)

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate() -> tuple[list[str], dict]:
    errors = list(validate_program_consistency())
    selection_errors, selection = validate_v2_selection()
    errors.extend(selection_errors)

    contract = load_replay_contract()
    errors.extend(validate_replay_contract(contract))

    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    cv = current.get("validation", {})

    first = build_holdout_replay(ROOT.parent)
    second = build_holdout_replay(ROOT.parent)
    if first != second or first["replay_sha256"] != second["replay_sha256"]:
        errors.append("HOLDOUT_REPLAY_NONDETERMINISTIC")

    parent = contract["parent_selection"]
    if first.get("parent_selection_ledger_sha256") != parent["selection_ledger_sha256"]:
        errors.append("HOLDOUT_REPLAY_PARENT_LEDGER_SHA_DRIFT")
    if first.get("checkpoint_count") != parent["checkpoint_count"]:
        errors.append("HOLDOUT_REPLAY_CHECKPOINT_COUNT_DRIFT")
    if first.get("selection_checkpoint_count") != parent["checkpoint_count"]:
        errors.append("HOLDOUT_REPLAY_SELECTION_COUNT_DRIFT")
    if first.get("research_security_scope_count") != parent["research_security_scope_count"]:
        errors.append("HOLDOUT_REPLAY_SECURITY_SCOPE_COUNT_DRIFT")
    if first.get("model_form") != contract["model_contract"]["model_form"]:
        errors.append("HOLDOUT_REPLAY_MODEL_FORM_DRIFT")
    if first.get("model_version") != contract["model_contract"]["model_version"]:
        errors.append("HOLDOUT_REPLAY_MODEL_VERSION_DRIFT")
    if first.get("unique_source_identity_reads_actual") != first.get("unique_source_identity_reads_expected"):
        errors.append("HOLDOUT_REPLAY_SOURCE_READ_ACCOUNTING_DRIFT")
    if first.get("r2_profile_instances", 0) <= 0:
        errors.append("HOLDOUT_REPLAY_ZERO_PROFILES")

    for key in (
        "cross_checkpoint_comparison_count",
        "cross_signature_comparison_count",
        "scalar_score_count",
        "ranking_count",
        "global_winner_count",
        "historical_performance_metric_count",
        "realized_outcome_record_count",
        "phase3d_result_read_count",
        "future_return_read_count",
        "regret_read_count",
        "calibration_read_count",
    ):
        if first.get(key) != 0:
            errors.append("HOLDOUT_REPLAY_FORBIDDEN_ACTIVITY_NONZERO:" + key)

    if first.get("phase3d_r2_started") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_3D_R2")
    if first.get("phase3e_r2_started") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_3E_R2")
    if first.get("repeat_phase3f_started") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_REPEAT_3F")
    if first.get("phase3_historical_validation_complete") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_PHASE3_COMPLETE")
    if first.get("phase4_entry_allowed") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_PHASE4")

    acceptance = contract["acceptance_contract"]
    if first["audit_errors"]:
        expected_status = acceptance["fail_status"]
    elif first["transform_failure_instances"] > 0:
        expected_status = acceptance["fail_status"]
    elif (
        first["comparable_exact_signature_group_instances"] > 0
        and first["comparable_profile_instances"] > 0
    ):
        expected_status = acceptance["pass_status"]
    else:
        expected_status = acceptance["partial_status"]
    if first["status"] != expected_status:
        errors.append("HOLDOUT_REPLAY_STATUS_CLASSIFICATION_DRIFT")

    expected_3d_gate = first["status"] == acceptance["pass_status"]
    if first["phase3d_r2_start_allowed"] is not expected_3d_gate:
        errors.append("HOLDOUT_REPLAY_3D_R2_GATE_DRIFT")

    checkpoint_ids = [row["checkpoint_id"] for row in first["checkpoints"]]
    commit_ids = [row["canonical_commit_sha"] for row in first["checkpoints"]]
    if len(checkpoint_ids) != len(set(checkpoint_ids)):
        errors.append("HOLDOUT_REPLAY_DUPLICATE_CHECKPOINT_ID")
    if len(commit_ids) != len(set(commit_ids)):
        errors.append("HOLDOUT_REPLAY_DUPLICATE_CHECKPOINT_COMMIT")
    if len(checkpoint_ids) != parent["checkpoint_count"]:
        errors.append("HOLDOUT_REPLAY_CHECKPOINT_ACCOUNTING_DRIFT")

    for checkpoint in first["checkpoints"]:
        selected_ids = set(checkpoint["selected_evidence_ids"])
        for profile in checkpoint["profiles"]:
            if set(profile["provenance_evidence_ids"]) - selected_ids:
                errors.append(
                    "HOLDOUT_REPLAY_PROFILE_PROVENANCE_OUTSIDE_PACKET:"
                    + checkpoint["checkpoint_id"]
                    + ":"
                    + profile["security_id"]
                )
            for dim in profile["dimension_states"]:
                if set(dim.get("provenance_evidence_ids", [])) - selected_ids:
                    errors.append(
                        "HOLDOUT_REPLAY_DIMENSION_PROVENANCE_OUTSIDE_PACKET:"
                        + checkpoint["checkpoint_id"]
                        + ":"
                        + profile["security_id"]
                        + ":"
                        + dim["rule_id"]
                    )

    # Before closeout, replay is computed as a candidate while governed state still
    # says H2 not started. After closeout, bind state exactly to the observed result.
    if state.get("independent_holdout_replay_complete") is True:
        phase3d_r2_round1_downstream = (
            state.get("phase3d_r2_round1_evidence_audit_complete") is True
        )
        expected_state = {
            "holdout_h2_started": True,
            "independent_holdout_replay_complete": True,
            "independent_holdout_replay_outcome": first["status"],
            "independent_holdout_replay_sha256": first["replay_sha256"],
            "independent_holdout_replay_checkpoint_count": first["checkpoint_count"],
            "independent_holdout_replay_profile_count": first["r2_profile_instances"],
            "independent_holdout_replay_transform_failures": first["transform_failure_instances"],
            "independent_holdout_replay_audit_error_count": len(first["audit_errors"]),
            "independent_holdout_replay_comparable_groups": first["comparable_exact_signature_group_instances"],
            "independent_holdout_replay_comparable_profiles": first["comparable_profile_instances"],
            "phase3d_r2_start_allowed": first["phase3d_r2_start_allowed"],
            "phase3d_r2_started": True if phase3d_r2_round1_downstream else False,
            "phase3e_r2_started": False,
            "repeat_phase3f_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, expected in expected_state.items():
            if state.get(key) != expected:
                errors.append("HOLDOUT_REPLAY_STATE_DRIFT:" + key)
            if key in cv and cv.get(key) != expected:
                errors.append("HOLDOUT_REPLAY_CURRENT_VALIDATION_DRIFT:" + key)

        expected_current_phase = (
            "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"
            if phase3d_r2_round1_downstream
            else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE"
        )
        if current.get("current_phase") != expected_current_phase:
            errors.append("HOLDOUT_REPLAY_CURRENT_PHASE_DRIFT")
        expected_next = (
            "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION"
            if phase3d_r2_round1_downstream
            else (
                "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"
                if first["phase3d_r2_start_allowed"]
                else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_REVIEW"
            )
        )
        if current.get("next_phase") != expected_next:
            errors.append("HOLDOUT_REPLAY_NEXT_PHASE_DRIFT")
        if phase3d_r2_round1_downstream:
            if state.get("phase3d_r2_round1_contract_frozen") is not True:
                errors.append("HOLDOUT_REPLAY_R1_CONTRACT_NOT_FROZEN")
            if state.get("phase3d_r2_round1_outcome") != "PASS_R2_MEASURABILITY_CONTRACT_FROZEN_EVIDENCE_ACQUISITION_REQUIRED":
                errors.append("HOLDOUT_REPLAY_R1_OUTCOME_DRIFT")
            if state.get("phase3d_r2_measurability_status") != "PENDING_OUTCOME_EVIDENCE_ACQUISITION":
                errors.append("HOLDOUT_REPLAY_R1_MEASURABILITY_DRIFT")
            if state.get("phase3d_r2_outcome_evidence_acquisition_start_allowed") is not True:
                errors.append("HOLDOUT_REPLAY_R1_ACQUISITION_GATE_NOT_OPEN")
            if state.get("phase3d_r2_outcome_evidence_acquisition_started") is not False:
                errors.append("HOLDOUT_REPLAY_R1_PREMATURE_ACQUISITION")
            if state.get("phase3d_r2_performance_measurement_start_allowed") is not False:
                errors.append("HOLDOUT_REPLAY_R1_PREMATURE_PERFORMANCE")
    else:
        if state.get("holdout_h2_started") is not False:
            errors.append("HOLDOUT_REPLAY_STATE_PREMATURE_H2")
        if state.get("holdout_h2_start_allowed") is not True:
            errors.append("HOLDOUT_REPLAY_PARENT_GATE_NOT_OPEN_IN_STATE")
        if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY":
            errors.append("HOLDOUT_REPLAY_PREEXEC_NEXT_PHASE_DRIFT")

    for surface_name, surface in (
        ("CONTRACT", contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
        ("RESULT", first["controls"]),
    ):
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
        "PHASE3_R2_INDEPENDENT_HOLDOUT_REPLAY_ACCEPTANCE_RESULT "
        f"status={result['status']} checkpoints={result['checkpoint_count']} "
        f"profiles={result['r2_profile_instances']} present_dimensions={result['present_dimension_instances']} "
        f"missing_dimensions={result['missing_dimension_instances']} "
        f"transform_failures={result['transform_failure_instances']} "
        f"signatures={result['distinct_comparison_signature_count']} "
        f"groups={result['exact_signature_group_instances']} "
        f"comparable_groups={result['comparable_exact_signature_group_instances']} "
        f"comparable_profiles={result['comparable_profile_instances']} "
        f"pair_checks={result['pareto_directional_pair_checks']} "
        f"dominance_edges={result['dominance_edge_count']} "
        f"frontier_profiles={result['frontier_profile_instances']} "
        f"dominated_profiles={result['dominated_profile_instances']} "
        f"unsupported_evidence={result['unsupported_selected_evidence_instances']} "
        f"audit_errors={len(result['audit_errors'])} outcomes=0 performance=0 "
        f"phase3d_r2_start_allowed={str(result['phase3d_r2_start_allowed']).lower()} "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE"
    )
