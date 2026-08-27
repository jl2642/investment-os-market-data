"""Independent PIT Holdout replay for the frozen R2.0.1 model.

Consumes the accepted V2 Holdout selection ledger, reconstructs the exact
checkpoint-local shared evidence packets from registered source identities,
reuses the existing model-neutral historical extractor and frozen 20-rule R2
transform catalog, then executes checkpoint-local exact-signature Pareto replay.

No realized outcomes, Phase 3D results, future returns, regret, calibration,
new feature mappings, new evidence fetches, scalarization, ranking, portfolio
writeback or trading authority are permitted here.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from strategy_kernel_v2.historical_feature_extractor import extract_model_neutral_features
from strategy_kernel_v2.historical_replay import CachingRegisteredSourceLoader
from strategy_kernel_v2.phase3_r2_holdout_v2_selection import build_holdout_v2_selection_ledger
from strategy_kernel_v2.phase3b_r2_contract import (
    compare_r2_profiles,
    load_contract as load_r2_contract,
    transform_model_neutral_row,
    validate_contract as validate_r2_contract,
)
from strategy_kernel_v2.phase3c_r2a_reconstruction import _dimension_state_ledger
from strategy_kernel_v2.phase3c_r2b_replay import _to_comparator_profile

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3_R2_INDEPENDENT_HOLDOUT_REPLAY_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3_R2_INDEPENDENT_HOLDOUT_REPLAY.json"

CONTROLS = {
    "model_specific_evidence_fetch_allowed": False,
    "later_evidence_backfill_allowed": False,
    "present_day_substitution_allowed": False,
    "new_family_feature_mapping_allowed": False,
    "new_security_scope_member_allowed": False,
    "subjective_mapping_allowed": False,
    "silent_proxy_allowed": False,
    "retrospective_probability_creation_allowed": False,
    "retrospective_confidence_creation_allowed": False,
    "retrospective_cost_score_creation_allowed": False,
    "realized_outcome_loading_allowed": False,
    "phase3d_result_loading_allowed": False,
    "future_return_loading_allowed": False,
    "regret_loading_allowed": False,
    "calibration_loading_allowed": False,
    "cross_checkpoint_comparison_allowed": False,
    "cross_signature_comparison_allowed": False,
    "scalar_policy_score_allowed": False,
    "dimension_weights_allowed": False,
    "ranking_allowed": False,
    "global_winner_selection_allowed": False,
    "target_weight_generation_allowed": False,
    "candidate_mutation_allowed": False,
    "real_position_mutation_allowed": False,
    "simulation_position_mutation_allowed": False,
    "target_portfolio_writeback_allowed": False,
    "user_decision_generation_allowed": False,
    "investment_recommendation_generation_allowed": False,
    "order_authorized": False,
    "orders": 0,
    "trade_authority": "NONE",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_replay_contract(path: str | Path = CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_replay_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_HOLDOUT_R2_REPLAY":
        errors.append("HOLDOUT_REPLAY_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_selection", {})
    if parent.get("status") != "PASS_SELECTION_SUFFICIENCY":
        errors.append("HOLDOUT_REPLAY_PARENT_SELECTION_NOT_PASS")
    if parent.get("checkpoint_count") != 14:
        errors.append("HOLDOUT_REPLAY_PARENT_CHECKPOINT_COUNT_DRIFT")
    if parent.get("selection_ledger_sha256") != "241bb441a960b2ccfb46a708ae81f7b38d5b2389215362406255cd4945b337be":
        errors.append("HOLDOUT_REPLAY_PARENT_LEDGER_SHA_DRIFT")
    if parent.get("h2_start_allowed") is not True:
        errors.append("HOLDOUT_REPLAY_PARENT_GATE_NOT_ALLOWED")

    model = contract.get("model_contract", {})
    if model.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("HOLDOUT_REPLAY_MODEL_FORM_DRIFT")
    if model.get("model_version") != "R2.0.1_RESEARCH":
        errors.append("HOLDOUT_REPLAY_MODEL_VERSION_DRIFT")
    if model.get("frozen_transform_rule_count") != 20:
        errors.append("HOLDOUT_REPLAY_TRANSFORM_COUNT_DRIFT")
    for key in (
        "new_transform_rules_allowed",
        "transform_threshold_changes_allowed",
        "transform_semantics_changes_allowed",
        "comparison_signature_changes_allowed",
    ):
        if model.get(key) is not False:
            errors.append("HOLDOUT_REPLAY_MODEL_MUTATION_OPEN:" + key)

    inputs = contract.get("replay_input_contract", {})
    for key in (
        "rebuild_parent_v2_selection_deterministically",
        "parent_selection_sha_must_match",
        "exact_selected_checkpoint_set_only",
        "exact_selected_checkpoint_source_identities_only",
        "exact_source_commit_path_blob_identity_required",
        "protected_main_first_parent_provenance_required",
        "model_specific_evidence_fetch_forbidden",
        "later_evidence_backfill_forbidden",
        "present_day_state_substitution_forbidden",
        "new_family_feature_mapping_during_replay_forbidden",
        "new_security_scope_member_during_replay_forbidden",
        "unsupported_packet_families_remain_uninterpreted",
        "existing_historical_feature_extractor_only",
        "existing_r2_transform_catalog_only",
    ):
        if inputs.get(key) is not True:
            errors.append("HOLDOUT_REPLAY_INPUT_GUARD_FALSE:" + key)

    firewall = contract.get("feature_semantics_firewall", {})
    for key in (
        "unsupported_family_data_may_create_new_r2_dimension",
        "subjective_mapping_allowed",
        "silent_proxy_allowed",
        "retrospective_probability_creation_allowed",
        "retrospective_confidence_creation_allowed",
        "retrospective_cost_score_creation_allowed",
    ):
        if firewall.get(key) is not False:
            errors.append("HOLDOUT_REPLAY_FEATURE_FIREWALL_OPEN:" + key)

    comparison = contract.get("comparison_contract", {})
    if comparison.get("method") != "PARETO_WITHIN_EXACT_COMPARISON_SIGNATURE":
        errors.append("HOLDOUT_REPLAY_COMPARISON_METHOD_DRIFT")
    for key in (
        "checkpoint_local_only",
        "cross_checkpoint_comparison_forbidden",
        "exact_signature_required",
        "cross_signature_dominance_forbidden",
        "missing_dimension_fill_forbidden",
        "local_frontier_is_not_global_winner",
    ):
        if comparison.get(key) is not True:
            errors.append("HOLDOUT_REPLAY_COMPARISON_GUARD_FALSE:" + key)
    for key in (
        "scalar_policy_score_allowed",
        "dimension_weights_allowed",
        "ranking_allowed",
        "global_winner_selection_allowed",
        "target_weight_generation_allowed",
    ):
        if comparison.get(key) is not False:
            errors.append("HOLDOUT_REPLAY_FORBIDDEN_COMPARISON_TRUE:" + key)

    outcome = contract.get("outcome_firewall", {})
    for key in (
        "realized_outcomes_loaded",
        "phase3d_results_loaded",
        "future_returns_loaded",
        "regret_loaded",
        "calibration_loaded",
        "historical_performance_generated",
        "model_or_selection_tuning_from_outcomes",
    ):
        if outcome.get(key) is not False:
            errors.append("HOLDOUT_REPLAY_OUTCOME_FIREWALL_OPEN:" + key)

    acceptance = contract.get("acceptance_contract", {})
    if acceptance.get("pass_status") != "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL":
        errors.append("HOLDOUT_REPLAY_PASS_STATUS_DRIFT")
    if acceptance.get("partial_status") != "PARTIAL_VALID_HOLDOUT_REPLAY_NO_COMPARABLE_EXACT_SIGNATURE_GROUP":
        errors.append("HOLDOUT_REPLAY_PARTIAL_STATUS_DRIFT")
    if acceptance.get("fail_status") != "FAIL_HOLDOUT_REPLAY_CONTRACT_OR_AUDIT":
        errors.append("HOLDOUT_REPLAY_FAIL_STATUS_DRIFT")
    if acceptance.get("phase3d_r2_start_allowed_only_on_pass") is not True:
        errors.append("HOLDOUT_REPLAY_3D_GATE_DRIFT")
    if acceptance.get("phase4_entry_allowed") is not False:
        errors.append("HOLDOUT_REPLAY_PREMATURE_PHASE4")
    return errors


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def _blob_at(repo: Path, sha: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{sha}:{path}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _evidence_id(checkpoint_id: str, family_id: str, blob_sha: str) -> str:
    token = hashlib.sha256(
        f"{checkpoint_id}|{family_id}|{blob_sha}".encode("utf-8")
    ).hexdigest()[:20]
    return f"HOLDOUTV2_{checkpoint_id}_{family_id}_{token}"


def _snapshot_from_selected_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    repo: Path,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    checkpoint_sha = str(checkpoint["canonical_commit_sha"])
    checkpoint_id = str(checkpoint["checkpoint_id"])
    for family in checkpoint["source_identities"]:
        family_id = str(family["family_id"])
        source = family["active_source"]
        path = str(source["path"])
        source_sha = str(source["source_commit_sha"])
        blob_sha = str(source["blob_sha"])
        if not _is_ancestor(repo, source_sha, checkpoint_sha):
            raise AssertionError(
                f"HOLDOUT_REPLAY_SOURCE_NOT_ON_CHECKPOINT_ANCESTRY:{checkpoint_id}:{family_id}"
            )
        if _blob_at(repo, checkpoint_sha, path) != blob_sha:
            raise AssertionError(
                f"HOLDOUT_REPLAY_CHECKPOINT_BLOB_DRIFT:{checkpoint_id}:{family_id}"
            )
        if _blob_at(repo, source_sha, path) != blob_sha:
            raise AssertionError(
                f"HOLDOUT_REPLAY_SOURCE_BLOB_DRIFT:{checkpoint_id}:{family_id}"
            )
        evidence_id = _evidence_id(checkpoint_id, family_id, blob_sha)
        records.append(
            {
                "evidence_id": evidence_id,
                "evidence_key": family_id,
                "evidence_class": list(family.get("evidence_classes", [])),
                "security_ids": list(family.get("security_ids", [])),
                "available_at": source["available_at"],
                "source": {
                    "commit_sha": source_sha,
                    "path": path,
                    "provenance_status": "CANONICAL_MAIN",
                    "blob_sha": blob_sha,
                },
            }
        )
    records.sort(key=lambda row: row["evidence_id"])
    return {
        "decision_point_id": checkpoint_id,
        "at": checkpoint["at"],
        "canonical_commit_sha": checkpoint_sha,
        "opportunity_security_ids": list(checkpoint["opportunity_security_ids"]),
        "selected_evidence_ids": [row["evidence_id"] for row in records],
        "selected_evidence": records,
    }


def _classify(
    *,
    audit_errors: list[str],
    transform_failures: int,
    comparable_groups: int,
    comparable_profiles: int,
) -> str:
    if audit_errors or transform_failures:
        return "FAIL_HOLDOUT_REPLAY_CONTRACT_OR_AUDIT"
    if comparable_groups > 0 and comparable_profiles > 0:
        return "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL"
    return "PARTIAL_VALID_HOLDOUT_REPLAY_NO_COMPARABLE_EXACT_SIGNATURE_GROUP"


def build_holdout_replay(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    replay_contract = load_replay_contract()
    contract_errors = validate_replay_contract(replay_contract)
    r2_contract = load_r2_contract()
    contract_errors.extend(validate_r2_contract(r2_contract))
    if contract_errors:
        raise ValueError("INVALID_HOLDOUT_REPLAY_CONTRACT:" + ";".join(contract_errors))
    if len(r2_contract.get("transform_catalog", [])) != 20:
        raise AssertionError("HOLDOUT_REPLAY_REQUIRES_FROZEN_20_RULE_CATALOG")

    selection = build_holdout_v2_selection_ledger(repo)
    parent = replay_contract["parent_selection"]
    if selection.get("status") != parent["status"]:
        raise AssertionError("HOLDOUT_REPLAY_PARENT_SELECTION_STATUS_DRIFT")
    if selection.get("selection_ledger_sha256") != parent["selection_ledger_sha256"]:
        raise AssertionError("HOLDOUT_REPLAY_PARENT_SELECTION_SHA_DRIFT")
    if selection.get("selected_checkpoint_count") != parent["checkpoint_count"]:
        raise AssertionError("HOLDOUT_REPLAY_PARENT_SELECTION_COUNT_DRIFT")
    if selection.get("h2_start_allowed") is not True:
        raise AssertionError("HOLDOUT_REPLAY_PARENT_H2_GATE_FALSE")

    selected_checkpoints = selection["selected_checkpoints"]
    selected_commit_ids = [row["canonical_commit_sha"] for row in selected_checkpoints]
    if len(selected_commit_ids) != len(set(selected_commit_ids)):
        raise AssertionError("HOLDOUT_REPLAY_DUPLICATE_SELECTED_CHECKPOINT_COMMIT")

    expected_unique_sources = {
        (
            family["active_source"]["source_commit_sha"],
            family["active_source"]["path"],
            family["active_source"]["blob_sha"],
        )
        for checkpoint in selected_checkpoints
        for family in checkpoint["source_identities"]
    }

    loader = CachingRegisteredSourceLoader(repo)
    checkpoints: list[dict[str, Any]] = []
    audit_errors: list[str] = []
    total_profiles = 0
    total_present_dimensions = 0
    total_missing_dimensions = 0
    total_transform_failures = 0
    comparison_evaluable_profiles = 0
    exact_signature_groups = 0
    comparable_groups = 0
    singleton_groups = 0
    comparable_profiles = 0
    directional_pair_checks = 0
    dominance_edges = 0
    frontier_profiles = 0
    dominated_profiles = 0
    unsupported_evidence_instances = 0
    distinct_signatures: set[str] = set()

    for selected in selected_checkpoints:
        snapshot = _snapshot_from_selected_checkpoint(selected, repo=repo)
        feature_layer = extract_model_neutral_features(snapshot, source_loader=loader)
        selected_ids = set(snapshot["selected_evidence_ids"])
        feature_rows = feature_layer["feature_rows"]
        profiles: list[dict[str, Any]] = []
        comparator_profiles: list[dict[str, Any]] = []

        for security_id in sorted(feature_rows):
            row = feature_rows[security_id]
            profile = transform_model_neutral_row(row, r2_contract)
            state_ledger = _dimension_state_ledger(row, profile, r2_contract)
            for dim in profile.get("dimensions", []):
                outside = set(dim.get("provenance_evidence_ids", [])) - selected_ids
                if outside:
                    audit_errors.append(
                        f"HOLDOUT_REPLAY_DIMENSION_PROVENANCE_OUTSIDE_PACKET:{selected['checkpoint_id']}:{security_id}:{dim['rule_id']}"
                    )
            present = sum(item["state"] == "PRESENT" for item in state_ledger)
            missing = sum(item["state"] == "MISSING" for item in state_ledger)
            failures = sum(item["state"] == "TRANSFORM_FAILURE" for item in state_ledger)
            total_present_dimensions += present
            total_missing_dimensions += missing
            total_transform_failures += failures
            if profile.get("comparison_contract_evaluable"):
                comparison_evaluable_profiles += 1
            distinct_signatures.add(profile["comparison_signature_sha256"])
            row_profile = {
                "security_id": security_id,
                "security_name": profile.get("security_name", security_id),
                "provenance_evidence_ids": list(profile["provenance_evidence_ids"]),
                "dimension_states": state_ledger,
                "present_dimension_count": present,
                "missing_dimension_count": missing,
                "transform_failure_count": failures,
                "profile_evaluable": profile["profile_evaluable"],
                "comparison_contract_evaluable": profile["comparison_contract_evaluable"],
                "comparison_signature": deepcopy(profile["comparison_signature"]),
                "comparison_signature_sha256": profile["comparison_signature_sha256"],
                "preserved_unmapped_context": deepcopy(profile["preserved_unmapped_context"]),
                "pareto_status": None,
            }
            profiles.append(row_profile)
            comparator_profiles.append(_to_comparator_profile(row_profile, r2_contract))

        mechanical = compare_r2_profiles(comparator_profiles, r2_contract)
        if mechanical.get("cross_signature_comparison_count") != 0:
            audit_errors.append(
                "HOLDOUT_REPLAY_CROSS_SIGNATURE_COMPARISON_NONZERO:"
                + selected["checkpoint_id"]
            )
        if mechanical.get("ranking_generated") is not False:
            audit_errors.append(
                "HOLDOUT_REPLAY_RANKING_GENERATED:" + selected["checkpoint_id"]
            )
        if mechanical.get("winner_selected") is not False:
            audit_errors.append(
                "HOLDOUT_REPLAY_WINNER_SELECTED:" + selected["checkpoint_id"]
            )

        groups: list[dict[str, Any]] = []
        for group in mechanical["groups"]:
            exact_signature_groups += 1
            members = list(group["security_ids"])
            row = {
                "comparison_signature_sha256": group["comparison_signature_sha256"],
                "status": group["status"],
                "security_ids": sorted(members),
                "pareto_frontier": list(group.get("pareto_frontier", [])),
                "dominated_by": deepcopy(group.get("dominated_by", {})),
            }
            if group["status"] == "COMPARABLE_EXACT_SIGNATURE":
                comparable_groups += 1
                comparable_profiles += len(members)
                directional_pair_checks += len(members) * (len(members) - 1)
                frontier = set(group.get("pareto_frontier", []))
                frontier_profiles += len(frontier)
                for sid, dominators in group.get("dominated_by", {}).items():
                    dominance_edges += len(dominators)
                    if dominators:
                        dominated_profiles += 1
            else:
                singleton_groups += 1
            groups.append(row)

        unsupported = list(feature_layer.get("unsupported_selected_evidence_ids", []))
        unsupported_evidence_instances += len(unsupported)
        total_profiles += len(profiles)
        checkpoints.append(
            {
                "checkpoint_id": selected["checkpoint_id"],
                "at": selected["at"],
                "canonical_commit_sha": selected["canonical_commit_sha"],
                "opportunity_security_ids": list(selected["opportunity_security_ids"]),
                "selected_source_identity_set_sha256": selected["source_identity_set_sha256"],
                "selected_evidence_ids": list(snapshot["selected_evidence_ids"]),
                "unsupported_selected_evidence_ids": unsupported,
                "feature_row_count": len(feature_rows),
                "profile_count": len(profiles),
                "profiles": profiles,
                "groups": groups,
            }
        )

    if loader.read_count != len(expected_unique_sources):
        audit_errors.append(
            f"HOLDOUT_REPLAY_SOURCE_READ_ACCOUNTING_DRIFT:{loader.read_count}:{len(expected_unique_sources)}"
        )
    if len(checkpoints) != parent["checkpoint_count"]:
        audit_errors.append(
            f"HOLDOUT_REPLAY_CHECKPOINT_RECONSTRUCTION_COUNT_DRIFT:{len(checkpoints)}:{parent['checkpoint_count']}"
        )
    if total_profiles == 0:
        audit_errors.append("HOLDOUT_REPLAY_ZERO_R2_PROFILES")

    status = _classify(
        audit_errors=audit_errors,
        transform_failures=total_transform_failures,
        comparable_groups=comparable_groups,
        comparable_profiles=comparable_profiles,
    )
    pass_status = replay_contract["acceptance_contract"]["pass_status"]
    phase3d_r2_start_allowed = status == pass_status

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3_R2_INDEPENDENT_POINT_IN_TIME_HOLDOUT",
        "subphase": "FROZEN_R2_REPLAY_AND_FINAL_ACCEPTANCE",
        "status": status,
        "model_form": r2_contract["model"]["model_form"],
        "model_version": r2_contract["model"]["model_version"],
        "parent_selection_ledger_sha256": selection["selection_ledger_sha256"],
        "checkpoint_count": len(checkpoints),
        "selection_checkpoint_count": selection["selected_checkpoint_count"],
        "research_security_scope_count": selection["v2_security_scope_count"],
        "unique_source_identity_reads_expected": len(expected_unique_sources),
        "unique_source_identity_reads_actual": loader.read_count,
        "r2_profile_instances": total_profiles,
        "present_dimension_instances": total_present_dimensions,
        "missing_dimension_instances": total_missing_dimensions,
        "transform_failure_instances": total_transform_failures,
        "comparison_contract_evaluable_profiles": comparison_evaluable_profiles,
        "distinct_comparison_signature_count": len(distinct_signatures),
        "exact_signature_group_instances": exact_signature_groups,
        "comparable_exact_signature_group_instances": comparable_groups,
        "singleton_signature_group_instances": singleton_groups,
        "comparable_profile_instances": comparable_profiles,
        "pareto_directional_pair_checks": directional_pair_checks,
        "dominance_edge_count": dominance_edges,
        "frontier_profile_instances": frontier_profiles,
        "dominated_profile_instances": dominated_profiles,
        "unsupported_selected_evidence_instances": unsupported_evidence_instances,
        "cross_checkpoint_comparison_count": 0,
        "cross_signature_comparison_count": 0,
        "scalar_score_count": 0,
        "ranking_count": 0,
        "global_winner_count": 0,
        "historical_performance_metric_count": 0,
        "realized_outcome_record_count": 0,
        "phase3d_result_read_count": 0,
        "future_return_read_count": 0,
        "regret_read_count": 0,
        "calibration_read_count": 0,
        "audit_errors": sorted(set(audit_errors)),
        "phase3d_r2_start_allowed": phase3d_r2_start_allowed,
        "phase3d_r2_started": False,
        "phase3e_r2_started": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
        "checkpoints": checkpoints,
        "controls": deepcopy(CONTROLS),
    }
    result["replay_sha256"] = _sha256(
        {k: v for k, v in result.items() if k != "replay_sha256"}
    )
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_holdout_replay()
    target = write_default(result)
    print(
        "PHASE3_R2_INDEPENDENT_HOLDOUT_REPLAY_BUILT "
        f"status={result['status']} checkpoints={result['checkpoint_count']} "
        f"profiles={result['r2_profile_instances']} comparable_profiles={result['comparable_profile_instances']} "
        f"groups={result['exact_signature_group_instances']} comparable_groups={result['comparable_exact_signature_group_instances']} "
        f"pair_checks={result['pareto_directional_pair_checks']} dominance_edges={result['dominance_edge_count']} "
        f"transform_failures={result['transform_failure_instances']} audit_errors={len(result['audit_errors'])} "
        "outcomes=0 performance=0 "
        f"phase3d_r2_start_allowed={str(result['phase3d_r2_start_allowed']).lower()} "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['replay_sha256']} path={target}"
    )
