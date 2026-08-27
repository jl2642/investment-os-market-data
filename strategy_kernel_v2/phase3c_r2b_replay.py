"""Phase 3C-R2B point-in-time mechanical Pareto replay and full audit.

This stage consumes the accepted Phase 3C-R2A reconstruction and executes the
first real historical R2 comparison. Comparisons are checkpoint-local and only
within an exact comparison signature. The stage does not load realized outcomes,
build holdout history, scalarize dimensions, rank securities, select a global
winner, generate target weights, or create investment decisions.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.phase3b_r2_contract import (
    compare_r2_profiles,
    load_contract as load_r2_contract,
    validate_contract as validate_r2_contract,
)
from strategy_kernel_v2.phase3c_r2a_reconstruction import (
    build_default as build_r2a_default,
    load_replay_contract as load_r2a_contract,
    validate_replay_contract as validate_r2a_contract,
)

ROOT = Path(__file__).resolve().parent
REPLAY_CONTRACT_FILE = ROOT / "PHASE3C_R2B_REPLAY_CONTRACT.json"
GENERATED_FILE = ROOT / "generated/PHASE3C_R2B_MECHANICAL_REPLAY.json"

CONTROLS = {
    "model_specific_evidence_fetch_allowed": False,
    "later_evidence_backfill_allowed": False,
    "present_day_substitution_allowed": False,
    "subjective_mapping_allowed": False,
    "retrospective_probability_creation_allowed": False,
    "retrospective_confidence_creation_allowed": False,
    "retrospective_cost_score_creation_allowed": False,
    "realized_outcome_loading_allowed": False,
    "realized_outcome_tuning_allowed": False,
    "holdout_build_allowed": False,
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


def load_replay_contract(path: str | Path = REPLAY_CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_replay_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_MECHANICAL_REPLAY":
        errors.append("R2B_CONTRACT_NOT_FROZEN_BEFORE_REPLAY")
    if contract.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("R2B_MODEL_IDENTITY_DRIFT")
    if contract.get("model_version") != "R2.0.1_RESEARCH":
        errors.append("R2B_MODEL_VERSION_DRIFT")

    execution = contract.get("execution_round_contract", {})
    if execution.get("phase3c_r2_total_execution_rounds") != 2:
        errors.append("R2B_EXECUTION_ROUND_COUNT_DRIFT")
    if execution.get("this_round") != "R2B_MECHANICAL_REPLAY_FULL_AUDIT_AND_FINAL_ACCEPTANCE":
        errors.append("R2B_EXECUTION_ROUND_ID_DRIFT")
    if execution.get("mechanical_r2_replay_starts_in_this_round") is not True:
        errors.append("R2B_MECHANICAL_REPLAY_START_GUARD_FALSE")
    if execution.get("no_additional_phase3c_r2_execution_round_is_created") is not True:
        errors.append("R2B_UNAUTHORIZED_EXTRA_ROUND")

    parent = contract.get("parent_acceptance", {})
    expected_parent = {
        "checkpoint_count": 7,
        "unique_registered_historical_source_reads": 29,
        "r2_profile_instances": 33,
        "frozen_transform_rule_count": 20,
        "transform_failure_instances": 0,
        "r2a_pareto_comparison_count": 0,
        "realized_outcome_record_count": 0,
        "holdout_checkpoint_count": 0,
    }
    for key, expected in expected_parent.items():
        if parent.get(key) != expected:
            errors.append(f"R2B_PARENT_ACCEPTANCE_DRIFT:{key}")

    inputs = contract.get("replay_input_contract", {})
    for key in (
        "rebuild_parent_r2a_from_exact_registered_history",
        "parent_reconstruction_sha_must_match",
        "same_checkpoint_opportunity_set_only",
        "same_checkpoint_selected_evidence_only",
        "only_parent_r2a_profiles_may_enter_replay",
        "comparison_contract_evaluable_profiles_only",
        "model_specific_evidence_fetch_forbidden",
        "later_evidence_backfill_forbidden",
        "present_day_substitution_forbidden",
        "subjective_mapping_forbidden",
        "retrospective_probability_creation_forbidden",
        "retrospective_confidence_creation_forbidden",
        "retrospective_cost_score_creation_forbidden",
    ):
        if inputs.get(key) is not True:
            errors.append("R2B_INPUT_GUARD_FALSE:" + key)

    comparison = contract.get("comparison_contract", {})
    if comparison.get("method") != "PARETO_WITHIN_EXACT_COMPARISON_SIGNATURE":
        errors.append("R2B_COMPARISON_METHOD_DRIFT")
    if comparison.get("comparison_group_min_profiles") != 2:
        errors.append("R2B_MIN_GROUP_SIZE_DRIFT")
    for key in (
        "checkpoint_local_only",
        "cross_checkpoint_comparison_forbidden",
        "exact_signature_required",
        "singleton_signature_groups_are_audited_not_compared",
        "cross_signature_dominance_forbidden",
        "missing_dimension_fill_forbidden",
        "local_pareto_frontier_is_not_a_global_winner",
    ):
        if comparison.get(key) is not True:
            errors.append("R2B_COMPARISON_GUARD_FALSE:" + key)
    for key in (
        "scalar_policy_score_allowed",
        "dimension_weights_allowed",
        "ranking_allowed",
        "global_winner_selection_allowed",
        "target_weight_generation_allowed",
    ):
        if comparison.get(key) is not False:
            errors.append("R2B_FORBIDDEN_COMPARISON_FEATURE_TRUE:" + key)

    classification = contract.get("classification_contract", {})
    if classification.get("pass_status") != "PASS_MECHANICAL_REPLAY_OPERATIONAL":
        errors.append("R2B_PASS_STATUS_DRIFT")
    if classification.get("partial_status") != "PARTIAL_VALID_REPLAY_NO_MULTI_PROFILE_EXACT_SIGNATURE_GROUP":
        errors.append("R2B_PARTIAL_STATUS_DRIFT")
    if classification.get("fail_status") != "FAIL_REPLAY_CONTRACT_OR_AUDIT":
        errors.append("R2B_FAIL_STATUS_DRIFT")
    if classification.get("independent_holdout_start_allowed_only_on_pass") is not True:
        errors.append("R2B_HOLDOUT_GATE_DRIFT")
    if classification.get("phase4_entry_allowed") is not False:
        errors.append("R2B_PREMATURE_PHASE4")

    boundary = contract.get("phase_boundary", {})
    if boundary.get("r2b_executes_real_point_in_time_mechanical_replay") is not True:
        errors.append("R2B_REAL_REPLAY_BOUNDARY_FALSE")
    for key in (
        "r2b_generates_historical_performance",
        "r2b_loads_phase3d_realized_outcomes",
        "r2b_builds_independent_holdout",
        "r2b_selects_global_winner",
        "phase3_historical_validation_complete",
        "phase4_entry_allowed",
    ):
        if boundary.get(key) is not False:
            errors.append("R2B_PHASE_BOUNDARY_BROKEN:" + key)
    return errors


def _rule_map(r2_contract: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {rule["rule_id"]: rule for rule in r2_contract["transform_catalog"]}


def _to_comparator_profile(
    profile: Mapping[str, Any],
    r2_contract: Mapping[str, Any],
) -> dict[str, Any]:
    rules = _rule_map(r2_contract)
    dimensions = []
    for state in profile.get("dimension_states", []):
        rule_id = state["rule_id"]
        rule = rules.get(rule_id)
        if rule is None:
            raise AssertionError("R2B_UNKNOWN_RULE_ID:" + rule_id)
        for key in ("dimension_id", "layer", "direction", "scale_id"):
            if state.get(key) != rule.get(key):
                raise AssertionError(f"R2B_DIMENSION_METADATA_DRIFT:{profile.get('security_id')}:{rule_id}:{key}")
        if str(state.get("transform_semantics_version")) != str(rule.get("transform_semantics_version")):
            raise AssertionError(f"R2B_TRANSFORM_VERSION_DRIFT:{profile.get('security_id')}:{rule_id}")
        if state.get("state") != "PRESENT":
            continue
        dimensions.append({
            "rule_id": rule_id,
            "dimension_id": state["dimension_id"],
            "category": rule["category"],
            "layer": state["layer"],
            "direction": state["direction"],
            "scale_id": state["scale_id"],
            "transform_semantics_version": str(state["transform_semantics_version"]),
            "value": state["value"],
            "source_feature_key": state["source_feature_key"],
            "provenance_evidence_ids": list(state.get("provenance_evidence_ids", [])),
            "state": "PRESENT",
        })

    signature = sorted([
        [d["dimension_id"], d["layer"], d["direction"], d["scale_id"], d["transform_semantics_version"]]
        for d in dimensions
    ])
    signature_sha = _sha256(signature)
    if signature != profile.get("comparison_signature"):
        raise AssertionError("R2B_PARENT_SIGNATURE_CONTENT_DRIFT:" + str(profile.get("security_id")))
    if signature_sha != profile.get("comparison_signature_sha256"):
        raise AssertionError("R2B_PARENT_SIGNATURE_SHA_DRIFT:" + str(profile.get("security_id")))

    return {
        "security_id": profile["security_id"],
        "security_name": profile.get("security_name", profile["security_id"]),
        "provenance_evidence_ids": list(profile.get("provenance_evidence_ids", [])),
        "dimensions": sorted(dimensions, key=lambda d: (d["layer"], d["dimension_id"], d["scale_id"])),
        "transform_failures": [],
        "preserved_unmapped_context": deepcopy(profile.get("preserved_unmapped_context", {})),
        "profile_evaluable": bool(profile.get("profile_evaluable")),
        "comparison_contract_evaluable": bool(profile.get("comparison_contract_evaluable")),
        "comparison_signature": deepcopy(signature),
        "comparison_signature_sha256": signature_sha,
    }


def _classify(audit_errors: list[str], comparable_groups: int, comparable_profiles: int) -> str:
    if audit_errors:
        return "FAIL_REPLAY_CONTRACT_OR_AUDIT"
    if comparable_groups > 0 and comparable_profiles > 0:
        return "PASS_MECHANICAL_REPLAY_OPERATIONAL"
    return "PARTIAL_VALID_REPLAY_NO_MULTI_PROFILE_EXACT_SIGNATURE_GROUP"


def build_phase3c_r2b_replay(
    r2a_result: Mapping[str, Any],
    *,
    r2_contract: Mapping[str, Any] | None = None,
    r2b_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    r2_contract = dict(r2_contract or load_r2_contract())
    r2b_contract = dict(r2b_contract or load_replay_contract())
    r2a_contract = load_r2a_contract()

    errors = (
        validate_r2_contract(r2_contract)
        + validate_r2a_contract(r2a_contract)
        + validate_replay_contract(r2b_contract)
    )
    if errors:
        raise ValueError("INVALID_R2B_CONTRACT:" + ";".join(errors))

    if r2a_result.get("reconstruction_sha256") != r2b_contract["parent_r2a_reconstruction_sha256"]:
        raise AssertionError("R2B_PARENT_RECONSTRUCTION_SHA_MISMATCH")
    parent = r2b_contract["parent_acceptance"]
    parent_checks = {
        "checkpoint_count": r2a_result.get("checkpoint_count"),
        "unique_registered_historical_source_reads": r2a_result.get("unique_registered_historical_source_reads"),
        "r2_profile_instances": r2a_result.get("r2_profile_instances"),
        "frozen_transform_rule_count": r2a_result.get("frozen_transform_rule_count"),
        "transform_failure_instances": r2a_result.get("transform_failure_instances"),
        "r2a_pareto_comparison_count": r2a_result.get("pareto_comparison_count"),
        "realized_outcome_record_count": r2a_result.get("realized_outcome_record_count"),
        "holdout_checkpoint_count": r2a_result.get("holdout_checkpoint_count"),
    }
    for key, actual in parent_checks.items():
        if actual != parent[key]:
            raise AssertionError(f"R2B_PARENT_ACCEPTANCE_MISMATCH:{key}:{actual}:{parent[key]}")

    audit_errors: list[str] = []
    checkpoint_results = []
    profile_count = 0
    comparison_contract_evaluable_profiles = 0
    exact_signature_group_instances = 0
    comparable_exact_signature_group_instances = 0
    singleton_signature_group_instances = 0
    comparable_profile_instances = 0
    pareto_directional_pair_checks = 0
    dominance_edge_count = 0
    frontier_profile_instances = 0
    dominated_profile_instances = 0
    cross_checkpoint_comparison_count = 0
    cross_signature_comparison_count = 0
    unmapped_context_comparison_use_count = 0
    accounted_profiles: set[tuple[str, str]] = set()

    min_group = int(r2_contract["dimension_architecture"]["comparison_group_min_profiles"])

    for checkpoint in r2a_result["checkpoints"]:
        decision_point_id = checkpoint["decision_point_id"]
        selected_evidence = set(checkpoint["selected_evidence_ids"])
        raw_profiles = checkpoint["profiles"]
        security_ids = [str(p["security_id"]) for p in raw_profiles]
        if len(security_ids) != len(set(security_ids)):
            audit_errors.append("R2B_DUPLICATE_SECURITY_WITHIN_CHECKPOINT:" + decision_point_id)

        comparator_profiles = []
        profile_by_id = {}
        status_by_security: dict[str, str] = {}
        for raw in raw_profiles:
            sid = str(raw["security_id"])
            key = (decision_point_id, sid)
            if key in accounted_profiles:
                audit_errors.append("R2B_PROFILE_ACCOUNTED_TWICE:" + decision_point_id + ":" + sid)
            accounted_profiles.add(key)
            profile_count += 1
            if raw.get("transform_failure_count") != 0:
                audit_errors.append("R2B_PARENT_TRANSFORM_FAILURE:" + decision_point_id + ":" + sid)
            if set(raw.get("provenance_evidence_ids", [])) - selected_evidence:
                audit_errors.append("R2B_PROFILE_PROVENANCE_OUTSIDE_CHECKPOINT:" + decision_point_id + ":" + sid)
            for dim in raw.get("dimension_states", []):
                if set(dim.get("provenance_evidence_ids", [])) - selected_evidence:
                    audit_errors.append("R2B_DIMENSION_PROVENANCE_OUTSIDE_CHECKPOINT:" + decision_point_id + ":" + sid)
            cp = _to_comparator_profile(raw, r2_contract)
            comparator_profiles.append(cp)
            profile_by_id[sid] = cp
            if cp["comparison_contract_evaluable"]:
                comparison_contract_evaluable_profiles += 1
                status_by_security[sid] = "EVALUABLE_AWAITING_SIGNATURE_GROUP"
            else:
                status_by_security[sid] = "NOT_COMPARISON_CONTRACT_EVALUABLE"

        mechanical = compare_r2_profiles(comparator_profiles, r2_contract)
        if mechanical.get("cross_signature_comparison_count") != 0:
            audit_errors.append("R2B_COMPARATOR_CROSS_SIGNATURE_NONZERO:" + decision_point_id)
        if mechanical.get("ranking_generated") is not False or mechanical.get("winner_selected") is not False:
            audit_errors.append("R2B_COMPARATOR_RANKING_OR_WINNER:" + decision_point_id)
        if mechanical.get("historical_replay_generated") is not False:
            audit_errors.append("R2B_PHASE3B_HELPER_MISREPRESENTED_AS_HISTORY:" + decision_point_id)

        groups = []
        seen_group_members: set[str] = set()
        for group in mechanical["groups"]:
            exact_signature_group_instances += 1
            member_ids = list(group["security_ids"])
            if len(member_ids) != len(set(member_ids)):
                audit_errors.append("R2B_DUPLICATE_GROUP_MEMBER:" + decision_point_id)
            signature_sha = group["comparison_signature_sha256"]
            for sid in member_ids:
                member = profile_by_id.get(sid)
                if member is None:
                    audit_errors.append("R2B_GROUP_MEMBER_OUTSIDE_CHECKPOINT:" + decision_point_id + ":" + sid)
                    continue
                if not member.get("comparison_contract_evaluable"):
                    audit_errors.append("R2B_UNEVALUABLE_PROFILE_COMPARED:" + decision_point_id + ":" + sid)
                if member.get("comparison_signature_sha256") != signature_sha:
                    audit_errors.append("R2B_CROSS_SIGNATURE_GROUP:" + decision_point_id + ":" + sid)
                if sid in seen_group_members:
                    audit_errors.append("R2B_PROFILE_IN_MULTIPLE_SIGNATURE_GROUPS:" + decision_point_id + ":" + sid)
                seen_group_members.add(sid)

            row = {
                "comparison_signature_sha256": signature_sha,
                "status": group["status"],
                "security_ids": sorted(member_ids),
                "pareto_frontier": list(group.get("pareto_frontier", [])),
                "dominated_by": deepcopy(group.get("dominated_by", {})),
            }
            if group["status"] == "COMPARABLE_EXACT_SIGNATURE":
                if len(member_ids) < min_group:
                    audit_errors.append("R2B_COMPARABLE_GROUP_BELOW_MIN_SIZE:" + decision_point_id)
                comparable_exact_signature_group_instances += 1
                comparable_profile_instances += len(member_ids)
                pair_checks = len(member_ids) * (len(member_ids) - 1)
                pareto_directional_pair_checks += pair_checks
                frontier = set(group.get("pareto_frontier", []))
                if frontier - set(member_ids):
                    audit_errors.append("R2B_FRONTIER_MEMBER_OUTSIDE_GROUP:" + decision_point_id)
                frontier_profile_instances += len(frontier)
                dominated_by = group.get("dominated_by", {})
                for sid in member_ids:
                    dominators = set(dominated_by.get(sid, []))
                    if dominators - set(member_ids):
                        audit_errors.append("R2B_DOMINATOR_OUTSIDE_GROUP:" + decision_point_id + ":" + sid)
                    dominance_edge_count += len(dominators)
                    if dominators:
                        dominated_profile_instances += 1
                        status_by_security[sid] = "DOMINATED_WITHIN_EXACT_SIGNATURE"
                    else:
                        status_by_security[sid] = "PARETO_FRONTIER_LOCAL"
                row["directional_pair_checks"] = pair_checks
            elif group["status"] == "INSUFFICIENT_GROUP_SIZE":
                if len(member_ids) >= min_group:
                    audit_errors.append("R2B_SINGLETON_STATUS_ON_COMPARABLE_SIZE:" + decision_point_id)
                singleton_signature_group_instances += 1
                for sid in member_ids:
                    status_by_security[sid] = "SINGLETON_EXACT_SIGNATURE"
                row["directional_pair_checks"] = 0
            else:
                audit_errors.append("R2B_UNKNOWN_GROUP_STATUS:" + decision_point_id + ":" + str(group["status"]))
            groups.append(row)

        expected_grouped = {
            sid for sid, profile in profile_by_id.items() if profile["comparison_contract_evaluable"]
        }
        if seen_group_members != expected_grouped:
            audit_errors.append("R2B_EVALUABLE_PROFILE_GROUP_ACCOUNTING_MISMATCH:" + decision_point_id)

        checkpoint_results.append({
            "decision_point_id": decision_point_id,
            "at": checkpoint["at"],
            "selected_evidence_ids": sorted(checkpoint["selected_evidence_ids"]),
            "profile_count": len(raw_profiles),
            "comparison_contract_evaluable_profile_count": sum(
                bool(p["comparison_contract_evaluable"]) for p in raw_profiles
            ),
            "exact_signature_groups": groups,
            "profile_replay_status": [
                {"security_id": sid, "status": status_by_security[sid]}
                for sid in sorted(status_by_security)
            ],
        })

    if profile_count != int(r2a_result["r2_profile_instances"]):
        audit_errors.append("R2B_PARENT_PROFILE_ACCOUNTING_MISMATCH")
    if comparison_contract_evaluable_profiles != int(r2a_result["comparison_contract_evaluable_profiles"]):
        audit_errors.append("R2B_PARENT_EVALUABLE_PROFILE_ACCOUNTING_MISMATCH")
    expected_pair_checks = sum(
        group["directional_pair_checks"]
        for checkpoint in checkpoint_results
        for group in checkpoint["exact_signature_groups"]
        if group["status"] == "COMPARABLE_EXACT_SIGNATURE"
    )
    if pareto_directional_pair_checks != expected_pair_checks:
        audit_errors.append("R2B_DIRECTIONAL_PAIR_CHECK_ACCOUNTING_MISMATCH")

    status = _classify(
        audit_errors,
        comparable_exact_signature_group_instances,
        comparable_profile_instances,
    )
    independent_holdout_start_allowed = status == "PASS_MECHANICAL_REPLAY_OPERATIONAL"

    result = {
        "schema_version": "1.0.0",
        "phase": "3C-R2B",
        "mode": "POINT_IN_TIME_MECHANICAL_PARETO_REPLAY_FULL_AUDIT",
        "status": status,
        "model_form": r2_contract["model"]["model_form"],
        "model_version": r2_contract["model"]["model_version"],
        "parent_r2a_reconstruction_sha256": r2a_result["reconstruction_sha256"],
        "checkpoint_count": r2a_result["checkpoint_count"],
        "unique_registered_historical_source_reads": r2a_result["unique_registered_historical_source_reads"],
        "profile_count": profile_count,
        "comparison_contract_evaluable_profiles": comparison_contract_evaluable_profiles,
        "exact_signature_group_instances": exact_signature_group_instances,
        "comparable_exact_signature_group_instances": comparable_exact_signature_group_instances,
        "singleton_signature_group_instances": singleton_signature_group_instances,
        "comparable_profile_instances": comparable_profile_instances,
        "pareto_directional_pair_checks": pareto_directional_pair_checks,
        "dominance_edge_count": dominance_edge_count,
        "frontier_profile_instances": frontier_profile_instances,
        "dominated_profile_instances": dominated_profile_instances,
        "cross_checkpoint_comparison_count": cross_checkpoint_comparison_count,
        "cross_signature_comparison_count": cross_signature_comparison_count,
        "unmapped_context_comparison_use_count": unmapped_context_comparison_use_count,
        "transform_failure_instances": r2a_result["transform_failure_instances"],
        "historical_performance_metric_count": 0,
        "realized_outcome_record_count": 0,
        "holdout_checkpoint_count": 0,
        "outcome_tuning_count": 0,
        "ranking_generated": False,
        "global_winner_selected": False,
        "target_weights_generated": False,
        "local_pareto_frontier_is_global_winner": False,
        "mechanical_replay_executed": True,
        "development_corpus_replay_complete": status in {
            "PASS_MECHANICAL_REPLAY_OPERATIONAL",
            "PARTIAL_VALID_REPLAY_NO_MULTI_PROFILE_EXACT_SIGNATURE_GROUP",
        },
        "historical_performance_claimed": False,
        "independent_holdout_start_allowed": independent_holdout_start_allowed,
        "independent_holdout_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
        "audit": {
            "passed": not audit_errors,
            "errors": audit_errors,
            "all_parent_profiles_accounted_for": profile_count == int(r2a_result["r2_profile_instances"]),
            "all_evaluable_profiles_group_accounted_for": (
                comparison_contract_evaluable_profiles
                == int(r2a_result["comparison_contract_evaluable_profiles"])
            ),
            "directional_pair_check_accounting_passed": (
                pareto_directional_pair_checks == expected_pair_checks
            ),
        },
        "checkpoints": checkpoint_results,
        "controls": deepcopy(CONTROLS),
    }
    result["replay_sha256"] = _sha256({k: v for k, v in result.items() if k != "replay_sha256"})
    return result


def build_default(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    r2a = build_r2a_default(repo)
    return build_phase3c_r2b_replay(r2a)


def write_default(result: Mapping[str, Any], path: str | Path = GENERATED_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_default()
    target = write_default(result)
    print(
        "PHASE3C_R2B_REPLAY_BUILT "
        f"status={result['status']} checkpoints={result['checkpoint_count']} profiles={result['profile_count']} "
        f"comparison_evaluable={result['comparison_contract_evaluable_profiles']} "
        f"signature_groups={result['exact_signature_group_instances']} "
        f"comparable_groups={result['comparable_exact_signature_group_instances']} "
        f"singleton_groups={result['singleton_signature_group_instances']} "
        f"comparable_profiles={result['comparable_profile_instances']} "
        f"pair_checks={result['pareto_directional_pair_checks']} dominance_edges={result['dominance_edge_count']} "
        f"frontier_instances={result['frontier_profile_instances']} dominated_instances={result['dominated_profile_instances']} "
        f"holdout_start_allowed={str(result['independent_holdout_start_allowed']).lower()} "
        f"phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['replay_sha256']} path={target}"
    )
