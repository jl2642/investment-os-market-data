from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE4_FORWARD_SHADOW_VALIDATION_CONTRACT.json"


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if contract.get("status") != "CANDIDATE_FORWARD_SHADOW_CONTRACT_PRE_EXECUTION":
        errors.append("P4_CONTRACT_STATUS_DRIFT")

    parent = contract.get("parent_repeat_phase3f", {})
    expected_parent = {
        "pr": 332,
        "final_head": "b42c32446d5be923241a83e2bbe21d7e857317ac",
        "status": "COMPLETE_REPEAT_PHASE3F_R2_HISTORICAL_PROMOTION_GATE",
        "promotion_requirement_pass_count": 4,
        "promotion_requirement_total_count": 4,
        "gate_outcome": "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION",
        "gate_sha256": "af174d3adb0bb70afa306f26fa0c2a66eb925e04421962dcfae5573b404d22ec",
        "phase3_historical_validation_complete": True,
        "phase4_entry_allowed": True,
    }
    for key, value in expected_parent.items():
        if parent.get(key) != value:
            errors.append("P4_PARENT_REPEAT3F_DRIFT:" + key)

    runners = contract.get("runner_set", {})
    if runners.get("legacy", {}).get("model_form") != "LEGACY_POLICY_BASELINE":
        errors.append("P4_LEGACY_RUNNER_DRIFT")
    candidate = runners.get("candidate", {})
    if candidate.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("P4_R2_MODEL_DRIFT")
    if candidate.get("model_version") != "R2.0.1_RESEARCH":
        errors.append("P4_R2_VERSION_DRIFT")
    if candidate.get("comparison_method") != "PARETO_WITHIN_EXACT_COMPARISON_SIGNATURE":
        errors.append("P4_R2_COMPARISON_METHOD_DRIFT")
    if candidate.get("transform_rule_count") != 20:
        errors.append("P4_R2_TRANSFORM_COUNT_DRIFT")
    for key in ("scalar_policy_score_allowed", "dimension_weights_allowed", "cross_signature_dominance_allowed"):
        if candidate.get(key) is not False:
            errors.append("P4_R2_FORBIDDEN_TRUE:" + key)
    if runners.get("runner_set_may_change_during_phase4") is not False:
        errors.append("P4_RUNNER_SET_MUTABLE")
    if runners.get("material_candidate_revision_requires_restart") is not True:
        errors.append("P4_REVISION_RESTART_GUARD_MISSING")

    packet = contract.get("shared_parallel_packet_contract", {})
    for key in (
        "same_checkpoint_timestamp_required",
        "same_opportunity_set_required",
        "same_selected_evidence_required",
        "same_reference_asset_required",
        "exact_source_identity_required",
        "r2_transform_may_read_only_model_neutral_feature_row",
        "missingness_must_remain_explicit",
        "legacy_disposition_must_be_contemporaneously_recorded",
    ):
        if packet.get(key) is not True:
            errors.append("P4_SHARED_PACKET_TRUE_DRIFT:" + key)
    for key in (
        "model_specific_evidence_fetch_forbidden",
        "later_checkpoint_input_backfill_forbidden",
    ):
        if packet.get(key) is not True:
            errors.append("P4_SHARED_PACKET_FIREWALL_OPEN:" + key)
    for key in ("legacy_disposition_ordinal_mapping_created", "legacy_and_r2_global_winner_comparison_created"):
        if packet.get(key) is not False:
            errors.append("P4_LEGACY_R2_COMPARISON_OVERREACH:" + key)

    firewall = contract.get("future_evidence_firewall", {})
    if firewall.get("eligibility_cutoff_rule") != "SOURCE_AVAILABILITY_TIME_UTC_STRICTLY_AFTER_ACCEPTED_PHASE4_CONTRACT_FREEZE_HEAD_GIT_COMMIT_TIME":
        errors.append("P4_FUTURE_CUTOFF_DRIFT")
    for key in (
        "accepted_freeze_head_materialized_only_at_closeout",
        "selector",
        "checkpoint_deduplication_key",
    ):
        if not firewall.get(key):
            errors.append("P4_FUTURE_FIREWALL_MISSING:" + key)
    for key in (
        "pre_freeze_evidence_may_count_as_phase4",
        "historical_replay_may_substitute_for_phase4",
        "future_checkpoint_selection_may_use_realized_outcomes",
        "future_checkpoint_selection_may_use_r2_result_values",
        "future_checkpoint_selection_may_use_legacy_result_values",
        "manual_result_driven_checkpoint_selection_allowed",
    ):
        if firewall.get(key) is not False:
            errors.append("P4_FUTURE_FIREWALL_OPEN:" + key)
    for key in ("source_lineage_must_resolve_at_checkpoint", "checkpoint_packet_immutable_after_freeze", "outcomes_may_be_loaded_only_after_fixed_horizon_maturity"):
        if firewall.get(key) is not True:
            errors.append("P4_FUTURE_FIREWALL_TRUE_DRIFT:" + key)

    cycles = contract.get("parallel_cycle_definition", {})
    if cycles.get("all_discovered_cycles_must_be_audited") is not True:
        errors.append("P4_CENSUS_AUDIT_NOT_REQUIRED")
    if cycles.get("incomplete_cycles_may_be_silently_dropped") is not False:
        errors.append("P4_INCOMPLETE_CYCLE_DROP_ALLOWED")
    if cycles.get("model_output_failure_is_evidence_not_exclusion") is not True:
        errors.append("P4_MODEL_FAILURE_NOT_EVIDENCE")

    suff = contract.get("forward_sufficiency_gate", {})
    expected_suff = {
        "minimum_complete_economically_mature_parallel_cycles": 12,
        "minimum_distinct_utc_dates": 6,
        "minimum_distinct_iso_weeks": 4,
        "minimum_distinct_evidence_regimes": 4,
        "minimum_unique_securities": 6,
        "minimum_r2_profile_instances": 48,
        "minimum_distinct_r2_dominance_edges": 24,
        "minimum_distinct_comparison_signatures": 2,
        "minimum_distinct_edges_per_observed_signature": 6,
        "all_discovered_eligible_cycles_audited": True,
        "all_counted_cycles_have_both_parallel_outputs": True,
        "thresholds_may_change_after_forward_results": False,
    }
    for key, value in expected_suff.items():
        if suff.get(key) != value:
            errors.append("P4_SUFFICIENCY_DRIFT:" + key)

    measurement = contract.get("economic_measurement_contract", {})
    if measurement.get("fixed_horizon_exchange_trading_sessions") != [1, 3, 5]:
        errors.append("P4_HORIZON_DRIFT")
    if measurement.get("edge_metric") != "DOMINATOR_RETURN_MINUS_DOMINATED_RETURN":
        errors.append("P4_EDGE_METRIC_DRIFT")
    if measurement.get("edge_concordance") != "DOMINATOR_RETURN_GTE_DOMINATED_RETURN":
        errors.append("P4_CONCORDANCE_DRIFT")
    for key in (
        "benchmark_adjusted_return_in_v1",
        "fx_translation_in_v1",
        "portfolio_pnl_in_v1",
        "sharpe_in_v1",
        "statistical_significance_required_for_v1_gate",
        "p_value_gate_allowed",
    ):
        if measurement.get(key) is not False:
            errors.append("P4_MEASUREMENT_SCOPE_EXPANDED:" + key)

    summaries = contract.get("mandatory_forward_summaries", {})
    if summaries.get("aggregation_schemes") != ["EQUAL_EDGE", "EQUAL_CHECKPOINT", "EQUAL_SIGNATURE"]:
        errors.append("P4_AGGREGATION_SCHEME_DRIFT")
    if summaries.get("per_horizon_metrics") != ["CONCORDANCE_RATE", "MEAN_EDGE_RETURN_SPREAD"]:
        errors.append("P4_FORWARD_METRIC_DRIFT")
    for key in ("signature_stratum_summaries_required", "leave_one_security_out_required", "leave_one_signature_out_required", "legacy_disposition_return_context_required", "legacy_disposition_return_context_is_descriptive_only"):
        if summaries.get(key) is not True:
            errors.append("P4_SUMMARY_REQUIREMENT_DRIFT:" + key)
    if summaries.get("legacy_disposition_ordinalization_forbidden") is not True:
        errors.append("P4_LEGACY_ORDINALIZATION_GUARD_MISSING")

    gate = contract.get("phase4_to_phase5_gate", {})
    expected_outcomes = {
        "PASS_PHASE4_FORWARD_VALIDATION_ELIGIBLE_FOR_PHASE5_PROPOSAL",
        "CONTINUE_PHASE4_FORWARD_SHADOW_VALIDATION",
        "FAIL_R2_FORWARD_VALIDATION_RETURN_TO_PHASE3_RESEARCH",
        "FAIL_PHASE4_INTEGRITY_RESTART_REQUIRED",
    }
    if set(gate.get("completion_outcomes", [])) != expected_outcomes:
        errors.append("P4_OUTCOME_SET_DRIFT")
    direction = gate.get("directional_requirements", {})
    if direction.get("apply_to_every_fixed_horizon") is not True or direction.get("apply_to_every_aggregation_scheme") is not True:
        errors.append("P4_DIRECTION_SCOPE_WEAKENED")
    if float(direction.get("minimum_concordance_rate", -1)) != 0.5:
        errors.append("P4_CONCORDANCE_THRESHOLD_DRIFT")
    if float(direction.get("minimum_mean_edge_return_spread", -1)) != 0.0:
        errors.append("P4_SPREAD_THRESHOLD_DRIFT")
    if direction.get("each_supported_signature_stratum_must_independently_pass") is not True:
        errors.append("P4_SIGNATURE_DIRECTION_GATE_WEAKENED")
    if direction.get("minimum_edges_for_supported_signature_stratum") != 6:
        errors.append("P4_SIGNATURE_MIN_EDGE_DRIFT")

    sec = gate.get("security_robustness_requirement", {})
    if sec.get("minimum_retained_edges_for_evaluable_jackknife") != 12:
        errors.append("P4_SECURITY_JACKKNIFE_MIN_DRIFT")
    for key in ("leave_one_security_out_must_be_evaluated", "every_evaluable_security_jackknife_must_pass_equal_edge_directional_requirements", "insufficient_retained_edges_blocks_completion_instead_of_counting_as_pass"):
        if sec.get(key) is not True:
            errors.append("P4_SECURITY_JACKKNIFE_GUARD_DRIFT:" + key)

    sig = gate.get("signature_robustness_requirement", {})
    if sig.get("minimum_retained_edges_for_evaluable_jackknife") != 6:
        errors.append("P4_SIGNATURE_JACKKNIFE_MIN_DRIFT")
    for key in ("leave_one_signature_out_must_be_evaluated", "every_evaluable_signature_jackknife_must_pass_equal_edge_directional_requirements", "insufficient_retained_edges_blocks_completion_instead_of_counting_as_pass"):
        if sig.get(key) is not True:
            errors.append("P4_SIGNATURE_JACKKNIFE_GUARD_DRIFT:" + key)

    if gate.get("pass_does_not_authorize_migration") is not True:
        errors.append("P4_PASS_AUTO_MIGRATION_GUARD_MISSING")
    if gate.get("pass_only_authorizes_separate_phase5_migration_proposal") is not True:
        errors.append("P4_PHASE5_PROPOSAL_BOUNDARY_MISSING")

    boundary = contract.get("candidate_state_boundary", {})
    expected_boundary = {
        "contract_freeze_closeout_applied": False,
        "phase4_contract_frozen": False,
        "phase4_started": False,
        "phase4_forward_observation_count": 0,
        "phase4_realized_outcome_read_count": 0,
        "phase4_complete": False,
        "phase5_migration_allowed": False,
    }
    for key, value in expected_boundary.items():
        if boundary.get(key) != value:
            errors.append("P4_CANDIDATE_BOUNDARY_DRIFT:" + key)

    auth = contract.get("authority_boundaries", {})
    for key, value in auth.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("P4_TRADE_AUTHORITY_DRIFT")
        elif value != 0:
            errors.append("P4_AUTHORITY_NONZERO:" + key)

    return sorted(set(errors))


def validate() -> list[str]:
    errors = list(validate_program_consistency())
    contract = load_contract()
    errors.extend(validate_contract(contract))

    state = _load("PROGRAM_STATE.json")
    current = _load("CURRENT_PHASE_STATUS.json")
    cv = current.get("validation", {})
    r2 = _load("PHASE3B_R2_MODEL_CONTRACT.json")
    repeat = _load("REPEAT_PHASE3F_R2_VALIDATION.json")
    program = _load("PROGRAM_CONTRACT.json")

    if state.get("repeat_phase3f_complete") is not True:
        errors.append("P4_PARENT_REPEAT3F_NOT_COMPLETE")
    if state.get("repeat_phase3f_gate_outcome") != "PROMOTE_TO_PHASE_4_FORWARD_VALIDATION":
        errors.append("P4_PARENT_GATE_OUTCOME_DRIFT")
    if state.get("repeat_phase3f_gate_sha256") != contract["parent_repeat_phase3f"]["gate_sha256"]:
        errors.append("P4_PARENT_GATE_SHA_DRIFT")
    if state.get("phase3_historical_validation_complete") is not True:
        errors.append("P4_PHASE3_NOT_COMPLETE")
    if state.get("phase4_entry_allowed") is not True or state.get("phase4_start_allowed") is not True:
        errors.append("P4_ENTRY_NOT_ALLOWED")
    if state.get("phase4_started") is not False:
        errors.append("P4_PREMATURE_START")
    if state.get("phase4_forward_validation_complete") is not False:
        errors.append("P4_PREMATURE_COMPLETE")
    if state.get("phase5_migration_allowed") is not False:
        errors.append("P4_PREMATURE_PHASE5")
    if current.get("next_phase") != "PHASE_4_FORWARD_PARALLEL_SHADOW_VALIDATION":
        errors.append("P4_CURRENT_NEXT_PHASE_DRIFT")
    if cv.get("phase4_entry_allowed") is not True or cv.get("phase4_started") is not False:
        errors.append("P4_CURRENT_BOUNDARY_DRIFT")

    if r2.get("model", {}).get("model_form") != contract["runner_set"]["candidate"]["model_form"]:
        errors.append("P4_R2_CONTRACT_MODEL_MISMATCH")
    if r2.get("model", {}).get("model_version") != contract["runner_set"]["candidate"]["model_version"]:
        errors.append("P4_R2_CONTRACT_VERSION_MISMATCH")
    if len(r2.get("transform_catalog", [])) != 20:
        errors.append("P4_R2_CONTRACT_TRANSFORM_COUNT_MISMATCH")
    if repeat.get("gate", {}).get("gate_sha256") != contract["parent_repeat_phase3f"]["gate_sha256"]:
        errors.append("P4_REPEAT_VALIDATION_SHA_MISMATCH")
    if repeat.get("gate", {}).get("promotion_requirement_pass_count") != 4:
        errors.append("P4_REPEAT_VALIDATION_PASS_COUNT_MISMATCH")

    if program.get("mandatory_gates", {}).get("phase4_forward_validation_required_for_phase5") is not True:
        errors.append("P4_PROGRAM_PHASE5_GATE_MISSING")
    authority = program.get("authority_boundaries_through_phase4", {})
    if authority.get("order_authorized") is not False or authority.get("orders") != 0 or authority.get("trade_authority") != "NONE":
        errors.append("P4_PROGRAM_AUTHORITY_DRIFT")

    if state.get("orders") != 0 or current.get("orders") != 0:
        errors.append("P4_ORDER_AUTHORITY_DRIFT")
    if state.get("trade_authority") != "NONE" or current.get("trade_authority") != "NONE":
        errors.append("P4_TRADE_AUTHORITY_CHANGED")

    return sorted(set(errors))


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    print(
        "PHASE4_FORWARD_SHADOW_CONTRACT_ACCEPTANCE "
        "status=CANDIDATE_FORWARD_SHADOW_CONTRACT_PRE_EXECUTION "
        "future_cutoff=ACCEPTED_FREEZE_HEAD_COMMIT_TIME "
        "runners=LEGACY_POLICY_BASELINE+R2.0.1_RESEARCH "
        "min_cycles=12 min_weeks=4 min_edges=24 min_signatures=2 "
        "horizons=1,3,5 aggregation=equal_edge,equal_checkpoint,equal_signature "
        "phase4_started=false phase5=false orders=0 trade_authority=NONE"
    )
