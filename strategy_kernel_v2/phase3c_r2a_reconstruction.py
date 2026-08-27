"""Phase 3C-R2A point-in-time R2 input reconstruction.

This stage reuses the accepted Phase 3A/3C historical source and model-neutral
feature extraction path, then applies only the frozen Phase 3B-R2 deterministic
transform catalog. It intentionally does NOT execute Pareto dominance, load
realized outcomes, build holdout history, rank securities, or generate decisions.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from strategy_kernel_v2.historical_feature_extractor import extract_model_neutral_features
from strategy_kernel_v2.historical_replay import (
    CachingRegisteredSourceLoader,
    load_default_phase3c_inputs,
)
from strategy_kernel_v2.phase3b_r2_contract import (
    load_contract as load_r2_contract,
    transform_model_neutral_row,
    validate_contract as validate_r2_contract,
)
from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger

ROOT = Path(__file__).resolve().parent
REPLAY_CONTRACT_FILE = ROOT / "PHASE3C_R2A_REPLAY_CONTRACT.json"
GENERATED_FILE = ROOT / "generated/PHASE3C_R2A_RECONSTRUCTION.json"

FALSE_CONTROLS = {
    "model_specific_evidence_fetch_allowed": False,
    "later_evidence_backfill_allowed": False,
    "subjective_mapping_allowed": False,
    "retrospective_probability_creation_allowed": False,
    "retrospective_confidence_creation_allowed": False,
    "retrospective_cost_score_creation_allowed": False,
    "realized_outcome_loading_allowed": False,
    "realized_outcome_tuning_allowed": False,
    "pareto_dominance_execution_allowed": False,
    "cross_signature_comparison_allowed": False,
    "scalar_policy_score_allowed": False,
    "dimension_weights_allowed": False,
    "ranking_allowed": False,
    "winner_selection_allowed": False,
    "target_weight_generation_allowed": False,
    "holdout_build_allowed": False,
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


def load_replay_contract(path: str | Path = REPLAY_CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_replay_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_R2A_RECONSTRUCTION_ONLY_NO_PARETO_NO_OUTCOMES":
        errors.append("R2A_CONTRACT_NOT_FROZEN")
    if contract.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("R2A_MODEL_IDENTITY_DRIFT")
    corpus = contract.get("development_corpus", {})
    if corpus.get("checkpoint_count") != 7:
        errors.append("R2A_CHECKPOINT_CONTRACT_DRIFT")
    if corpus.get("expected_unique_registered_historical_source_reads") != 29:
        errors.append("R2A_SOURCE_READ_CONTRACT_DRIFT")
    if corpus.get("independent_holdout") is not False or corpus.get("may_count_as_independent_validation") is not False:
        errors.append("R2A_SEED_MISCLASSIFIED_AS_HOLDOUT")

    inputs = contract.get("input_contract", {})
    for key in (
        "phase3a_selected_evidence_only",
        "exact_registered_commit_path_reads_only",
        "reuse_historical_feature_extractor",
        "model_neutral_feature_rows_required",
        "model_specific_evidence_fetch_forbidden",
        "later_evidence_backfill_forbidden",
        "present_day_state_substitution_forbidden",
        "subjective_mapping_forbidden",
        "retrospective_probability_creation_forbidden",
        "retrospective_confidence_creation_forbidden",
        "retrospective_cost_score_creation_forbidden",
    ):
        if inputs.get(key) is not True:
            errors.append("R2A_INPUT_GUARD_FALSE:" + key)

    transforms = contract.get("transform_contract", {})
    if transforms.get("transform_rule_count") != 20 or transforms.get("frozen_catalog_only") is not True:
        errors.append("R2A_TRANSFORM_CATALOG_DRIFT")
    for key in (
        "new_transform_rules_allowed",
        "threshold_tuning_allowed",
        "realized_outcome_tuning_allowed",
    ):
        if transforms.get(key) is not False:
            errors.append("R2A_UNSAFE_TRANSFORM_TRUE:" + key)
    if transforms.get("missingness_must_remain_explicit") is not True:
        errors.append("R2A_MISSINGNESS_GUARD_FALSE")

    boundary = contract.get("phase_boundary", {})
    if boundary.get("r2a_reads_point_in_time_historical_sources") is not True:
        errors.append("R2A_HISTORY_READ_BOUNDARY_FALSE")
    if boundary.get("r2a_reconstructs_r2_profiles") is not True:
        errors.append("R2A_RECONSTRUCTION_BOUNDARY_FALSE")
    for key in (
        "r2a_executes_pareto",
        "r2a_generates_historical_performance",
        "r2a_loads_phase3d_realized_outcomes",
        "r2a_builds_independent_holdout",
        "r2a_selects_winner",
        "phase4_entry_allowed",
    ):
        if boundary.get(key) is not False:
            errors.append("R2A_PHASE_BOUNDARY_BROKEN:" + key)
    return errors


def _dimension_state_ledger(
    row: Mapping[str, Any],
    profile: Mapping[str, Any],
    r2_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    present_by_rule = {item["rule_id"]: item for item in profile.get("dimensions", [])}
    failure_by_rule = {
        item["rule_id"]: item["reason"] for item in profile.get("transform_failures", [])
    }
    feature_provenance = row.get("feature_provenance", {})
    states: list[dict[str, Any]] = []
    for rule in r2_contract["transform_catalog"]:
        rule_id = rule["rule_id"]
        source = rule["source_feature_key"]
        base = {
            "rule_id": rule_id,
            "source_feature_key": source,
            "dimension_id": rule["dimension_id"],
            "layer": rule["layer"],
            "direction": rule["direction"],
            "scale_id": rule["scale_id"],
            "transform_semantics_version": str(rule["transform_semantics_version"]),
        }
        if rule_id in present_by_rule:
            dim = present_by_rule[rule_id]
            states.append({
                **base,
                "state": "PRESENT",
                "applicability_state": "APPLICABLE_BY_OBSERVED_SOURCE",
                "value": dim["value"],
                "provenance_evidence_ids": list(dim["provenance_evidence_ids"]),
            })
        elif rule_id in failure_by_rule:
            states.append({
                **base,
                "state": "TRANSFORM_FAILURE",
                "applicability_state": "UNKNOWN_APPLICABILITY",
                "reason": failure_by_rule[rule_id],
                "provenance_evidence_ids": list(feature_provenance.get(source, [])),
            })
        else:
            states.append({
                **base,
                "state": "MISSING",
                "applicability_state": "UNKNOWN_APPLICABILITY",
                "provenance_evidence_ids": [],
            })
    return states


def build_phase3c_r2a_reconstruction(
    registry: Mapping[str, Any] | list[Mapping[str, Any]],
    decision_points: Mapping[str, Any] | list[Mapping[str, Any]],
    *,
    source_loader: Callable[[Mapping[str, Any]], Any],
    r2_contract: Mapping[str, Any] | None = None,
    replay_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    r2_contract = dict(r2_contract or load_r2_contract())
    replay_contract = dict(replay_contract or load_replay_contract())
    r2_errors = validate_r2_contract(r2_contract)
    r2a_errors = validate_replay_contract(replay_contract)
    if r2_errors or r2a_errors:
        raise ValueError("INVALID_R2A_CONTRACT:" + ";".join(r2_errors + r2a_errors))
    if len(r2_contract.get("transform_catalog", [])) != 20:
        raise ValueError("R2A_REQUIRES_FROZEN_20_RULE_CATALOG")

    evidence_records = registry["records"] if isinstance(registry, Mapping) else registry
    points = decision_points["decision_points"] if isinstance(decision_points, Mapping) else decision_points
    ledger = build_point_in_time_ledger(evidence_records, points)

    checkpoints: list[dict[str, Any]] = []
    feature_security_instances = 0
    present_dimension_instances = 0
    missing_dimension_instances = 0
    transform_failure_instances = 0
    comparison_contract_evaluable_profiles = 0
    signature_hashes: set[str] = set()
    subjective_feature_fill_count = 0
    retrospective_probability_backfill_count = 0
    retrospective_scenario_backfill_count = 0

    for snapshot in ledger["snapshots"]:
        feature_layer = extract_model_neutral_features(snapshot, source_loader=source_loader)
        feature_rows = feature_layer.get("feature_rows", {})
        profiles: list[dict[str, Any]] = []
        for security_id in sorted(feature_rows):
            row = feature_rows[security_id]
            profile = transform_model_neutral_row(row, r2_contract)
            state_ledger = _dimension_state_ledger(row, profile, r2_contract)
            for item in profile.get("dimensions", []):
                outside = set(item.get("provenance_evidence_ids", [])) - set(snapshot["selected_evidence_ids"])
                if outside:
                    raise AssertionError(
                        f"R2A_DIMENSION_PROVENANCE_OUTSIDE_CHECKPOINT:{security_id}:{item['rule_id']}"
                    )
            present = sum(item["state"] == "PRESENT" for item in state_ledger)
            missing = sum(item["state"] == "MISSING" for item in state_ledger)
            failures = sum(item["state"] == "TRANSFORM_FAILURE" for item in state_ledger)
            present_dimension_instances += present
            missing_dimension_instances += missing
            transform_failure_instances += failures
            if profile.get("comparison_contract_evaluable"):
                comparison_contract_evaluable_profiles += 1
            signature_hashes.add(profile["comparison_signature_sha256"])
            profiles.append({
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
            })

        feature_security_instances += len(profiles)
        subjective_feature_fill_count += int(feature_layer.get("subjective_feature_fill_count", 0))
        retrospective_probability_backfill_count += int(feature_layer.get("retrospective_probability_backfill_count", 0))
        retrospective_scenario_backfill_count += int(feature_layer.get("retrospective_scenario_backfill_count", 0))
        checkpoints.append({
            "decision_point_id": snapshot["decision_point_id"],
            "at": snapshot["at"],
            "opportunity_security_ids": sorted(snapshot["opportunity_security_ids"]),
            "selected_evidence_ids": sorted(snapshot["selected_evidence_ids"]),
            "feature_row_count": len(feature_rows),
            "profiles": profiles,
            "unsupported_selected_evidence_ids": list(feature_layer.get("unsupported_selected_evidence_ids", [])),
        })

    source_reads = getattr(source_loader, "read_count", None)
    result = {
        "schema_version": "1.0.0",
        "phase": "3C-R2A",
        "mode": "POINT_IN_TIME_R2_PROFILE_RECONSTRUCTION_ONLY",
        "status": "R2A_RECONSTRUCTION_COMPLETE_AWAITING_R2B_MECHANICAL_PARETO",
        "model_form": r2_contract["model"]["model_form"],
        "model_version": r2_contract["model"]["model_version"],
        "checkpoint_count": len(checkpoints),
        "unique_registered_historical_source_reads": source_reads,
        "feature_security_instances": feature_security_instances,
        "r2_profile_instances": feature_security_instances,
        "frozen_transform_rule_count": len(r2_contract["transform_catalog"]),
        "present_dimension_instances": present_dimension_instances,
        "missing_dimension_instances": missing_dimension_instances,
        "transform_failure_instances": transform_failure_instances,
        "comparison_contract_evaluable_profiles": comparison_contract_evaluable_profiles,
        "distinct_comparison_signature_count": len(signature_hashes),
        "model_specific_evidence_fetch_count": 0,
        "subjective_feature_fill_count": subjective_feature_fill_count,
        "retrospective_probability_backfill_count": retrospective_probability_backfill_count,
        "retrospective_scenario_backfill_count": retrospective_scenario_backfill_count,
        "later_evidence_backfill_count": 0,
        "pareto_comparison_count": 0,
        "cross_signature_comparison_count": 0,
        "historical_performance_metric_count": 0,
        "realized_outcome_record_count": 0,
        "holdout_checkpoint_count": 0,
        "ranking_generated": False,
        "winner_selected": False,
        "target_weights_generated": False,
        "phase3c_r2b_start_allowed_if_validation_passes": True,
        "independent_holdout_start_allowed": False,
        "phase4_entry_allowed": False,
        "checkpoints": checkpoints,
        "controls": deepcopy(FALSE_CONTROLS),
    }
    result["reconstruction_sha256"] = _sha256({k: v for k, v in result.items() if k != "reconstruction_sha256"})
    return result


def build_default(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    registry, points = load_default_phase3c_inputs(repo)
    loader = CachingRegisteredSourceLoader(repo)
    return build_phase3c_r2a_reconstruction(registry, points, source_loader=loader)


def write_default(result: Mapping[str, Any], path: str | Path = GENERATED_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_default()
    target = write_default(result)
    print(
        "PHASE3C_R2A_RECONSTRUCTION_BUILT "
        f"checkpoints={result['checkpoint_count']} source_reads={result['unique_registered_historical_source_reads']} "
        f"feature_instances={result['feature_security_instances']} profiles={result['r2_profile_instances']} "
        f"present_dimensions={result['present_dimension_instances']} missing_dimensions={result['missing_dimension_instances']} "
        f"transform_failures={result['transform_failure_instances']} pareto_comparisons=0 holdout=0 "
        f"sha256={result['reconstruction_sha256']} path={target}"
    )
