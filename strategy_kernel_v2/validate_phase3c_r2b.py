from __future__ import annotations

import json
from pathlib import Path

from strategy_kernel_v2.phase3b_r2_contract import (
    load_contract as load_r2_contract,
    validate_contract as validate_r2_contract,
)
from strategy_kernel_v2.phase3c_r2a_reconstruction import (
    build_default as build_r2a_default,
    load_replay_contract as load_r2a_contract,
    validate_replay_contract as validate_r2a_contract,
)
from strategy_kernel_v2.phase3c_r2b_replay import (
    _classify,
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
    r2_contract = load_r2_contract()
    r2a_contract = load_r2a_contract()
    r2b_contract = load_replay_contract()
    errors.extend(validate_r2_contract(r2_contract))
    errors.extend(validate_r2a_contract(r2a_contract))
    errors.extend(validate_replay_contract(r2b_contract))

    r2a_first = build_r2a_default(ROOT.parent)
    r2a_second = build_r2a_default(ROOT.parent)
    if (
        r2a_first != r2a_second
        or r2a_first["reconstruction_sha256"] != r2a_second["reconstruction_sha256"]
    ):
        errors.append("R2B_PARENT_R2A_NONDETERMINISTIC")
    if r2a_first["reconstruction_sha256"] != r2b_contract["parent_r2a_reconstruction_sha256"]:
        errors.append("R2B_PARENT_R2A_SHA_DRIFT")

    first = build_default(ROOT.parent)
    second = build_default(ROOT.parent)
    if first != second or first["replay_sha256"] != second["replay_sha256"]:
        errors.append("R2B_NONDETERMINISTIC_REPLAY")

    parent = r2b_contract["parent_acceptance"]
    exact_parent = {
        "checkpoint_count": parent["checkpoint_count"],
        "unique_registered_historical_source_reads": parent["unique_registered_historical_source_reads"],
        "profile_count": parent["r2_profile_instances"],
        "transform_failure_instances": parent["transform_failure_instances"],
        "historical_performance_metric_count": 0,
        "realized_outcome_record_count": 0,
        "holdout_checkpoint_count": 0,
        "outcome_tuning_count": 0,
        "cross_checkpoint_comparison_count": 0,
        "cross_signature_comparison_count": 0,
        "unmapped_context_comparison_use_count": 0,
    }
    for key, expected in exact_parent.items():
        if first.get(key) != expected:
            errors.append(f"R2B_ACCEPTANCE_MISMATCH:{key}:{first.get(key)}:{expected}")

    expected_status = _classify(
        list(first.get("audit", {}).get("errors", [])),
        int(first.get("comparable_exact_signature_group_instances", 0)),
        int(first.get("comparable_profile_instances", 0)),
    )
    if first.get("status") != expected_status:
        errors.append("R2B_CLASSIFICATION_MISMATCH")
    if first.get("audit", {}).get("passed") is not True:
        errors.append(
            "R2B_FULL_AUDIT_FAILED:"
            + json.dumps(first.get("audit", {}).get("errors", []), ensure_ascii=False)
        )
    if first.get("status") != "PASS_MECHANICAL_REPLAY_OPERATIONAL":
        errors.append("R2B_NOT_OPERATIONAL_ON_DEVELOPMENT_CORPUS")
    if first.get("comparable_exact_signature_group_instances", 0) <= 0:
        errors.append("R2B_NO_COMPARABLE_EXACT_SIGNATURE_GROUP")
    if first.get("comparable_profile_instances", 0) <= 0:
        errors.append("R2B_NO_COMPARABLE_PROFILE_INSTANCE")
    if first.get("pareto_directional_pair_checks", 0) <= 0:
        errors.append("R2B_NO_MECHANICAL_PARETO_PAIR_CHECKS")

    if first.get("mechanical_replay_executed") is not True:
        errors.append("R2B_MECHANICAL_REPLAY_NOT_EXECUTED")
    if first.get("development_corpus_replay_complete") is not True:
        errors.append("R2B_DEVELOPMENT_CORPUS_REPLAY_NOT_COMPLETE")
    if first.get("historical_performance_claimed") is not False:
        errors.append("R2B_HISTORICAL_PERFORMANCE_CLAIMED")
    if first.get("ranking_generated") is not False:
        errors.append("R2B_RANKING_GENERATED")
    if first.get("global_winner_selected") is not False:
        errors.append("R2B_GLOBAL_WINNER_SELECTED")
    if first.get("target_weights_generated") is not False:
        errors.append("R2B_TARGET_WEIGHTS_GENERATED")
    if first.get("local_pareto_frontier_is_global_winner") is not False:
        errors.append("R2B_LOCAL_FRONTIER_MISREPRESENTED_AS_GLOBAL_WINNER")
    if first.get("independent_holdout_start_allowed") is not True:
        errors.append("R2B_HOLDOUT_NOT_UNLOCKED_AFTER_PASS")
    if first.get("independent_holdout_started") is not False:
        errors.append("R2B_HOLDOUT_PREMATURELY_STARTED")
    if first.get("phase3_historical_validation_complete") is not False:
        errors.append("R2B_PHASE3_PREMATURELY_COMPLETE")
    if first.get("phase4_entry_allowed") is not False:
        errors.append("R2B_PREMATURE_PHASE4")

    for checkpoint in first.get("checkpoints", []):
        status_rows = checkpoint.get("profile_replay_status", [])
        if len(status_rows) != checkpoint.get("profile_count"):
            errors.append("R2B_CHECKPOINT_PROFILE_STATUS_ACCOUNTING_MISMATCH:" + checkpoint["decision_point_id"])
        for row in status_rows:
            if row.get("status") == "EVALUABLE_AWAITING_SIGNATURE_GROUP":
                errors.append("R2B_EVALUABLE_PROFILE_LEFT_UNGROUPED:" + checkpoint["decision_point_id"])
        for group in checkpoint.get("exact_signature_groups", []):
            member_ids = set(group.get("security_ids", []))
            if group.get("status") == "COMPARABLE_EXACT_SIGNATURE":
                if len(member_ids) < 2:
                    errors.append("R2B_COMPARABLE_GROUP_TOO_SMALL:" + checkpoint["decision_point_id"])
                if set(group.get("pareto_frontier", [])) - member_ids:
                    errors.append("R2B_FRONTIER_OUTSIDE_GROUP:" + checkpoint["decision_point_id"])
                for sid, dominators in group.get("dominated_by", {}).items():
                    if sid not in member_ids or set(dominators) - member_ids:
                        errors.append("R2B_DOMINANCE_RELATION_OUTSIDE_GROUP:" + checkpoint["decision_point_id"])
            elif group.get("status") == "INSUFFICIENT_GROUP_SIZE":
                if len(member_ids) >= 2:
                    errors.append("R2B_SINGLETON_GROUP_SIZE_DRIFT:" + checkpoint["decision_point_id"])
            else:
                errors.append("R2B_UNKNOWN_GROUP_STATUS:" + checkpoint["decision_point_id"])

    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    cv = current["validation"]

    holdout_h1_downstream = state.get("holdout_h1_started") is True
    holdout_replay_downstream = state.get("independent_holdout_replay_complete") is True
    phase3d_r2_downstream = state.get("phase3d_r2_started") is True
    expected_state = {
        "r2_phase3c_replay_start_allowed": True,
        "r2_phase3c_replay_started": True,
        "r2_phase3c_replay_complete": True,
        "r2_phase3c_r2a_complete": True,
        "r2_phase3c_r2b_start_allowed": True,
        "r2_phase3c_r2b_started": True,
        "r2_phase3c_r2b_complete": True,
        "r2_real_historical_replay_executed": True,
        "r2_historical_replay_coverage_claimed": True,
        "r2_historical_performance_claimed": False,
        "r2_phase3c_r2b_mechanical_pareto_executed": True,
        "r2_phase3c_r2b_realized_outcomes_loaded": False,
        "r2_phase3c_r2b_holdout_started": False,
        "r2_independent_holdout_start_allowed": True,
        "holdout_build_started": True if holdout_h1_downstream else False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    for key, expected in expected_state.items():
        if state.get(key) is not expected:
            errors.append("R2B_STATE_DRIFT:" + key)

    if state.get("r2_phase3c_r2b_outcome") != first.get("status"):
        errors.append("R2B_STATE_OUTCOME_MISMATCH")
    count_fields = {
        "r2_phase3c_r2b_exact_signature_group_instances": "exact_signature_group_instances",
        "r2_phase3c_r2b_comparable_group_count": "comparable_exact_signature_group_instances",
        "r2_phase3c_r2b_singleton_group_count": "singleton_signature_group_instances",
        "r2_phase3c_r2b_comparable_profile_instances": "comparable_profile_instances",
        "r2_phase3c_r2b_pareto_directional_pair_checks": "pareto_directional_pair_checks",
        "r2_phase3c_r2b_dominance_edges": "dominance_edge_count",
        "r2_phase3c_r2b_frontier_profile_instances": "frontier_profile_instances",
        "r2_phase3c_r2b_dominated_profile_instances": "dominated_profile_instances",
    }
    for state_key, result_key in count_fields.items():
        if state.get(state_key) != first.get(result_key):
            errors.append("R2B_STATE_COUNT_MISMATCH:" + state_key)

    if holdout_h1_downstream:
        if state.get("holdout_h1_complete") is not True:
            errors.append("R2B_LEGAL_HOLDOUT_H1_STATE_INVALID")
        if holdout_replay_downstream:
            if state.get("holdout_h2_started") is not True:
                errors.append("R2B_LEGAL_HOLDOUT_REPLAY_STATE_INVALID")
            if phase3d_r2_downstream:
                if state.get("phase3d_r2_round1_complete") is not True:
                    errors.append("R2B_PHASE3D_R2_ROUND1_NOT_COMPLETE")
                if state.get("phase3d_r2_round1_status") != "PARTIAL_R2_MEASURABILITY_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED":
                    errors.append("R2B_PHASE3D_R2_ROUND1_STATUS_DRIFT")
                if state.get("phase3d_r2_performance_started") is not bool(state.get("phase3d_r2_performance_measurement_complete")):
                    errors.append("R2B_PHASE3D_R2_PREMATURE_PERFORMANCE")
        elif state.get("holdout_h2_started") is not False:
            errors.append("R2B_LEGAL_HOLDOUT_H1_PREMATURE_H2")
        expected_current_phase = (
            "PHASE_3D_R2_MEASURABILITY_AND_PERFORMANCE_IF_SUPPORTED"
            if phase3d_r2_downstream
            else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE"
        )
        if current.get("current_phase") != expected_current_phase:
            errors.append("R2B_CURRENT_HOLDOUT_H1_PHASE_MISMATCH")
        holdout_v2_pass = (
            state.get("holdout_v2_selection_complete") is True
            and state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
        )
        expected_next = (
            (
                (
                    "PHASE_3E_R2_STRUCTURAL_SUPPORT_GATE_CONTRACT"
                    if state.get("phase3d_r2_performance_measurement_complete") is True
                    else "PHASE_3D_R2_PERFORMANCE_MEASUREMENT"
                )
                if state.get("phase3d_r2_outcome_evidence_acquisition_complete") is True
                else "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION"
            )
            if phase3d_r2_downstream
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
        expected_status = (
            (
                "PHASE3D_R2_PERFORMANCE_COMPLETE_3E_SUPPORT_GATE_REQUIRED_PHASE4_BLOCKED"
                if state.get("phase3d_r2_performance_measurement_complete") is True
                else (
                    "PHASE3D_R2_OUTCOME_EVIDENCE_COMPLETE_PERFORMANCE_READY_PHASE4_BLOCKED"
                    if state.get("phase3d_r2_outcome_evidence_acquisition_complete") is True
                    else "PHASE3D_R2_ROUND1_PARTIAL_OUTCOME_EVIDENCE_ACQUISITION_REQUIRED_PHASE4_BLOCKED"
                )
            )
            if phase3d_r2_downstream
            else (
                "INDEPENDENT_HOLDOUT_REPLAY_PASS_PHASE3D_R2_READY_PHASE4_BLOCKED"
                if holdout_replay_downstream
                else (
                    "V2_SELECTION_SUFFICIENT_H2_READY_PHASE4_BLOCKED"
                    if holdout_v2_pass
                    else "H1_SELECTION_INSUFFICIENT_COVERAGE_EXPANSION_REQUIRED_H2_BLOCKED_PHASE4_BLOCKED"
                )
            )
        )
        if current.get("next_phase") != expected_next:
            errors.append("R2B_CURRENT_HOLDOUT_NEXT_PHASE_MISMATCH")
        if current.get("status") != expected_status:
            errors.append("R2B_CURRENT_HOLDOUT_STATUS_MISMATCH")
    else:
        if current.get("current_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
            errors.append("R2B_CURRENT_PHASE_MISMATCH")
        if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
            errors.append("R2B_NEXT_PHASE_MISMATCH")
        if current.get("status") != "R2_MECHANICAL_REPLAY_COMPLETE_READY_FOR_INDEPENDENT_HOLDOUT_PHASE4_BLOCKED":
            errors.append("R2B_CURRENT_STATUS_MISMATCH")

    current_expected = {
        "r2_phase3c_replay_started": True,
        "r2_phase3c_replay_complete": True,
        "r2_phase3c_r2a_complete": True,
        "r2_phase3c_r2b_start_allowed": True,
        "r2_phase3c_r2b_started": True,
        "r2_phase3c_r2b_complete": True,
        "r2_real_historical_replay_executed": True,
        "r2_historical_replay_coverage_claimed": True,
        "r2_historical_performance_claimed": False,
        "r2_phase3c_r2b_mechanical_pareto_executed": True,
        "r2_phase3c_r2b_realized_outcomes_loaded": False,
        "r2_phase3c_r2b_holdout_started": False,
        "r2_independent_holdout_start_allowed": True,
        "holdout_build_started": True if holdout_h1_downstream else False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    for key, expected in current_expected.items():
        if cv.get(key) is not expected:
            errors.append("R2B_CURRENT_VALIDATION_DRIFT:" + key)
    if cv.get("r2_phase3c_r2b_outcome") != first.get("status"):
        errors.append("R2B_CURRENT_OUTCOME_MISMATCH")
    for state_key, result_key in count_fields.items():
        current_key = state_key
        if cv.get(current_key) != first.get(result_key):
            errors.append("R2B_CURRENT_COUNT_MISMATCH:" + current_key)

    for surface_name, surface in [
        ("CONTRACT", r2b_contract["authority_boundaries"]),
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
        "PHASE3C_R2B_ACCEPTANCE_PASS "
        f"status={result['status']} checkpoints={result['checkpoint_count']} profiles={result['profile_count']} "
        f"comparison_evaluable={result['comparison_contract_evaluable_profiles']} "
        f"signature_groups={result['exact_signature_group_instances']} "
        f"comparable_groups={result['comparable_exact_signature_group_instances']} "
        f"singleton_groups={result['singleton_signature_group_instances']} "
        f"comparable_profiles={result['comparable_profile_instances']} "
        f"pair_checks={result['pareto_directional_pair_checks']} "
        f"dominance_edges={result['dominance_edge_count']} "
        f"frontier_instances={result['frontier_profile_instances']} "
        f"dominated_instances={result['dominated_profile_instances']} "
        "outcomes=0 holdout=0 holdout_start_allowed=true "
        "phase3_historical_validation_complete=false phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
