"""Deterministic Phase 3D realized-outcome analysis under the frozen contract."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from statistics import mean, median
from typing import Any, Mapping

from strategy_kernel_v2.phase3d_measurement import build_measurability_scaffold, CANDIDATE_SENTINEL

HORIZONS = (1, 3, 5)
CALIBRATION_SENTINEL = "NOT_MEASURABLE_NO_HORIZON_COMPATIBLE_NUMERICAL_FORECAST"
COUNTERFACTUAL_SENTINEL = "NOT_MEASURABLE_NO_CONTEMPORANEOUS_COUNTERFACTUAL"


def _r(outcome: float, entry: float) -> float:
    return round(float(outcome) / float(entry) - 1.0, 8)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(mean(values), 8),
        "median": round(median(values), 8),
        "min": round(min(values), 8),
        "max": round(max(values), 8),
    }


def build_phase3d_outcomes(phase3c_replay: Mapping[str, Any], source_manifest: Mapping[str, Any]) -> dict[str, Any]:
    scaffold = build_measurability_scaffold(phase3c_replay)
    schedule = source_manifest["contract_derived_schedule"]
    price_series = source_manifest["price_series"]
    legacy_results = []
    by_status_horizon: dict[tuple[str, int], list[float]] = defaultdict(list)
    retained_horizon: dict[int, list[float]] = defaultdict(list)

    for row in scaffold["legacy_instances"]:
        cp = row["decision_point_id"]
        sid = row["security_id"]
        if cp not in schedule or sid not in price_series:
            raise AssertionError(f"PHASE3D_OUTCOME_SOURCE_MISSING:{cp}:{sid}")
        dates = schedule[cp]
        prices = price_series[sid]["observations"]
        required = [dates["entry"], dates["h1"], dates["h3"], dates["h5"]]
        missing = [d for d in required if d not in prices]
        if missing:
            raise AssertionError(f"PHASE3D_PRICE_DATE_MISSING:{sid}:{','.join(missing)}")
        entry = float(prices[dates["entry"]])
        returns = {}
        observations = {}
        for h in HORIZONS:
            d = dates[f"h{h}"]
            px = float(prices[d])
            rr = _r(px, entry)
            returns[str(h)] = rr
            observations[str(h)] = {"date": d, "close": px, "price_return": rr}
            by_status_horizon[(row["legacy_status"], h)].append(rr)
            if row["legacy_status"] == "RETAINED":
                retained_horizon[h].append(rr)
        result = deepcopy(row)
        result.update({
            "entry_observation": {"date": dates["entry"], "close": entry},
            "horizon_observations": observations,
            "calibration_status": CALIBRATION_SENTINEL,
            "regret_status": COUNTERFACTUAL_SENTINEL,
            "total_return_status": "NOT_MEASURABLE_CORPORATE_ACTION_DATA_NOT_LOADED",
        })
        legacy_results.append(result)

    candidate_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in scaffold["candidate_not_measurable_records"]:
        candidate_groups[(row["decision_point_id"], row["model_form"])].append(row["security_id"])
    candidate_records = [
        {
            "decision_point_id": cp,
            "model_form": model,
            "security_ids": sorted(ids),
            "security_count": len(ids),
            "calibration": CANDIDATE_SENTINEL,
            "regret": CANDIDATE_SENTINEL,
            "return_attribution": CANDIDATE_SENTINEL,
        }
        for (cp, model), ids in sorted(candidate_groups.items())
    ]

    status_summary = {}
    for status in sorted({r["legacy_status"] for r in legacy_results}):
        status_summary[status] = {str(h): _summary(by_status_horizon[(status, h)]) for h in HORIZONS}

    return {
        "schema_version": "1.0.0",
        "phase": "3D",
        "mode": "NEGATIVE_RESULT_MEASURABILITY_AND_REGRET_OBSERVABILITY",
        "realized_outcomes_loaded": True,
        "legacy_instance_count": len(legacy_results),
        "candidate_security_model_checkpoint_count": scaffold["candidate_record_count"],
        "candidate_group_record_count": len(candidate_records),
        "legacy_instance_results": legacy_results,
        "candidate_not_measurable_records": candidate_records,
        "descriptive_status_horizon_summary": status_summary,
        "retained_only_forward_price_summary": {str(h): _summary(retained_horizon[h]) for h in HORIZONS},
        "interpretation_controls": {
            "opportunity_observation_is_not_regret": True,
            "prioritized_research_is_not_executed_capital": True,
            "simulation_reduction_is_not_reconstructed_executed_counterfactual": True,
            "candidate_performance_comparison_available": False,
            "cross_model_winner_selected": False,
            "statistical_significance_claimed": False,
            "duplicate_checkpoint_dependence_disclosed": True,
        },
        "orders": 0,
        "trade_authority": "NONE",
    }
