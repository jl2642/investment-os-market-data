"""Strategy Kernel v2 Phase 3C bounded historical decision/capital replay.

Consumes Phase 3A point-in-time snapshots and Phase 3B fixed model forms. No model
may read historical sources directly; all source access happens once in the model-neutral
Phase 3C-1 extractor, then every model receives the same shared observation packet.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from strategy_kernel_v2.competing_model_forms import (
    build_shared_observation_packet,
    run_competing_model_suite,
)
from strategy_kernel_v2.historical_feature_extractor import (
    adapt_features_to_shared_observations,
    extract_model_neutral_features,
    git_show_registered_source,
)
from strategy_kernel_v2.point_in_time_ledger import build_point_in_time_ledger

FALSE_CONTROLS = {
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

MODEL_FORMS = (
    "LEGACY_POLICY_BASELINE",
    "PHASE2_PROBABILISTIC_VECTOR",
    "SIMPLE_NON_PROBABILISTIC_PARETO",
)


class CachingRegisteredSourceLoader:
    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = repo_root
        self._cache: dict[tuple[str, str], Any] = {}
        self.read_count = 0

    def __call__(self, record: Mapping[str, Any]) -> Any:
        source = record["source"]
        key = (source["commit_sha"], source["path"])
        if key not in self._cache:
            self._cache[key] = git_show_registered_source(record, repo_root=self.repo_root)
            self.read_count += 1
        return deepcopy(self._cache[key])


def _normalize_legacy_disposition(disposition: str) -> str | None:
    text = disposition.upper()
    if any(token in text for token in ("REDUCE", "TRIM", "EXIT")):
        return "REDUCED"
    if any(token in text for token in ("HOLD", "RETAIN")):
        return "RETAINED"
    if any(token in text for token in ("WATCH", "NO_TRADE", "NO_DECISION", "NO_ACTION")):
        return "NO_ACTION"
    if any(token in text for token in ("PRIORITY", "PREPARE", "REVIEW_PRIORITY")):
        return "PRIORITIZED"
    buy_or_add = any(token in text for token in ("BUY", "ADD", "ADMIT"))
    explicit_no = any(token in text for token in ("NO_BUY", "NO_ADD"))
    if buy_or_add and not explicit_no:
        return "ADMITTED"
    return None


def normalize_model_outcomes(model_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    model_form = model_output["model_form"]
    outcomes: list[dict[str, Any]] = []

    if model_form == "LEGACY_POLICY_BASELINE":
        for row in model_output["rows"]:
            if row["status"] != "EVALUABLE":
                outcomes.append(
                    {
                        "security_id": row["security_id"],
                        "status": "BLOCKED",
                        "reason_codes": list(row.get("reason_codes", [])),
                    }
                )
                continue
            disposition = row["legacy_disposition"]
            normalized = _normalize_legacy_disposition(disposition)
            outcomes.append(
                {
                    "security_id": row["security_id"],
                    "status": normalized or "OBSERVED_UNMAPPED",
                    "legacy_disposition": disposition,
                    "reason_codes": list(row.get("reason_codes", [])),
                    "provenance_evidence_ids": list(row.get("provenance_evidence_ids", [])),
                }
            )
        return outcomes

    rows = model_output.get("rows", {})
    for security_id, row in rows.items():
        outcomes.append(
            {
                "security_id": security_id,
                "status": "PRIORITIZED" if row.get("pareto_status") == "FRONTIER" else "ADMITTED",
                "pareto_status": row.get("pareto_status"),
                "dominated_by": list(row.get("dominated_by", [])),
            }
        )
    for row in model_output.get("blocked", []):
        outcomes.append(
            {
                "security_id": row["security_id"],
                "status": "BLOCKED",
                "reason_codes": list(row.get("reason_codes", [])),
            }
        )
    return sorted(outcomes, key=lambda row: row["security_id"])


def _summarize_model_checkpoint(model_output: Mapping[str, Any]) -> dict[str, Any]:
    outcomes = normalize_model_outcomes(model_output)
    counts: dict[str, int] = {}
    for row in outcomes:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "model_form": model_output["model_form"],
        "evaluable_count": int(model_output.get("evaluable_count", 0)),
        "outcome_counts": dict(sorted(counts.items())),
        "outcomes": outcomes,
    }


def build_phase3c_replay(
    registry: Mapping[str, Any] | list[Mapping[str, Any]],
    decision_points: Mapping[str, Any] | list[Mapping[str, Any]],
    *,
    source_loader: Callable[[Mapping[str, Any]], Any],
) -> dict[str, Any]:
    evidence_records = registry["records"] if isinstance(registry, Mapping) else registry
    points = (
        decision_points["decision_points"]
        if isinstance(decision_points, Mapping)
        else decision_points
    )
    ledger = build_point_in_time_ledger(evidence_records, points)
    checkpoint_results = []
    aggregate = {
        model_form: {
            "checkpoint_count": 0,
            "evaluable_security_instances": 0,
            "outcome_counts": {},
        }
        for model_form in MODEL_FORMS
    }

    for snapshot in ledger["snapshots"]:
        feature_layer = extract_model_neutral_features(snapshot, source_loader=source_loader)
        observations = adapt_features_to_shared_observations(feature_layer)
        packet = build_shared_observation_packet(
            snapshot,
            structured_observations=observations,
            reference_asset=None,
        )
        suite = run_competing_model_suite(packet)
        if suite["model_specific_evidence_fetches"] != 0:
            raise AssertionError("MODEL_SPECIFIC_EVIDENCE_FETCH_DETECTED")

        summaries = []
        for model_output in suite["models"]:
            summary = _summarize_model_checkpoint(model_output)
            summaries.append(summary)
            state = aggregate[model_output["model_form"]]
            state["checkpoint_count"] += 1
            state["evaluable_security_instances"] += summary["evaluable_count"]
            for key, count in summary["outcome_counts"].items():
                state["outcome_counts"][key] = state["outcome_counts"].get(key, 0) + count

        checkpoint_results.append(
            {
                "decision_point_id": snapshot["decision_point_id"],
                "at": snapshot["at"],
                "input_packet_sha256": packet["input_packet_sha256"],
                "opportunity_security_ids": list(packet["opportunity_security_ids"]),
                "selected_evidence_ids": list(packet["selected_evidence_ids"]),
                "feature_row_count": len(feature_layer["feature_rows"]),
                "unsupported_selected_evidence_ids": list(feature_layer["unsupported_selected_evidence_ids"]),
                "subjective_feature_fill_count": feature_layer["subjective_feature_fill_count"],
                "retrospective_probability_backfill_count": feature_layer[
                    "retrospective_probability_backfill_count"
                ],
                "retrospective_scenario_backfill_count": feature_layer[
                    "retrospective_scenario_backfill_count"
                ],
                "model_summaries": summaries,
            }
        )

    for state in aggregate.values():
        state["outcome_counts"] = dict(sorted(state["outcome_counts"].items()))

    total_evaluable = sum(
        state["evaluable_security_instances"] for state in aggregate.values()
    )
    candidate_evaluable = (
        aggregate["PHASE2_PROBABILISTIC_VECTOR"]["evaluable_security_instances"]
        + aggregate["SIMPLE_NON_PROBABILISTIC_PARETO"]["evaluable_security_instances"]
    )

    return {
        "schema_version": "1.0.0",
        "phase": "3C",
        "mode": "BOUNDED_POINT_IN_TIME_DECISION_CAPITAL_REPLAY",
        "checkpoint_count": len(checkpoint_results),
        "feature_extraction_mode": "EXACT_REGISTERED_COMMIT_PATH_GIT_SHOW",
        "model_specific_evidence_fetches": 0,
        "subjective_feature_fill_count": sum(
            row["subjective_feature_fill_count"] for row in checkpoint_results
        ),
        "retrospective_probability_backfill_count": sum(
            row["retrospective_probability_backfill_count"] for row in checkpoint_results
        ),
        "retrospective_scenario_backfill_count": sum(
            row["retrospective_scenario_backfill_count"] for row in checkpoint_results
        ),
        "aggregate_by_model": aggregate,
        "total_evaluable_security_instances": total_evaluable,
        "candidate_model_evaluable_security_instances": candidate_evaluable,
        "comparative_candidate_replay_available": candidate_evaluable > 0,
        "checkpoint_results": checkpoint_results,
        "historical_performance_metrics_generated": False,
        "regret_analysis_generated": False,
        "calibration_generated": False,
        "user_decision_generated": False,
        "investment_recommendation_generated": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }


def load_default_phase3c_inputs(root: str | Path = ".") -> tuple[dict[str, Any], dict[str, Any]]:
    root_path = Path(root)
    with (root_path / "strategy_kernel_v2/PHASE3A_EVIDENCE_REGISTRY.json").open(
        "r", encoding="utf-8"
    ) as handle:
        registry = json.load(handle)
    with (root_path / "strategy_kernel_v2/PHASE3A_DECISION_POINTS.json").open(
        "r", encoding="utf-8"
    ) as handle:
        points = json.load(handle)
    return registry, points
