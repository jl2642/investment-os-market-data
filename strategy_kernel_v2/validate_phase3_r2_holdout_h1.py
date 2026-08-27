from __future__ import annotations

import json
from pathlib import Path
import subprocess

from strategy_kernel_v2.phase3_r2_holdout_h1 import (
    OUTPUT_FILE,
    _blob_at,
    _commit_time,
    _git,
    _load_json,
    _parse_time,
    _universe_commits,
    build_holdout_h1_ledger,
    build_family_catalog,
    build_source_snapshot,
    write_default,
)
from strategy_kernel_v2.validate_phase3_r2_holdout_h0 import validate as validate_h0
from strategy_kernel_v2.program_consistency import validate_program_consistency

ROOT = Path(__file__).resolve().parent


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def validate() -> tuple[list[str], dict]:
    errors = list(validate_program_consistency())
    errors.extend(validate_h0())

    contract = _load_json(ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
    registry = _load_json(ROOT / "PHASE3A_EVIDENCE_REGISTRY.json")
    state = _load_json(ROOT / "PROGRAM_STATE.json")
    current = _load_json(ROOT / "CURRENT_PHASE_STATUS.json")

    first = build_holdout_h1_ledger(ROOT.parent)
    second = build_holdout_h1_ledger(ROOT.parent)
    if first != second or first["selection_ledger_sha256"] != second["selection_ledger_sha256"]:
        errors.append("H1_NONDETERMINISTIC_LEDGER")

    if first.get("selector_mode") != "CENSUS_OF_ALL_ELIGIBLE_DISTINCT_DECISION_EVIDENCE_FINGERPRINTS":
        errors.append("H1_SELECTOR_MODE_DRIFT")
    if first.get("model_form_frozen_but_not_executed") != contract["model_form"]:
        errors.append("H1_MODEL_IDENTITY_DRIFT")
    if first.get("model_version_frozen_but_not_executed") != contract["model_version"]:
        errors.append("H1_MODEL_VERSION_DRIFT")

    for key in (
        "realized_outcomes_read_count",
        "phase3d_results_read_count",
        "r2_profile_compute_count",
        "r2_pareto_replay_count",
        "future_return_read_count",
        "regret_or_calibration_read_count",
        "discretionary_subsampling_count",
        "manual_cherry_pick_count",
    ):
        if first.get(key) != 0:
            errors.append("H1_FORBIDDEN_ACTIVITY_NONZERO:" + key)

    start_sha = contract["frozen_repository_universe"]["start_commit_inclusive"]
    end_sha = contract["frozen_repository_universe"]["end_commit_inclusive"]
    universe = _universe_commits(ROOT.parent, start_sha, end_sha)
    if first["frozen_universe"]["commit_count"] != len(universe):
        errors.append("H1_UNIVERSE_COMMIT_COUNT_DRIFT")
    if first["universe_commit_audit_count"] != len(universe):
        errors.append("H1_UNIVERSE_AUDIT_COUNT_DRIFT")
    if len(first["universe_commit_audit"]) != len(universe):
        errors.append("H1_UNIVERSE_AUDIT_ROWS_DRIFT")
    if [row["commit_sha"] for row in first["universe_commit_audit"]] != universe:
        errors.append("H1_UNIVERSE_AUDIT_ORDER_DRIFT")

    selected = first["selected_checkpoints"]
    if first["selected_checkpoint_count"] != len(selected):
        errors.append("H1_SELECTED_COUNT_DRIFT")
    selected_audit = [row for row in first["universe_commit_audit"] if row["selected"]]
    if len(selected_audit) != len(selected):
        errors.append("H1_SELECTED_AUDIT_ACCOUNTING_DRIFT")
    if [row["commit_sha"] for row in selected_audit] != [row["canonical_commit_sha"] for row in selected]:
        errors.append("H1_SELECTED_COMMIT_ORDER_DRIFT")

    selected_commit_ids = [row["canonical_commit_sha"] for row in selected]
    selected_checkpoint_ids = [row["checkpoint_id"] for row in selected]
    selected_fingerprints = [row["decision_evidence_fingerprint_sha256"] for row in selected]
    if len(selected_commit_ids) != len(set(selected_commit_ids)):
        errors.append("H1_DUPLICATE_SELECTED_COMMIT")
    if len(selected_checkpoint_ids) != len(set(selected_checkpoint_ids)):
        errors.append("H1_DUPLICATE_CHECKPOINT_ID")
    if len(selected_fingerprints) != len(set(selected_fingerprints)):
        errors.append("H1_DUPLICATE_SELECTED_FINGERPRINT")

    seed_commits = set(contract["seed_firewall"]["excluded_commit_shas"])
    if set(selected_commit_ids) & seed_commits:
        errors.append("H1_SEED_COMMIT_SELECTED")

    family_catalog = build_family_catalog(registry, contract)
    scope = sorted(registry["scope_security_ids"])
    seed_source_sets = set()
    for seed_sha in sorted(seed_commits):
        seed_snapshot = build_source_snapshot(
            ROOT.parent,
            seed_sha,
            family_catalog=family_catalog,
            opportunity_security_ids=scope,
            contract=contract,
        )
        seed_source_sets.add(seed_snapshot["source_identity_set_sha256"])

    for checkpoint in selected:
        checkpoint_sha = checkpoint["canonical_commit_sha"]
        checkpoint_time = _parse_time(checkpoint["at"])
        if checkpoint["opportunity_security_ids"] != scope:
            errors.append("H1_OPPORTUNITY_SCOPE_DRIFT:" + checkpoint["checkpoint_id"])
        if checkpoint["source_identity_set_sha256"] in seed_source_sets:
            errors.append("H1_EXACT_SEED_SOURCE_SET_SELECTED:" + checkpoint["checkpoint_id"])
        if not _is_ancestor(ROOT.parent, start_sha, checkpoint_sha):
            errors.append("H1_CHECKPOINT_BEFORE_UNIVERSE_START:" + checkpoint["checkpoint_id"])
        if not _is_ancestor(ROOT.parent, checkpoint_sha, end_sha):
            errors.append("H1_CHECKPOINT_OUTSIDE_FROZEN_MAIN:" + checkpoint["checkpoint_id"])

        research_families = set(contract["frozen_evidence_families"]["research_or_decision_families"])
        present_families = set(checkpoint["available_frozen_evidence_family_ids"])
        if "CANDIDATE_STATE" not in present_families:
            errors.append("H1_CANDIDATE_MISSING:" + checkpoint["checkpoint_id"])
        if len(present_families & research_families) < 1:
            errors.append("H1_RESEARCH_DECISION_FAMILY_MISSING:" + checkpoint["checkpoint_id"])

        for family in checkpoint["source_identities"]:
            source = family["active_source"]
            source_time = _parse_time(source["available_at"])
            if source_time > checkpoint_time:
                errors.append("H1_FUTURE_SOURCE_LEAK:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])
            if not _is_ancestor(ROOT.parent, source["source_commit_sha"], checkpoint_sha):
                errors.append("H1_SOURCE_NOT_AVAILABLE_ON_CHECKPOINT_ANCESTRY:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])
            blob_at_checkpoint = _blob_at(ROOT.parent, checkpoint_sha, source["path"])
            blob_at_source = _blob_at(ROOT.parent, source["source_commit_sha"], source["path"])
            if source["blob_sha"] != blob_at_checkpoint or source["blob_sha"] != blob_at_source:
                errors.append("H1_SOURCE_BLOB_IDENTITY_DRIFT:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])

    # Every selected checkpoint must represent a fingerprint change on that main commit.
    for row in selected_audit:
        if row["fingerprint_changed_from_previous_main_commit"] is not True:
            errors.append("H1_SELECTED_WITHOUT_MAIN_COMMIT_FINGERPRINT_CHANGE:" + row["commit_sha"])
        if row["fingerprint_differs_from_previous_selected_checkpoint"] is not True:
            errors.append("H1_SELECTED_WITHOUT_PREVIOUS_SELECTED_CHANGE:" + row["commit_sha"])
        if row["source_identity_set_matches_seed"] is not False:
            errors.append("H1_SELECTED_SEED_SOURCE_SET:" + row["commit_sha"])
        if row["eligible_structure"] is not True:
            errors.append("H1_SELECTED_INELIGIBLE_STRUCTURE:" + row["commit_sha"])
        if row["seed_commit"] is not False:
            errors.append("H1_SELECTED_SEED_FLAG:" + row["commit_sha"])
        if row["exclusion_reason"] is not None:
            errors.append("H1_SELECTED_WITH_EXCLUSION_REASON:" + row["commit_sha"])

    # Pure no-change main commits and explicit seeds must never leak into the census.
    for row in first["universe_commit_audit"]:
        if row["seed_commit"] and row["selected"]:
            errors.append("H1_SEED_AUDIT_SELECTED:" + row["commit_sha"])
        if (
            row["eligible_structure"]
            and not row["seed_commit"]
            and not row["fingerprint_changed_from_previous_main_commit"]
            and row["selected"]
        ):
            errors.append("H1_PURE_NO_CHANGE_COMMIT_SELECTED:" + row["commit_sha"])

    suff = first["sufficiency"]
    checks = suff["checks"]
    if suff["all_thresholds_passed"] != all(checks.values()):
        errors.append("H1_SUFFICIENCY_CONJUNCTION_DRIFT")
    expected_status = "PASS_SELECTION_SUFFICIENCY" if all(checks.values()) else "FAIL_SELECTION_SUFFICIENCY"
    if first["status"] != expected_status:
        errors.append("H1_STATUS_CLASSIFICATION_DRIFT")
    if first["h2_start_allowed"] != all(checks.values()):
        errors.append("H1_H2_GATE_CLASSIFICATION_DRIFT")

    # H1 has still not run R2 or outcomes, regardless of PASS/FAIL.
    if first["h2_started"] is not False:
        errors.append("H1_PREMATURE_H2_START")
    if first["phase3_historical_validation_complete"] is not False:
        errors.append("H1_PREMATURE_PHASE3_COMPLETE")
    if first["phase4_entry_allowed"] is not False:
        errors.append("H1_PREMATURE_PHASE4")

    # Before final state closeout the result may be computed while state still says H1 not started.
    # After closeout, state must match the exact deterministic result.
    if state.get("holdout_h1_complete") is True:
        observed = suff["observed"]
        v2_downstream = state.get("holdout_v2_selection_complete") is True
        v2_pass = state.get("holdout_v2_selection_outcome") == "PASS_SELECTION_SUFFICIENCY"
        global_h2_start_allowed = v2_pass if v2_downstream else first["h2_start_allowed"]
        expected_state = {
            "holdout_h1_started": True,
            "holdout_build_started": True,
            "holdout_h1_complete": True,
            "holdout_h1_outcome": first["status"],
            "holdout_h1_selected_checkpoint_count": observed["holdout_checkpoints"],
            "holdout_h1_distinct_utc_dates": observed["distinct_utc_dates"],
            "holdout_h1_distinct_iso_weeks": observed["distinct_iso_weeks"],
            "holdout_h1_distinct_evidence_regimes": observed["distinct_evidence_regime_signatures"],
            "holdout_h1_unique_securities": observed["unique_securities"],
            "holdout_h1_opportunity_profile_instances": observed["opportunity_profile_instances"],
            "holdout_h1_checkpoints_outside_seed_span": observed["checkpoints_strictly_outside_seed_time_span"],
            "holdout_h2_start_allowed": global_h2_start_allowed,
            "holdout_h2_started": False,
            "phase3_historical_validation_complete": False,
            "phase4_entry_allowed": False,
        }
        for key, expected in expected_state.items():
            if state.get(key) != expected:
                errors.append("H1_STATE_DRIFT:" + key)
        extra_state = {
            "holdout_h1_selection_ledger_sha256": first["selection_ledger_sha256"],
            "holdout_h1_max_single_utc_date_fraction": observed["maximum_single_utc_date_fraction"],
            "holdout_h1_max_single_evidence_regime_fraction": observed["maximum_single_evidence_regime_fraction"],
            "holdout_v1_coverage_sufficient": first["h2_start_allowed"],
            "holdout_coverage_expansion_required": (not v2_pass) if v2_downstream else (not first["h2_start_allowed"]),
            "holdout_threshold_relaxation_after_result_allowed": False,
            "holdout_v2_pre_result_contract_required": not first["h2_start_allowed"],
        }
        failed_thresholds = sorted(key for key, passed in checks.items() if not passed)
        extra_state["holdout_h1_failed_thresholds"] = failed_thresholds
        for key, expected in extra_state.items():
            if state.get(key) != expected:
                errors.append("H1_STATE_EXTRA_DRIFT:" + key)
        cv = current.get("validation", {})
        for key, expected in {**expected_state, **extra_state}.items():
            if key in cv and cv.get(key) != expected:
                errors.append("H1_CURRENT_VALIDATION_DRIFT:" + key)
        if current.get("current_phase") != "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE":
            errors.append("H1_CURRENT_PHASE_DRIFT")
        if v2_downstream:
            expected_status = (
                "V2_SELECTION_SUFFICIENT_H2_READY_PHASE4_BLOCKED"
                if v2_pass
                else "V2_SELECTION_INSUFFICIENT_COVERAGE_EXPANSION_REQUIRED_H2_BLOCKED_PHASE4_BLOCKED"
            )
            expected_next = (
                "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
                if v2_pass
                else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
            )
        else:
            expected_status = (
                "H1_SELECTION_SUFFICIENT_H2_READY_PHASE4_BLOCKED"
                if first["h2_start_allowed"]
                else "H1_SELECTION_INSUFFICIENT_COVERAGE_EXPANSION_REQUIRED_H2_BLOCKED_PHASE4_BLOCKED"
            )
            expected_next = (
                "INDEPENDENT_POINT_IN_TIME_HOLDOUT_R2_REPLAY"
                if first["h2_start_allowed"]
                else "INDEPENDENT_POINT_IN_TIME_HOLDOUT_COVERAGE_EXPANSION"
            )
        if current.get("status") != expected_status:
            errors.append("H1_CURRENT_STATUS_DRIFT")
        if current.get("next_phase") != expected_next:
            errors.append("H1_NEXT_PHASE_DRIFT")

    if not errors:
        write_default(first)
    return errors, first


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    observed = result["sufficiency"]["observed"]
    print(
        "PHASE3_R2_HOLDOUT_H1_ACCEPTANCE_RESULT "
        f"status={result['status']} checkpoints={observed['holdout_checkpoints']} "
        f"dates={observed['distinct_utc_dates']} weeks={observed['distinct_iso_weeks']} "
        f"regimes={observed['distinct_evidence_regime_signatures']} "
        f"securities={observed['unique_securities']} profiles={observed['opportunity_profile_instances']} "
        f"outside_seed={observed['checkpoints_strictly_outside_seed_time_span']} "
        f"max_date_fraction={observed['maximum_single_utc_date_fraction']:.6f} "
        f"max_regime_fraction={observed['maximum_single_evidence_regime_fraction']:.6f} "
        "outcomes_read=0 r2_replays=0 "
        f"h2_start_allowed={str(result['h2_start_allowed']).lower()} "
        "phase3_historical_validation_complete=false phase4_entry_allowed=false "
        "orders=0 trade_authority=NONE"
    )
