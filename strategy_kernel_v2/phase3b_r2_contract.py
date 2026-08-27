"""Phase 3B-R2 revised model contract mechanics.

Contract-only and shadow/research-only. This module does not read historical sources.
It transforms an already model-neutral feature row using a frozen rule catalog and
compares only profiles with an exact common comparison signature. Missingness and
unknown applicability remain explicit; no cross-signature dominance is allowed.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3B_R2_MODEL_CONTRACT.json"

FALSE_CONTROLS = {
    "historical_source_read_allowed": False,
    "model_specific_evidence_fetch_allowed": False,
    "later_evidence_backfill_allowed": False,
    "retrospective_probability_creation_allowed": False,
    "retrospective_confidence_creation_allowed": False,
    "retrospective_cost_score_creation_allowed": False,
    "subjective_mapping_allowed": False,
    "missing_dimension_fill_allowed": False,
    "cross_signature_dominance_allowed": False,
    "scalar_policy_score_allowed": False,
    "dimension_weights_allowed": False,
    "target_weight_generation_allowed": False,
    "winner_selection_allowed": False,
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


def load_contract(path: str | Path = CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(field + "_MUST_BE_NUMBER")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(field + "_MUST_BE_FINITE")
    return number


def _apply_operation(value: Any, operation: Mapping[str, Any], rule_id: str) -> float:
    kind = operation.get("type")
    if kind == "IDENTITY_FINITE_NUMBER":
        return _finite_number(value, rule_id)
    if kind == "IDENTITY_NONNEGATIVE_NUMBER":
        number = _finite_number(value, rule_id)
        if number < 0:
            raise ValueError(rule_id + "_NEGATIVE")
        return number
    if kind == "IDENTITY_BOUNDED_NUMBER":
        number = _finite_number(value, rule_id)
        lo = float(operation["min"])
        hi = float(operation["max"])
        if number < lo or number > hi:
            raise ValueError(rule_id + "_OUT_OF_RANGE")
        return number
    if kind == "BOOLEAN_TO_0_1":
        if not isinstance(value, bool):
            raise ValueError(rule_id + "_MUST_BE_BOOLEAN")
        return 1.0 if value else 0.0
    if kind == "MIN_LIST_FIELD":
        if not isinstance(value, list) or not value:
            raise ValueError(rule_id + "_LIST_REQUIRED")
        field = str(operation["field"])
        numbers = []
        for item in value:
            if not isinstance(item, Mapping) or field not in item:
                raise ValueError(rule_id + "_LIST_FIELD_REQUIRED")
            numbers.append(_finite_number(item[field], rule_id + "_" + field))
        return min(numbers)
    if kind == "PREFIX_GATE":
        if not isinstance(value, str):
            raise ValueError(rule_id + "_STRING_REQUIRED")
        pass_prefixes = operation.get("pass_prefixes")
        fail_prefixes = operation.get("fail_prefixes")
        if pass_prefixes is None:
            pass_prefixes = [operation.get("pass_prefix")]
        if fail_prefixes is None:
            fail_prefixes = [operation.get("fail_prefix")]
        if (
            not isinstance(pass_prefixes, list)
            or not pass_prefixes
            or not all(isinstance(prefix, str) and prefix for prefix in pass_prefixes)
        ):
            raise ValueError(rule_id + "_PASS_PREFIX_SET_REQUIRED")
        if (
            not isinstance(fail_prefixes, list)
            or not fail_prefixes
            or not all(isinstance(prefix, str) and prefix for prefix in fail_prefixes)
        ):
            raise ValueError(rule_id + "_FAIL_PREFIX_SET_REQUIRED")
        if any(value.startswith(prefix) for prefix in pass_prefixes):
            return 1.0
        if any(value.startswith(prefix) for prefix in fail_prefixes):
            return 0.0
        raise ValueError(rule_id + "_UNRECOGNIZED_GATE_STATE")
    raise ValueError("UNSUPPORTED_TRANSFORM_OPERATION:" + str(kind))


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    model = contract.get("model", {})
    if contract.get("status") != "FROZEN_REVISED_MODEL_CONTRACT_NO_HISTORICAL_REPLAY":
        errors.append("R2_CONTRACT_NOT_FROZEN")
    if model.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("R2_MODEL_IDENTITY_DRIFT")
    if model.get("new_identity") is not True or model.get("overwrites_prior_model") is not False:
        errors.append("R2_NEW_IDENTITY_GUARD_FAILED")

    preserved = contract.get("preserved_reference_forms", [])
    expected = [
        "LEGACY_POLICY_BASELINE",
        "PHASE2_PROBABILISTIC_VECTOR",
        "SIMPLE_NON_PROBABILISTIC_PARETO",
    ]
    if preserved != expected:
        errors.append("R2_REFERENCE_FORMS_DRIFT")

    shared = contract.get("shared_input_contract", {})
    for key in (
        "same_timestamp_required",
        "same_opportunity_set_required",
        "same_selected_evidence_required",
        "model_specific_evidence_fetch_forbidden",
        "feature_provenance_must_resolve_inside_shared_packet",
        "later_evidence_backfill_forbidden",
    ):
        if shared.get(key) is not True:
            errors.append("R2_SHARED_INPUT_GUARD_FALSE:" + key)

    architecture = contract.get("dimension_architecture", {})
    if architecture.get("absence_is_not_zero") is not True:
        errors.append("R2_ABSENCE_ZERO_DRIFT")
    if architecture.get("absence_is_not_automatically_not_applicable") is not True:
        errors.append("R2_ABSENCE_APPLICABILITY_DRIFT")
    if architecture.get("comparison_evaluable_min_present_core_dimensions") != 2:
        errors.append("R2_MIN_CORE_DIMENSION_DRIFT")
    if architecture.get("comparison_requires_evidence_or_completeness_dimension") is not True:
        errors.append("R2_EVIDENCE_DIMENSION_GUARD_FALSE")

    semantics = contract.get("comparison_semantics", {})
    if semantics.get("method") != "PARETO_WITHIN_EXACT_COMPARISON_SIGNATURE":
        errors.append("R2_COMPARISON_METHOD_DRIFT")
    for key in (
        "cross_signature_dominance_forbidden",
        "missing_dimension_fill_forbidden",
    ):
        if semantics.get(key) is not True:
            errors.append("R2_COMPARISON_GUARD_FALSE:" + key)
    for key in (
        "scalar_policy_score_allowed",
        "dimension_weights_allowed",
        "ranking_generated",
        "target_weights_generated",
        "winner_selection_allowed_in_3b_r2",
    ):
        if semantics.get(key) is not False:
            errors.append("R2_FORBIDDEN_COMPARISON_FEATURE_TRUE:" + key)

    rule_ids: set[str] = set()
    forbidden_source_fragments = ("phase3d", "realized_outcome", "forward_return")
    for rule in contract.get("transform_catalog", []):
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            errors.append("R2_RULE_ID_REQUIRED")
            continue
        if rule_id in rule_ids:
            errors.append("R2_DUPLICATE_RULE_ID:" + rule_id)
        rule_ids.add(rule_id)
        source = str(rule.get("source_feature_key", ""))
        if not source:
            errors.append("R2_SOURCE_FEATURE_REQUIRED:" + rule_id)
        if any(fragment in source.lower() for fragment in forbidden_source_fragments):
            errors.append("R2_OUTCOME_TUNED_SOURCE_FORBIDDEN:" + rule_id)
        if rule.get("layer") not in {"CORE_DECISION", "PORTFOLIO_OVERLAY", "EXECUTION_OVERLAY"}:
            errors.append("R2_LAYER_INVALID:" + rule_id)
        if rule.get("direction") not in {"MAXIMIZE", "MINIMIZE"}:
            errors.append("R2_DIRECTION_INVALID:" + rule_id)
        if not rule.get("scale_id") or not rule.get("transform_semantics_version"):
            errors.append("R2_SCALE_OR_VERSION_REQUIRED:" + rule_id)
        if not isinstance(rule.get("operation"), Mapping):
            errors.append("R2_OPERATION_REQUIRED:" + rule_id)

    firewall = contract.get("development_corpus_firewall", {})
    if firewall.get("seven_seed_checkpoints_are_independent_validation") is not False:
        errors.append("R2_SEED_MISCLASSIFIED_AS_HOLDOUT")
    for key in (
        "phase3d_realized_outcomes_may_select_fields",
        "phase3d_realized_outcomes_may_select_thresholds",
        "phase3d_realized_outcomes_may_select_mappings",
        "same_seed_tuning_may_count_as_validation",
    ):
        if firewall.get(key) is not False:
            errors.append("R2_FIREWALL_BROKEN:" + key)

    boundary = contract.get("phase_boundary", {})
    if boundary.get("phase3b_r2_defines_contract") is not True:
        errors.append("R2_PHASE_BOUNDARY_NOT_CONTRACT")
    for key in (
        "phase3b_r2_reads_historical_sources",
        "phase3b_r2_executes_real_historical_replay",
        "phase3b_r2_claims_replay_coverage",
        "phase3b_r2_claims_performance",
        "phase3b_r2_selects_winner",
        "phase4_entry_allowed",
    ):
        if boundary.get(key) is not False:
            errors.append("R2_PHASE_BOUNDARY_BROKEN:" + key)
    return errors


def transform_model_neutral_row(
    row: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply only frozen R2 transforms to one already-extracted feature row."""
    contract = dict(contract or load_contract())
    errors = validate_contract(contract)
    if errors:
        raise ValueError("INVALID_R2_CONTRACT:" + ";".join(errors))

    features = row.get("features", {})
    feature_provenance = row.get("feature_provenance", {})
    packet_provenance = set(row.get("provenance_evidence_ids", []))
    if not isinstance(features, Mapping) or not isinstance(feature_provenance, Mapping):
        raise ValueError("R2_MODEL_NEUTRAL_FEATURE_ROW_REQUIRED")

    dimensions: list[dict[str, Any]] = []
    missing_rule_ids: list[str] = []
    transform_failures: list[dict[str, str]] = []
    emitted_keys: set[tuple[str, str, str, str, str]] = set()

    for rule in contract["transform_catalog"]:
        source = rule["source_feature_key"]
        if source not in features:
            missing_rule_ids.append(rule["rule_id"])
            continue
        provenance = feature_provenance.get(source)
        if not isinstance(provenance, list) or not provenance:
            raise ValueError("R2_FEATURE_PROVENANCE_REQUIRED:" + source)
        outside = set(provenance) - packet_provenance
        if outside:
            raise ValueError("R2_FEATURE_PROVENANCE_OUTSIDE_ROW:" + source)
        try:
            transformed = _apply_operation(features[source], rule["operation"], rule["rule_id"])
        except (TypeError, ValueError) as exc:
            transform_failures.append({"rule_id": rule["rule_id"], "reason": str(exc)})
            continue
        key = (
            rule["dimension_id"],
            rule["layer"],
            rule["direction"],
            rule["scale_id"],
            str(rule["transform_semantics_version"]),
        )
        if key in emitted_keys:
            raise ValueError("R2_DUPLICATE_DIMENSION_SIGNATURE:" + rule["dimension_id"])
        emitted_keys.add(key)
        dimensions.append({
            "rule_id": rule["rule_id"],
            "dimension_id": rule["dimension_id"],
            "category": rule["category"],
            "layer": rule["layer"],
            "direction": rule["direction"],
            "scale_id": rule["scale_id"],
            "transform_semantics_version": str(rule["transform_semantics_version"]),
            "value": transformed,
            "source_feature_key": source,
            "provenance_evidence_ids": sorted(provenance),
            "state": "PRESENT",
        })

    preserved = {
        key: deepcopy(features[key])
        for key in contract.get("preserved_unmapped_context", [])
        if key in features
    }
    core = [d for d in dimensions if d["layer"] == "CORE_DECISION"]
    has_evidence = any(d["category"] == "EVIDENCE_OR_COMPLETENESS" for d in core)
    profile_evaluable = len(core) >= int(contract["dimension_architecture"]["profile_evaluable_min_present_core_dimensions"])
    comparison_contract_evaluable = (
        len(core) >= int(contract["dimension_architecture"]["comparison_evaluable_min_present_core_dimensions"])
        and has_evidence
        and not transform_failures
    )
    signature = sorted(
        [
            [d["dimension_id"], d["layer"], d["direction"], d["scale_id"], d["transform_semantics_version"]]
            for d in dimensions
        ]
    )
    out = {
        "schema_version": "1.0.0",
        "phase": "3B-R2",
        "model_form": contract["model"]["model_form"],
        "security_id": row.get("security_id"),
        "security_name": row.get("security_name", row.get("security_id")),
        "provenance_evidence_ids": sorted(packet_provenance),
        "dimensions": sorted(dimensions, key=lambda d: (d["layer"], d["dimension_id"], d["scale_id"])),
        "missing_rule_ids": sorted(missing_rule_ids),
        "transform_failures": transform_failures,
        "preserved_unmapped_context": preserved,
        "profile_evaluable": profile_evaluable,
        "comparison_contract_evaluable": comparison_contract_evaluable,
        "comparison_signature": signature,
        "comparison_signature_sha256": _sha256(signature),
        "missingness_preserved": True,
        "absent_dimensions_treated_as_zero": False,
        "absent_dimensions_treated_as_not_applicable": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
    return out


def _dominates(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    av = {d["dimension_id"]: d for d in a["dimensions"]}
    bv = {d["dimension_id"]: d for d in b["dimensions"]}
    if set(av) != set(bv):
        raise ValueError("R2_CROSS_SIGNATURE_DOMINANCE_FORBIDDEN")
    no_worse = True
    strictly_better = False
    for key in av:
        left = av[key]
        right = bv[key]
        if (
            left["layer"], left["direction"], left["scale_id"], left["transform_semantics_version"]
        ) != (
            right["layer"], right["direction"], right["scale_id"], right["transform_semantics_version"]
        ):
            raise ValueError("R2_CROSS_SIGNATURE_DOMINANCE_FORBIDDEN")
        if left["direction"] == "MAXIMIZE":
            no_worse = no_worse and left["value"] >= right["value"]
            strictly_better = strictly_better or left["value"] > right["value"]
        else:
            no_worse = no_worse and left["value"] <= right["value"]
            strictly_better = strictly_better or left["value"] < right["value"]
    return no_worse and strictly_better


def compare_r2_profiles(
    profiles: list[Mapping[str, Any]],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pareto compare only exact-signature groups; never rank across signatures."""
    contract = dict(contract or load_contract())
    errors = validate_contract(contract)
    if errors:
        raise ValueError("INVALID_R2_CONTRACT:" + ";".join(errors))

    groups: dict[str, list[dict[str, Any]]] = {}
    profile_rows: list[dict[str, Any]] = []
    for raw in profiles:
        profile = deepcopy(dict(raw))
        profile_rows.append(profile)
        if not profile.get("comparison_contract_evaluable"):
            continue
        groups.setdefault(profile["comparison_signature_sha256"], []).append(profile)

    result_groups = []
    comparable_profile_count = 0
    min_group = int(contract["dimension_architecture"]["comparison_group_min_profiles"])
    for signature_sha, group in sorted(groups.items()):
        ids = [str(row["security_id"]) for row in group]
        if len(group) < min_group:
            result_groups.append({
                "comparison_signature_sha256": signature_sha,
                "status": "INSUFFICIENT_GROUP_SIZE",
                "security_ids": sorted(ids),
                "pareto_frontier": [],
            })
            continue
        dominated_by = {str(row["security_id"]): [] for row in group}
        for row in group:
            sid = str(row["security_id"])
            for other in group:
                other_id = str(other["security_id"])
                if sid != other_id and _dominates(other, row):
                    dominated_by[sid].append(other_id)
        frontier = sorted(sid for sid, dominators in dominated_by.items() if not dominators)
        comparable_profile_count += len(group)
        result_groups.append({
            "comparison_signature_sha256": signature_sha,
            "status": "COMPARABLE_EXACT_SIGNATURE",
            "security_ids": sorted(ids),
            "pareto_frontier": frontier,
            "dominated_by": {sid: sorted(values) for sid, values in dominated_by.items()},
        })

    return {
        "schema_version": "1.0.0",
        "phase": "3B-R2",
        "model_form": contract["model"]["model_form"],
        "mode": "SYNTHETIC_CONTRACT_MECHANICS_ONLY",
        "profile_count": len(profile_rows),
        "profile_evaluable_count": sum(bool(row.get("profile_evaluable")) for row in profile_rows),
        "comparison_contract_evaluable_count": sum(bool(row.get("comparison_contract_evaluable")) for row in profile_rows),
        "comparable_profile_count": comparable_profile_count,
        "groups": result_groups,
        "cross_signature_comparison_count": 0,
        "ranking_generated": False,
        "winner_selected": False,
        "historical_replay_generated": False,
        "historical_performance_claimed": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
