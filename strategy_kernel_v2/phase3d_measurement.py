"""Phase 3D negative-result measurability scaffold.

Builds the instance universe mechanically from the accepted Phase 3C replay. This
module does not load realized outcomes; it freezes which Legacy security/checkpoint
instances are eligible for outcome observation and emits fail-closed candidate rows.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

CANDIDATE_SENTINEL = "NOT_MEASURABLE_NO_CONTEMPORANEOUS_OUTPUTS"


def _legacy_outcome_class(status: str) -> str:
    if status == "RETAINED":
        return "MEASURABLE_FORWARD_PRICE_RETURN_IF_PRICES_AVAILABLE"
    if status == "REDUCED":
        return "POSTURE_OUTCOME_OBSERVATION_ONLY_NO_EXECUTED_COUNTERFACTUAL"
    if status in {"NO_ACTION", "PRIORITIZED"}:
        return "OPPORTUNITY_OBSERVATION_ONLY"
    return "OBSERVATION_ONLY_UNCLASSIFIED_CAPITAL_AUTHORITY"


def build_measurability_scaffold(phase3c_replay: Mapping[str, Any]) -> dict[str, Any]:
    legacy_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for cp in phase3c_replay["checkpoint_results"]:
        by_model = {m["model_form"]: m for m in cp["model_summaries"]}
        legacy = by_model["LEGACY_POLICY_BASELINE"]
        for row in legacy["outcomes"]:
            if row["status"] == "BLOCKED":
                continue
            legacy_rows.append({
                "decision_point_id": cp["decision_point_id"],
                "checkpoint_at": cp["at"],
                "security_id": row["security_id"],
                "legacy_status": row["status"],
                "legacy_disposition": row.get("legacy_disposition"),
                "provenance_evidence_ids": list(row.get("provenance_evidence_ids", [])),
                "outcome_class": _legacy_outcome_class(row["status"]),
                "regret_status": "NOT_MEASURABLE_NO_CONTEMPORANEOUS_COUNTERFACTUAL",
            })

        for model_form in ("PHASE2_PROBABILISTIC_VECTOR", "SIMPLE_NON_PROBABILISTIC_PARETO"):
            model = by_model[model_form]
            for row in model["outcomes"]:
                candidate_rows.append({
                    "decision_point_id": cp["decision_point_id"],
                    "checkpoint_at": cp["at"],
                    "security_id": row["security_id"],
                    "model_form": model_form,
                    "historical_replay_status": row["status"],
                    "calibration": CANDIDATE_SENTINEL,
                    "regret": CANDIDATE_SENTINEL,
                    "return_attribution": CANDIDATE_SENTINEL,
                })

    legacy_rows.sort(key=lambda r: (r["decision_point_id"], r["security_id"]))
    candidate_rows.sort(key=lambda r: (r["decision_point_id"], r["model_form"], r["security_id"]))
    return {
        "schema_version": "1.0.0",
        "phase": "3D",
        "mode": "NEGATIVE_RESULT_MEASURABILITY_SCAFFOLD",
        "legacy_evaluable_instance_count": len(legacy_rows),
        "candidate_record_count": len(candidate_rows),
        "legacy_instances": deepcopy(legacy_rows),
        "candidate_not_measurable_records": deepcopy(candidate_rows),
        "realized_outcomes_loaded": False,
        "winner_selected": False,
        "orders": 0,
        "trade_authority": "NONE",
    }
