from __future__ import annotations

import json
from pathlib import Path
import subprocess

from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json"


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _git_commit_exists(sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=ROOT.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _git_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def validate() -> list[str]:
    errors = list(validate_program_consistency())
    contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")
    decision_points = load("PHASE3A_DECISION_POINTS.json")["decision_points"]
    post3f = load("PHASE3_POST3F_RESEARCH_PATH_DECISION.json")

    if contract.get("status") != "FROZEN_BEFORE_HOLDOUT_SELECTION_OR_R2_REPLAY_WITH_PRESELECTION_FEASIBILITY_CORRECTION":
        errors.append("HOLDOUT_H0_CONTRACT_NOT_FROZEN")
    if contract.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("HOLDOUT_H0_MODEL_IDENTITY_DRIFT")
    if contract.get("model_version") != "R2.0.1_RESEARCH":
        errors.append("HOLDOUT_H0_MODEL_VERSION_DRIFT")

    identity = contract.get("holdout_identity", {})
    if identity.get("holdout_is_macro_phase") is not False:
        errors.append("HOLDOUT_H0_MACRO_PHASE_DRIFT")
    if identity.get("holdout_is_phase3g") is not False:
        errors.append("HOLDOUT_H0_PHASE3G_DRIFT")
    if identity.get("holdout_is_direct_phase4_gate") is not False:
        errors.append("HOLDOUT_H0_DIRECT_PHASE4_DRIFT")
    if identity.get("seven_seed_checkpoints_are_development_only") is not True:
        errors.append("HOLDOUT_H0_SEED_FIREWALL_MISSING")

    universe = contract.get("frozen_repository_universe", {})
    start_sha = universe.get("start_commit_inclusive")
    end_sha = universe.get("end_commit_inclusive")
    if universe.get("source_branch") != "main":
        errors.append("HOLDOUT_H0_SOURCE_BRANCH_DRIFT")
    if universe.get("source_branch_must_be_protected") is not True:
        errors.append("HOLDOUT_H0_PROTECTED_MAIN_NOT_REQUIRED")
    if universe.get("open_pr_heads_allowed") is not False:
        errors.append("HOLDOUT_H0_OPEN_PR_EVIDENCE_ALLOWED")
    if universe.get("future_commits_may_enter_v1_holdout") is not False:
        errors.append("HOLDOUT_H0_UNIVERSE_NOT_FROZEN")
    if state.get("canonical_main_sha") != end_sha or current.get("canonical_main_sha") != end_sha:
        errors.append("HOLDOUT_H0_FROZEN_MAIN_HEAD_MISMATCH")
    for sha, label in ((start_sha, "START"), (end_sha, "END")):
        if not isinstance(sha, str) or not _git_commit_exists(sha):
            errors.append("HOLDOUT_H0_UNKNOWN_" + label + "_COMMIT")
    if isinstance(start_sha, str) and isinstance(end_sha, str):
        if _git_commit_exists(start_sha) and _git_commit_exists(end_sha) and not _git_is_ancestor(start_sha, end_sha):
            errors.append("HOLDOUT_H0_UNIVERSE_NOT_ON_SINGLE_MAIN_ANCESTRY")

    seed = contract.get("seed_firewall", {})
    expected_ids = [row["decision_point_id"] for row in decision_points]
    expected_shas = [row["canonical_commit_sha"] for row in decision_points]
    if seed.get("excluded_checkpoint_ids") != expected_ids:
        errors.append("HOLDOUT_H0_SEED_CHECKPOINT_SET_DRIFT")
    if seed.get("excluded_commit_shas") != expected_shas:
        errors.append("HOLDOUT_H0_SEED_COMMIT_SET_DRIFT")
    if len(set(expected_ids)) != 7 or len(set(expected_shas)) != 7:
        errors.append("HOLDOUT_H0_SEED_CARDINALITY_DRIFT")
    if seed.get("seed_first_at") != decision_points[0]["at"]:
        errors.append("HOLDOUT_H0_SEED_FIRST_TIME_DRIFT")
    if seed.get("seed_last_at") != decision_points[-1]["at"]:
        errors.append("HOLDOUT_H0_SEED_LAST_TIME_DRIFT")
    for sha in expected_shas:
        if not _git_commit_exists(sha):
            errors.append("HOLDOUT_H0_SEED_COMMIT_MISSING:" + sha)
        elif isinstance(end_sha, str) and _git_commit_exists(end_sha) and not _git_is_ancestor(sha, end_sha):
            errors.append("HOLDOUT_H0_SEED_NOT_ON_FROZEN_MAIN_ANCESTRY:" + sha)
    for key in (
        "exact_seed_commit_reuse_forbidden",
        "exact_seed_source_identity_set_reuse_forbidden",
        "seed_checkpoint_relabeling_forbidden",
        "same_seed_outcome_tuning_as_holdout_forbidden",
    ):
        if seed.get(key) is not True:
            errors.append("HOLDOUT_H0_SEED_FIREWALL_FALSE:" + key)

    original_requirements = post3f.get("holdout_coverage_contract_requirements", {})
    required_mapping = {
        "disjoint_from_seven_seed_checkpoints": seed.get("exact_seed_commit_reuse_forbidden") is True,
        "checkpoint_selection_may_use_realized_outcomes": contract["outcome_and_model_firewall"].get("realized_outcomes_may_be_read_during_selection"),
        "point_in_time_availability_provenance_required": contract["point_in_time_provenance"].get("every_evidence_row_requires_available_at_or_before_checkpoint"),
        "exact_source_identity_required": contract["point_in_time_provenance"].get("every_evidence_row_requires_exact_source_commit_or_blob_identity"),
        "later_evidence_backfill_forbidden": contract["point_in_time_provenance"].get("later_evidence_backfill_forbidden"),
        "coverage_must_expand_dates_or_regimes_beyond_current_seed": contract["quantitative_sufficiency_gate"].get("minimum_checkpoints_strictly_outside_seed_time_span", 0) > 0,
        "quantitative_sufficiency_threshold_must_be_frozen_before_holdout_results": contract["quantitative_sufficiency_gate"].get("threshold_change_after_holdout_selection_or_replay_result_forbidden"),
    }
    for key, required in original_requirements.items():
        if required is True and required_mapping.get(key) is not True:
            errors.append("HOLDOUT_H0_POST3F_REQUIREMENT_NOT_PRESERVED:" + key)
        if key == "checkpoint_selection_may_use_realized_outcomes" and required is False:
            if required_mapping.get(key) is not False:
                errors.append("HOLDOUT_H0_OUTCOME_BLINDNESS_DRIFT")

    selector = contract.get("deterministic_selector", {})
    if selector.get("mode") != "CENSUS_OF_ALL_ELIGIBLE_DISTINCT_DECISION_EVIDENCE_FINGERPRINTS":
        errors.append("HOLDOUT_H0_SELECTOR_MODE_DRIFT")
    for key in (
        "eligible_commit_must_be_on_frozen_main_ancestry",
        "eligible_commit_must_be_within_frozen_universe",
        "eligible_commit_must_not_be_seed_commit",
        "candidate_state_must_exist",
        "opportunity_security_set_must_be_nonempty",
        "fingerprint_must_differ_from_previous_selected_checkpoint",
        "pure_docs_ci_or_infrastructure_change_without_fingerprint_change_is_not_checkpoint",
        "all_eligible_distinct_fingerprints_must_be_selected",
        "regime_definition_may_not_use_prices_returns_or_outcomes",
    ):
        if selector.get(key) is not True:
            errors.append("HOLDOUT_H0_SELECTOR_GUARD_FALSE:" + key)
    for key in ("discretionary_subsampling_allowed", "random_sampling_allowed", "manual_cherry_pick_allowed"):
        if selector.get(key) is not False:
            errors.append("HOLDOUT_H0_SELECTOR_CHERRY_PICK_RISK:" + key)

    firewall = contract.get("outcome_and_model_firewall", {})
    for key in (
        "realized_outcomes_may_be_read_during_selection",
        "phase3d_results_may_be_read_during_selection",
        "r2_profile_values_may_be_computed_during_selection",
        "r2_pareto_replay_may_run_during_selection",
        "r2_replayability_status_may_influence_selection",
        "future_return_may_influence_selection",
        "regret_or_calibration_may_influence_selection",
        "manual_include_or_exclude_based_on_expected_model_behavior",
    ):
        if firewall.get(key) is not False:
            errors.append("HOLDOUT_H0_FIREWALL_OPEN:" + key)
    if firewall.get("selector_changes_after_first_holdout_r2_result_forbidden") is not True:
        errors.append("HOLDOUT_H0_POST_RESULT_SELECTOR_CHANGE_NOT_FORBIDDEN")

    q = contract.get("quantitative_sufficiency_gate", {})
    expected_thresholds = {
        "minimum_holdout_checkpoints": 12,
        "minimum_distinct_utc_dates": 6,
        "minimum_distinct_iso_weeks": 4,
        "minimum_distinct_evidence_regime_signatures": 4,
        "minimum_unique_securities": 6,
        "minimum_opportunity_profile_instances": 48,
        "minimum_checkpoints_strictly_outside_seed_time_span": 1,
        "maximum_single_utc_date_fraction": 0.40,
        "maximum_single_evidence_regime_fraction": 0.50,
    }
    for key, expected in expected_thresholds.items():
        if q.get(key) != expected:
            errors.append(f"HOLDOUT_H0_THRESHOLD_DRIFT:{key}:{q.get(key)}:{expected}")
    if q.get("all_thresholds_must_pass") is not True:
        errors.append("HOLDOUT_H0_THRESHOLDS_NOT_CONJUNCTIVE")
    if q.get("threshold_change_after_holdout_selection_or_replay_result_forbidden") is not True:
        errors.append("HOLDOUT_H0_THRESHOLD_TUNING_NOT_FORBIDDEN")
    amendments = contract.get("amendment_history", [])
    if len(amendments) != 1:
        errors.append("HOLDOUT_H0_AMENDMENT_HISTORY_DRIFT")
    else:
        amendment = amendments[0]
        if amendment.get("amendment_id") != "H0_1_PRESELECTION_OUTSIDE_SEED_FEASIBILITY_CORRECTION":
            errors.append("HOLDOUT_H0_AMENDMENT_ID_DRIFT")
        for key in ("h1_selection_started", "holdout_ledger_observed", "r2_holdout_replay_observed", "realized_outcomes_observed", "outcome_or_model_tuning"):
            if amendment.get(key) is not False:
                errors.append("HOLDOUT_H0_AMENDMENT_NOT_PRESELECTION_CLEAN:" + key)
        if amendment.get("prior_value") != 2 or amendment.get("new_value") != 1:
            errors.append("HOLDOUT_H0_AMENDMENT_VALUE_DRIFT")

    h0 = contract.get("h0_acceptance", {})
    if h0.get("frozen_main_head_must_equal") != end_sha:
        errors.append("HOLDOUT_H0_ACCEPTANCE_MAIN_HEAD_DRIFT")
    if h0.get("seed_checkpoint_count_must_equal") != 7 or h0.get("seed_commit_count_must_equal") != 7:
        errors.append("HOLDOUT_H0_ACCEPTANCE_SEED_COUNT_DRIFT")
    if h0.get("minimum_holdout_checkpoints_must_equal") != 12:
        errors.append("HOLDOUT_H0_ACCEPTANCE_MIN_CHECKPOINT_DRIFT")
    if h0.get("minimum_checkpoints_strictly_outside_seed_time_span_must_equal") != 1:
        errors.append("HOLDOUT_H0_ACCEPTANCE_OUTSIDE_SEED_DRIFT")
    if h0.get("selector_must_be_census") is not True:
        errors.append("HOLDOUT_H0_ACCEPTANCE_SELECTOR_NOT_CENSUS")
    if h0.get("discretionary_subsampling_allowed_must_be") is not False:
        errors.append("HOLDOUT_H0_ACCEPTANCE_SUBSAMPLING_DRIFT")
    for key in (
        "realized_outcomes_read_count_must_equal",
        "r2_replay_count_must_equal",
        "holdout_checkpoint_ledger_count_must_equal",
    ):
        if h0.get(key) != 0:
            errors.append("HOLDOUT_H0_PREMATURE_ACTIVITY:" + key)

    downstream_started = state.get("holdout_h1_started") is True or state.get("holdout_build_started") is True
    if state.get("holdout_selection_contract_frozen") is not True:
        errors.append("HOLDOUT_H0_STATE_NOT_FROZEN")
    if state.get("holdout_selection_contract_freeze_commit") != "adc1e9a1239c5556b48f57f1d3dbbb527d60a716":
        errors.append("HOLDOUT_H0_FREEZE_COMMIT_DRIFT")
    if state.get("holdout_h0_complete") is not True:
        errors.append("HOLDOUT_H0_STATE_NOT_COMPLETE")
    if state.get("holdout_h1_start_allowed") is not True:
        errors.append("HOLDOUT_H0_H1_NOT_ALLOWED")
    if not downstream_started:
        if state.get("holdout_h1_started") is not False or state.get("holdout_build_started") is not False:
            errors.append("HOLDOUT_H0_PREMATURE_BUILD")
        future_files = [
            ROOT / "generated/PHASE3_R2_HOLDOUT_SELECTION_LEDGER.json",
            ROOT / "generated/PHASE3_R2_HOLDOUT_REPLAY.json",
        ]
        if any(path.exists() for path in future_files):
            errors.append("HOLDOUT_H0_FUTURE_ARTIFACT_PREMATURELY_PRESENT")

    cv = current.get("validation", {})
    if current.get("current_phase") != "PHASE_3C_R2_POINT_IN_TIME_REPLAY":
        errors.append("HOLDOUT_H0_CURRENT_PHASE_DRIFT")
    if current.get("next_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
        errors.append("HOLDOUT_H0_NEXT_PHASE_DRIFT")
    for key, expected in (
        ("holdout_selection_contract_frozen", True),
        ("holdout_h0_complete", True),
        ("holdout_h1_start_allowed", True),
        ("holdout_h1_started", False),
        ("holdout_build_started", False),
        ("direct_holdout_to_phase4_allowed", False),
        ("repeat_phase3f_required_after_holdout_and_r2_downstream_evidence", True),
        ("phase3_historical_validation_complete", False),
        ("phase4_entry_allowed", False),
    ):
        if not downstream_started and cv.get(key) is not expected:
            errors.append("HOLDOUT_H0_CURRENT_STATUS_DRIFT:" + key)

    if state.get("r2_independent_holdout_start_allowed") is not True:
        errors.append("HOLDOUT_H0_PARENT_GATE_NOT_ALLOWED")
    if state.get("phase3_historical_validation_complete") is not False:
        errors.append("HOLDOUT_H0_PREMATURE_PHASE3_COMPLETE")
    if state.get("phase4_entry_allowed") is not False:
        errors.append("HOLDOUT_H0_PREMATURE_PHASE4")

    for surface_name, surface in (
        ("CONTRACT", contract["authority_boundaries"]),
        ("STATE", state),
        ("CURRENT", current),
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

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        raise AssertionError(";".join(errors))
    contract = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    q = contract["quantitative_sufficiency_gate"]
    print(
        "PHASE3_R2_HOLDOUT_H0_ACCEPTANCE_PASS "
        f"universe={contract['frozen_repository_universe']['start_commit_inclusive'][:8]}.."
        f"{contract['frozen_repository_universe']['end_commit_inclusive'][:8]} "
        f"seed_exclusions={len(contract['seed_firewall']['excluded_checkpoint_ids'])} "
        f"min_checkpoints={q['minimum_holdout_checkpoints']} "
        f"min_dates={q['minimum_distinct_utc_dates']} "
        f"min_weeks={q['minimum_distinct_iso_weeks']} "
        f"min_regimes={q['minimum_distinct_evidence_regime_signatures']} "
        f"min_securities={q['minimum_unique_securities']} "
        f"min_profiles={q['minimum_opportunity_profile_instances']} min_outside_seed={q['minimum_checkpoints_strictly_outside_seed_time_span']} "
        "outcomes_read=0 r2_replays=0 holdout_ledger=0 "
        "h1_start_allowed=true phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
