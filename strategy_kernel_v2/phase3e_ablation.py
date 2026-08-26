"""Phase 3E structural input-burden ablation.

This module intentionally does NOT read Phase 3D realized outcomes. It asks a narrower
question: on the same point-in-time Phase 3A/3C corpus, does removing exactly one model
input restore historical replayability? Adjacent observables are inventoried but never
substituted into fixed model-contract fields.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.historical_feature_extractor import extract_model_neutral_features
from strategy_kernel_v2.historical_replay import CachingRegisteredSourceLoader
from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger

FALSE_CONTROLS = {
    "phase3d_outcomes_read": False,
    "phase3d_returns_used_for_ablation_selection": False,
    "proxy_substitution_allowed": False,
    "subjective_mapping_allowed": False,
    "retrospective_probability_creation_allowed": False,
    "retrospective_confidence_creation_allowed": False,
    "retrospective_cost_score_creation_allowed": False,
    "revised_model_execution_allowed": False,
    "winner_selection_allowed": False,
    "same_seed_performance_claim_allowed": False,
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _variant_coverage(
    instances: list[dict[str, Any]],
    variants: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    baseline_count = None
    out: list[dict[str, Any]] = []
    for variant in variants:
        required = set(variant["required_feature_keys"])
        evaluable = [
            row for row in instances
            if required <= set(row["features"])
        ]
        checkpoint_ids = sorted({row["decision_point_id"] for row in evaluable})
        record = {
            "variant_id": variant["variant_id"],
            "removed_component": variant.get("removed_component"),
            "required_feature_keys": list(variant["required_feature_keys"]),
            "evaluable_security_instance_count": len(evaluable),
            "checkpoint_count_with_any_evaluable": len(checkpoint_ids),
            "evaluable_checkpoint_ids": checkpoint_ids,
        }
        if baseline_count is None:
            baseline_count = len(evaluable)
        record["delta_vs_fixed_baseline"] = len(evaluable) - baseline_count
        out.append(record)
    return out


def _feature_presence(instances: list[dict[str, Any]], keys: set[str]) -> dict[str, int]:
    return {
        key: sum(1 for row in instances if key in row["features"])
        for key in sorted(keys)
    }


def _adjacent_inventory(
    instances: list[dict[str, Any]],
    groups: Mapping[str, list[str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group, keys in groups.items():
        rows = [row for row in instances if any(key in row["features"] for key in keys)]
        present_keys = sorted({key for row in rows for key in keys if key in row["features"]})
        result[group] = {
            "security_instance_count_with_adjacent_observable": len(rows),
            "present_feature_keys": present_keys,
            "contract_substitution_allowed": False,
        }
    return result


def build_phase3e_ablation(
    registry: Mapping[str, Any],
    decision_points: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    source_loader,
) -> dict[str, Any]:
    ledger = build_point_in_time_ledger(registry["records"], decision_points["decision_points"])
    instances: list[dict[str, Any]] = []
    for snapshot in ledger["snapshots"]:
        layer = extract_model_neutral_features(snapshot, source_loader=source_loader)
        for security_id, row in layer["feature_rows"].items():
            instances.append({
                "decision_point_id": snapshot["decision_point_id"],
                "at": snapshot["at"],
                "security_id": security_id,
                "features": deepcopy(row.get("features", {})),
                "provenance_evidence_ids": list(row.get("provenance_evidence_ids", [])),
            })

    p2 = _variant_coverage(instances, contract["phase2_variants"])
    simple = _variant_coverage(instances, contract["simple_variants"])

    required_keys = {
        key
        for variant in contract["phase2_variants"] + contract["simple_variants"]
        for key in variant["required_feature_keys"]
    }
    presence = _feature_presence(instances, required_keys)
    adjacent = _adjacent_inventory(instances, contract["adjacent_observable_inventory"])

    p2_unlocks = sum(1 for row in p2[1:] if row["evaluable_security_instance_count"] > p2[0]["evaluable_security_instance_count"])
    simple_unlocks = sum(1 for row in simple[1:] if row["evaluable_security_instance_count"] > simple[0]["evaluable_security_instance_count"])
    total_unlocks = p2_unlocks + simple_unlocks

    if (
        p2[0]["evaluable_security_instance_count"] == 0
        and simple[0]["evaluable_security_instance_count"] == 0
        and total_unlocks == 0
    ):
        finding = "NO_SINGLE_COMPONENT_ABLATION_RESTORES_HISTORICAL_REPLAY"
    else:
        finding = "SINGLE_COMPONENT_ABLATION_CHANGES_HISTORICAL_COVERAGE"

    return {
        "schema_version": "1.0.0",
        "phase": "3E",
        "mode": contract["mode"],
        "finding": finding,
        "checkpoint_count": len(ledger["snapshots"]),
        "feature_security_instance_count": len(instances),
        "historical_source_reads": getattr(source_loader, "read_count", None),
        "phase2_ablation": p2,
        "simple_ablation": simple,
        "single_component_ablation_unlock_count": total_unlocks,
        "exact_contract_feature_presence": presence,
        "adjacent_observable_inventory": adjacent,
        "interpretation": {
            "fixed_models_overwritten": False,
            "candidate_model_execution_generated": False,
            "historical_candidate_performance_generated": False,
            "proxy_fields_count_as_contract_inputs": False,
            "material_revision_requires_loopback": True,
            "loopback_target": "PHASE_3B_CONTRACT_DEFINITION_THEN_PHASE_3C_REPLAY",
        },
        "controls": deepcopy(FALSE_CONTROLS),
    }


def build_default(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    registry = _load_json(root / "strategy_kernel_v2/PHASE3A_EVIDENCE_REGISTRY.json")
    points = _load_json(root / "strategy_kernel_v2/PHASE3A_DECISION_POINTS.json")
    contract = _load_json(root / "strategy_kernel_v2/PHASE3E_ABLATION_CONTRACT.json")
    loader = CachingRegisteredSourceLoader(root)
    return build_phase3e_ablation(registry, points, contract, source_loader=loader)


if __name__ == "__main__":
    result = build_default(".")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
