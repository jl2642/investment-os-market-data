from __future__ import annotations

import json
from pathlib import Path
import subprocess

from strategy_kernel_v2.phase3_r2_holdout_h1 import _blob_at, _parse_time
from strategy_kernel_v2.phase3_r2_holdout_v2_selection import (
    OUTPUT_FILE,
    build_holdout_v2_selection_ledger,
    write_default,
)
from strategy_kernel_v2.program_consistency import validate_program_consistency
from strategy_kernel_v2.validate_phase3_r2_holdout_v2_contract import validate as validate_v2_contract

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


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
    errors.extend(validate_v2_contract())

    contract = load("PHASE3_R2_HOLDOUT_COVERAGE_EXPANSION_V2_CONTRACT.json")
    h0 = load("PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json")
    state = load("PROGRAM_STATE.json")
    current = load("CURRENT_PHASE_STATUS.json")

    first = build_holdout_v2_selection_ledger(ROOT.parent)
    second = build_holdout_v2_selection_ledger(ROOT.parent)
    if first != second or first["selection_ledger_sha256"] != second["selection_ledger_sha256"]:
        errors.append("V2_SELECTION_NONDETERMINISTIC")

    if first.get("v2_contract_id") != contract["contract_id"]:
        errors.append("V2_SELECTION_CONTRACT_ID_DRIFT")
    if first.get("parent_h1_result") != "FAIL_SELECTION_SUFFICIENCY":
        errors.append("V2_SELECTION_PARENT_H1_RESULT_DRIFT")
    if first.get("parent_h1_checkpoint_count") != 8:
        errors.append("V2_SELECTION_PARENT_H1_COUNT_DRIFT")
    if first.get("selector_mode") != h0["deterministic_selector"]["mode"]:
        errors.append("V2_SELECTION_SELECTOR_MODE_DRIFT")
    if first.get("family_catalog_count") != 14:
        errors.append("V2_SELECTION_FAMILY_COUNT_DRIFT")
    if first.get("v2_security_scope_count") != 18:
        errors.append("V2_SELECTION_SECURITY_SCOPE_COUNT_DRIFT")
    if first.get("v2_security_scope_ids") != contract["v2_security_scope"]["security_ids"]:
        errors.append("V2_SELECTION_SECURITY_SCOPE_DRIFT")

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
            errors.append("V2_SELECTION_FORBIDDEN_ACTIVITY_NONZERO:" + key)

    selected = first["selected_checkpoints"]
    audit = first["universe_commit_audit"]
    selected_audit = [row for row in audit if row["selected"]]
    if first["selected_checkpoint_count"] != len(selected):
        errors.append("V2_SELECTION_COUNT_DRIFT")
    if len(selected_audit) != len(selected):
        errors.append("V2_SELECTION_AUDIT_ACCOUNTING_DRIFT")
    if [row["commit_sha"] for row in selected_audit] != [row["canonical_commit_sha"] for row in selected]:
        errors.append("V2_SELECTION_COMMIT_ORDER_DRIFT")

    ids = [row["checkpoint_id"] for row in selected]
    commits = [row["canonical_commit_sha"] for row in selected]
    fingerprints = [row["decision_evidence_fingerprint_sha256"] for row in selected]
    if len(ids) != len(set(ids)):
        errors.append("V2_SELECTION_DUPLICATE_CHECKPOINT_ID")
    if len(commits) != len(set(commits)):
        errors.append("V2_SELECTION_DUPLICATE_COMMIT")
    if len(fingerprints) != len(set(fingerprints)):
        errors.append("V2_SELECTION_DUPLICATE_FINGERPRINT")

    seed_commits = set(h0["seed_firewall"]["excluded_commit_shas"])
    if set(commits) & seed_commits:
        errors.append("V2_SELECTION_SEED_COMMIT_SELECTED")

    start_sha = first["frozen_universe"]["start_commit_inclusive"]
    end_sha = first["frozen_universe"]["end_commit_inclusive"]
    if start_sha != contract["unchanged_v1_contract"]["protected_main_universe"]["start_commit_inclusive"]:
        errors.append("V2_SELECTION_UNIVERSE_START_DRIFT")
    if end_sha != contract["unchanged_v1_contract"]["protected_main_universe"]["end_commit_inclusive"]:
        errors.append("V2_SELECTION_UNIVERSE_END_DRIFT")

    for row in selected_audit:
        if row["eligible_structure"] is not True:
            errors.append("V2_SELECTION_INELIGIBLE_ROW_SELECTED:" + row["commit_sha"])
        if row["seed_commit"] is not False:
            errors.append("V2_SELECTION_SEED_FLAG_SELECTED:" + row["commit_sha"])
        if row["fingerprint_changed_from_previous_main_commit"] is not True:
            errors.append("V2_SELECTION_WITHOUT_CURRENT_MAIN_CHANGE:" + row["commit_sha"])
        if row["fingerprint_differs_from_previous_selected_checkpoint"] is not True:
            errors.append("V2_SELECTION_WITHOUT_PREVIOUS_SELECTED_CHANGE:" + row["commit_sha"])
        if row["source_identity_set_matches_seed"] is not False:
            errors.append("V2_SELECTION_SEED_SOURCE_SET_SELECTED:" + row["commit_sha"])
        if row["exclusion_reason"] is not None:
            errors.append("V2_SELECTION_SELECTED_WITH_EXCLUSION_REASON:" + row["commit_sha"])

    for checkpoint in selected:
        checkpoint_sha = checkpoint["canonical_commit_sha"]
        checkpoint_time = _parse_time(checkpoint["at"])
        if checkpoint["opportunity_security_ids"] != contract["v2_security_scope"]["security_ids"]:
            errors.append("V2_SELECTION_CHECKPOINT_SCOPE_DRIFT:" + checkpoint["checkpoint_id"])
        if not _is_ancestor(ROOT.parent, start_sha, checkpoint_sha):
            errors.append("V2_SELECTION_CHECKPOINT_BEFORE_START:" + checkpoint["checkpoint_id"])
        if not _is_ancestor(ROOT.parent, checkpoint_sha, end_sha):
            errors.append("V2_SELECTION_CHECKPOINT_AFTER_END:" + checkpoint["checkpoint_id"])
        for family in checkpoint["source_identities"]:
            source = family["active_source"]
            source_time = _parse_time(source["available_at"])
            if source_time > checkpoint_time:
                errors.append("V2_SELECTION_FUTURE_SOURCE_LEAK:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])
            if not _is_ancestor(ROOT.parent, source["source_commit_sha"], checkpoint_sha):
                errors.append("V2_SELECTION_SOURCE_NOT_ON_ANCESTRY:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])
            blob_at_checkpoint = _blob_at(ROOT.parent, checkpoint_sha, source["path"])
            blob_at_source = _blob_at(ROOT.parent, source["source_commit_sha"], source["path"])
            if source["blob_sha"] != blob_at_checkpoint or source["blob_sha"] != blob_at_source:
                errors.append("V2_SELECTION_SOURCE_BLOB_DRIFT:" + checkpoint["checkpoint_id"] + ":" + family["family_id"])

    suff = first["sufficiency"]
    checks = suff["checks"]
    if suff["all_thresholds_passed"] != all(checks.values()):
        errors.append("V2_SELECTION_SUFFICIENCY_CONJUNCTION_DRIFT")
    expected_status = "PASS_SELECTION_SUFFICIENCY" if all(checks.values()) else "FAIL_SELECTION_SUFFICIENCY"
    if first["status"] != expected_status:
        errors.append("V2_SELECTION_STATUS_CLASSIFICATION_DRIFT")
    if first["h2_start_allowed"] != all(checks.values()):
        errors.append("V2_SELECTION_H2_GATE_DRIFT")
    if first["h2_started"] is not False:
        errors.append("V2_SELECTION_PREMATURE_H2_START")
    if first["phase3_historical_validation_complete"] is not False:
        errors.append("V2_SELECTION_PREMATURE_PHASE3_COMPLETE")
    if first["phase4_entry_allowed"] is not False:
        errors.append("V2_SELECTION_PREMATURE_PHASE4")

    # The initial candidate run intentionally computes the ledger before governed
    # state closeout. Once closeout is recorded, bind state exactly to this result.
    if state.get("holdout_v2_selection_complete") is True:
        observed = suff["observed"]
        replay_downstream = state.get("independent_holdout_replay_complete") is True
        repeat_done = state.get("repeat_phase3f_complete") is True
        expected_state = {
            "holdout_v2_selection_started": True,
            "holdout_v2_selection_complete": True,
            "holdout_v2_selection_outcome": first["status"],
            "holdout_v2_selected_checkpoint_count": observed["holdout_checkpoints"],
            "holdout_v2_distinct_utc_dates": observed["distinct_utc_dates"],
            "holdout_v2_distinct_iso_weeks": observed["distinct_iso_weeks"],
            "holdout_v2_distinct_evidence_regimes": observed["distinct_evidence_regime_signatures"],
            "holdout_v2_unique_securities": observed["unique_securities"],
            "holdout_v2_opportunity_profile_instances": observed["opportunity_profile_instances"],
            "holdout_v2_checkpoints_outside_seed_span": observed["checkpoints_strictly_outside_seed_time_span"],
            "holdout_v2_max_single_utc_date_fraction": observed["maximum_single_utc_date_fraction"],
            "holdout_v2_max_single_evidence_regime_fraction": observed["maximum_single_evidence_regime_fraction"],
            "holdout_h2_start_allowed": first["h2_start_allowed"],
            "holdout_h2_started": True if replay_downstream else False,
            "phase3_historical_validation_complete": repeat_done,
            "phase4_entry_allowed": repeat_done,
        }
        for key, expected in expected_state.items():
            if state.get(key) != expected:
                errors.append("V2_SELECTION_STATE_DRIFT:" + key)
        cv = current.get("validation", {})
        for key, expected in expected_state.items():
            if key in cv and cv.get(key) != expected:
                errors.append("V2_SELECTION_CURRENT_VALIDATION_DRIFT:" + key)
        failed = sorted(key for key, passed in checks.items() if not passed)
        if state.get("holdout_v2_failed_thresholds") != failed:
            errors.append("V2_SELECTION_FAILED_THRESHOLD_STATE_DRIFT")
        if state.get("holdout_v2_selection_ledger_sha256") != first["selection_ledger_sha256"]:
            errors.append("V2_SELECTION_LEDGER_SHA_STATE_DRIFT")

    if not errors:
        write_default(first)
    return errors, first


if __name__ == "__main__":
    errors, result = validate()
    if errors:
        raise AssertionError(";".join(errors))
    observed = result["sufficiency"]["observed"]
    print(
        "PHASE3_R2_HOLDOUT_V2_SELECTION_ACCEPTANCE_RESULT "
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
