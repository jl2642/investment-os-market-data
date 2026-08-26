"""Strategy Kernel v2 Phase 3C historical decision/capital replay harness.

Shadow/research-only. Phase 3C first extracts model-neutral features from exact
Phase 3A registered historical sources, then executes the three fixed Phase 3B
model forms on one shared packet. It measures replay coverage and recorded shadow
states only; outcome/regret/performance evaluation belongs to Phase 3D.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from strategy_kernel_v2.competing_model_forms import (
    MODEL_ORDER,
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
    "hindsight_allowed": False,
    "model_specific_evidence_fetch_allowed": False,
    "retrospective_probability_backfill_allowed": False,
    "retrospective_scenario_backfill_allowed": False,
    "subjective_feature_fill_allowed": False,
    "model_winner_selection_allowed": False,
    "performance_or_regret_conclusion_allowed": False,
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


def _evaluable_count(model_output: Mapping[str, Any]) -> int:
    return int(model_output.get("evaluable_count", 0))


def _legacy_states(model_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = model_output.get("rows", [])
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("status") != "EVALUABLE":
            continue
        result.append(
            {
                "security_id": row["security_id"],
                "recorded_disposition": row.get("legacy_disposition"),
                "reason_codes": list(row.get("reason_codes", [])),
                "provenance_evidence_ids": list(row.get("provenance_evidence_ids", [])),
            }
        )
    return result


def _pareto_states(model_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = model_output.get("rows", {})
    if not isinstance(rows, Mapping):
        return []
    result = []
    for sid, row in rows.items():
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "security_id": sid,
                "pareto_status": row.get("pareto_status"),
                "dominated_by": list(row.get("dominated_by", [])),
            }
        )
    return result


def _blocked_states(model_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocked = model_output.get("blocked")
    if isinstance(blocked, list):
        return [deepcopy(dict(row)) for row in blocked if isinstance(row, Mapping)]
    rows = model_output.get("rows")
    if isinstance(rows, list):
        return [
            deepcopy(dict(row))
            for row in rows
            if isinstance(row, Mapping) and row.get("status") == "NOT_EVALUABLE"
        ]
    return []


def _summarize_model_output(model_output: Mapping[str, Any]) -> dict[str, Any]:
    model_form = str(model_output["model_form"])
    summary = {
        "model_form": model_form,
        "input_packet_sha256": model_output["input_packet_sha256"],
        "evaluable_count": _evaluable_count(model_output),
        "blocked": _blocked_states(model_output),
        "policy_score": model_output.get("policy_score"),
        "target_weights": model_output.get("target_weights"),
        "investment_recommendation_generated": bool(
            model_output.get("investment_recommendation_generated", False)
        ),
        "user_decision_generated": bool(model_output.get("user_decision_generated", False)),
    }
    if model_form == "LEGACY_POLICY_BASELINE":
        summary["recorded_legacy_states"] = _legacy_states(model_output)
    else:
        summary["pareto_states"] = _pareto_states(model_output)
        summary["pareto_frontier"] = list(model_output.get("pareto_frontier", []))
    return summary


def run_phase3c_replay(
    evidence_records,
    decision_points,
    *,
    source_loader: Callable[[Mapping[str, Any]], Any] = git_show_registered_source,
) -> dict[str, Any]:
    """Run bounded point-in-time replay using the fixed Phase 3B model forms."""
    ledger = build_point_in_time_ledger(evidence_records, decision_points)
    checkpoint_results = []
    aggregate = {
        model: {
            "evaluable_security_observations": 0,
            "checkpoints_with_any_evaluable_security": 0,
            "blocked_security_observations": 0,
        }
        for model in MODEL_ORDER
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
        if suite["input_packet_sha256"] != packet["input_packet_sha256"]:
            raise AssertionError("PHASE3C_SHARED_PACKET_IDENTITY_BROKEN")

        model_summaries = []
        for output in suite["model_outputs"]:
            summary = _summarize_model_output(output)
            model = summary["model_form"]
            evaluable = summary["evaluable_count"]
            blocked = len(summary["blocked"])
            aggregate[model]["evaluable_security_observations"] += evaluable
            aggregate[model]["blocked_security_observations"] += blocked
            if evaluable:
                aggregate[model]["checkpoints_with_any_evaluable_security"] += 1
            model_summaries.append(summary)

        checkpoint_results.append(
            {
                "decision_point_id": snapshot["decision_point_id"],
                "at": snapshot["at"],
                "opportunity_security_ids": list(snapshot["opportunity_security_ids"]),
                "selected_evidence_ids": list(snapshot["selected_evidence_ids"]),
                "feature_layer": feature_layer,
                "shared_packet_sha256": packet["input_packet_sha256"],
                "model_summaries": model_summaries,
            }
        )

    legacy_evaluable = aggregate["LEGACY_POLICY_BASELINE"]["evaluable_security_observations"]
    phase2_evaluable = aggregate["PHASE2_PROBABILISTIC_VECTOR"]["evaluable_security_observations"]
    simple_evaluable = aggregate["SIMPLE_NON_PROBABILISTIC_PARETO"]["evaluable_security_observations"]
    candidate_evaluable = phase2_evaluable + simple_evaluable

    if legacy_evaluable > 0 and candidate_evaluable == 0:
        status = "PARTIAL_REPLAY_MODEL_INPUT_COVERAGE_BLOCKED"
        phase3c_complete = False
        next_gate = "EXPAND_OR_GOVERN_MODEL_NEUTRAL_HISTORICAL_INPUT_COVERAGE_WITHOUT_BACKFILL"
    elif candidate_evaluable > 0:
        status = "BOUNDED_REPLAY_AVAILABLE_FOR_MULTI_MODEL_COMPARISON"
        phase3c_complete = True
        next_gate = "PHASE3D_CALIBRATION_AND_REGRET_ANALYSIS"
    else:
        status = "NO_HISTORICAL_REPLAY_EVALUABLE"
        phase3c_complete = False
        next_gate = "EXPAND_HISTORICAL_EXTRACTABLE_DECISION_INPUTS"

    return {
        "schema_version": "1.0.0",
        "phase": "3C",
        "mode": "POINT_IN_TIME_DECISION_CAPITAL_REPLAY",
        "status": status,
        "checkpoint_count": len(checkpoint_results),
        "model_forms": list(MODEL_ORDER),
        "aggregate_model_coverage": aggregate,
        "checkpoint_results": checkpoint_results,
        "historical_shadow_replay_generated": True,
        "historical_outcome_performance_evaluated": False,
        "regret_analysis_generated": False,
        "model_winner_selected": False,
        "phase3c_complete": phase3c_complete,
        "next_gate": next_gate,
        "investment_recommendation_generated": False,
        "user_decision_generated": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
