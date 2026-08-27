"""Phase 3E-R2 predefined robustness execution.

Executes only the five axes frozen by the accepted structural support gate.
All calculations reuse the accepted Phase 3D-R2 frozen-pack measurement;
there is no market-data refetch, model tuning, edge recomputation, or subset search.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from strategy_kernel_v2.phase3d_r2_performance_measurement import build_performance_measurement

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3E_R2_ROBUSTNESS_EXECUTION_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3E_R2_ROBUSTNESS_RESULTS.json"

getcontext().prec = 28
Q = Decimal("0.000000000001")

CONTROLS = {
    "model_mutations": 0,
    "transform_mutations": 0,
    "comparison_signature_mutations": 0,
    "holdout_population_mutations": 0,
    "dominance_relation_mutations": 0,
    "outcome_refetches": 0,
    "outcome_value_mutations": 0,
    "result_driven_subset_selections": 0,
    "simultaneous_multi_axis_searches": 0,
    "candidate_membership_mutations": 0,
    "real_account_mutations": 0,
    "simulation_mutations": 0,
    "target_portfolio_writebacks": 0,
    "investment_recommendations_generated": 0,
    "orders": 0,
    "trade_authority": "NONE",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _fmt(value: Decimal) -> str:
    return format(value.quantize(Q, rounding=ROUND_HALF_EVEN), "f")


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")


def load_contract() -> dict[str, Any]:
    return _load(CONTRACT_FILE)


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BY_ACCEPTED_STRUCTURAL_SUPPORT_GATE_BEFORE_EXECUTION":
        errors.append("R2E_ROBUSTNESS_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_support_gate", {})
    expected = {
        "final_head": "47cf9df36f6a541a6f58ecd4487c67e91e26f1bf",
        "gate_status": "PASS_R2_STRUCTURAL_SUPPORT_FOR_ROBUSTNESS",
        "gate_sha256": "c6288bb86700af9de8089fd14e1be379bb1beef4d4eeb537cf1f2e471c37d404",
        "support_contract_git_blob_sha": "a06d48ddbb9b154aa04ad959525b3dbd4fa8a62f",
        "measurement_sha256": "a3e474745dc8074be363f3d9b8e7082923bd67adeff6c6e42431e1f6a406edad",
        "frozen_dominance_edge_count": 54,
        "edge_bearing_checkpoint_count": 13,
        "endpoint_security_count": 7,
        "exact_signature_count": 2,
        "fixed_horizon_sessions": [1, 3, 5],
    }
    for key, value in expected.items():
        if parent.get(key) != value:
            errors.append("R2E_ROBUSTNESS_PARENT_DRIFT:" + key)

    plan = contract.get("execution_plan", {})
    if plan.get("one_axis_at_a_time") is not True:
        errors.append("R2E_ROBUSTNESS_ONE_AXIS_FALSE")
    for key in ("new_test_axes_allowed", "simultaneous_multi_axis_search_allowed", "result_driven_subset_selection_allowed"):
        if plan.get(key) is not False:
            errors.append("R2E_ROBUSTNESS_PLAN_FIREWALL_OPEN:" + key)
    tests = {row["test_id"]: row for row in plan.get("required_tests", [])}
    expected_ids = {
        "R2E_HORIZON_STRATIFICATION",
        "R2E_CHECKPOINT_JACKKNIFE",
        "R2E_SECURITY_JACKKNIFE",
        "R2E_SIGNATURE_STRATIFICATION_AND_JACKKNIFE",
        "R2E_AGGREGATION_WEIGHTING_SENSITIVITY",
    }
    if set(tests) != expected_ids:
        errors.append("R2E_ROBUSTNESS_TEST_SET_DRIFT")
    if tests.get("R2E_CHECKPOINT_JACKKNIFE", {}).get("expected_perturbations") != 13:
        errors.append("R2E_ROBUSTNESS_CHECKPOINT_COUNT_DRIFT")
    if tests.get("R2E_SECURITY_JACKKNIFE", {}).get("expected_perturbations") != 7:
        errors.append("R2E_ROBUSTNESS_SECURITY_COUNT_DRIFT")
    if tests.get("R2E_SIGNATURE_STRATIFICATION_AND_JACKKNIFE", {}).get("expected_perturbations") != 2:
        errors.append("R2E_ROBUSTNESS_SIGNATURE_COUNT_DRIFT")

    reuse = contract.get("measurement_reuse", {})
    for key in (
        "outcome_refetch_allowed",
        "outcome_value_mutation_allowed",
        "dominance_relation_recomputation_allowed",
        "model_or_transform_mutation_allowed",
        "comparison_signature_mutation_allowed",
    ):
        if reuse.get(key) is not False:
            errors.append("R2E_ROBUSTNESS_REUSE_FIREWALL_OPEN:" + key)
    if reuse.get("baseline_edge_measurements_required") != 162:
        errors.append("R2E_ROBUSTNESS_BASELINE_MEASUREMENT_COUNT_DRIFT")

    outputs = contract.get("descriptive_outputs", {})
    for key in (
        "statistical_significance_claim_allowed",
        "confidence_interval_allowed",
        "p_value_allowed",
        "robustness_pass_fail_threshold_defined",
        "economic_winner_selection_allowed",
    ):
        if outputs.get(key) is not False:
            errors.append("R2E_ROBUSTNESS_INFERENCE_FIREWALL_OPEN:" + key)

    auth = contract.get("authority_boundaries", {})
    for key, value in auth.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2E_ROBUSTNESS_TRADE_AUTHORITY_DRIFT")
        elif value != 0:
            errors.append("R2E_ROBUSTNESS_AUTHORITY_NONZERO:" + key)
    return errors


def _edge_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = list(rows)
    if not data:
        raise ValueError("EMPTY_EDGE_SUMMARY")
    spreads = [_d(row["edge_return_spread"]) for row in data]
    dom = [_d(row["dominator_return"]) for row in data]
    sub = [_d(row["dominated_return"]) for row in data]
    concordant = sum(bool(row["concordant"]) for row in data)
    n = len(data)
    return {
        "edge_horizon_record_count": n,
        "distinct_edge_count": len({row["edge_id"] for row in data}),
        "concordant_count": concordant,
        "discordant_count": n - concordant,
        "concordance_rate": _fmt(Decimal(concordant) / Decimal(n)),
        "mean_edge_return_spread": _fmt(_mean(spreads)),
        "median_edge_return_spread": _fmt(_median(spreads)),
        "min_edge_return_spread": _fmt(min(spreads)),
        "max_edge_return_spread": _fmt(max(spreads)),
        "mean_dominator_return": _fmt(_mean(dom)),
        "mean_dominated_return": _fmt(_mean(sub)),
    }


def _by_horizon(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = list(rows)
    out: dict[str, Any] = {}
    for horizon in (1, 3, 5):
        selected = [row for row in data if int(row["horizon_sessions"]) == horizon]
        if not selected:
            raise ValueError("EMPTY_HORIZON:" + str(horizon))
        out[str(horizon)] = _edge_summary(selected)
    return out


def _cluster_weighted_summary(rows: list[Mapping[str, Any]], cluster_key: str) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[cluster_key])].append(row)
    if not groups:
        raise ValueError("EMPTY_CLUSTER_GROUP:" + cluster_key)

    cluster_rows: list[dict[str, Any]] = []
    for cluster, members in sorted(groups.items()):
        summary = _edge_summary(members)
        cluster_rows.append({
            "cluster": cluster,
            "edge_count": summary["distinct_edge_count"],
            "concordance_rate": summary["concordance_rate"],
            "mean_edge_return_spread": summary["mean_edge_return_spread"],
            "mean_dominator_return": summary["mean_dominator_return"],
            "mean_dominated_return": summary["mean_dominated_return"],
        })
    return {
        "cluster_count": len(cluster_rows),
        "edge_horizon_record_count": len(rows),
        "concordance_rate": _fmt(_mean([_d(row["concordance_rate"]) for row in cluster_rows])),
        "mean_edge_return_spread": _fmt(_mean([_d(row["mean_edge_return_spread"]) for row in cluster_rows])),
        "mean_dominator_return": _fmt(_mean([_d(row["mean_dominator_return"]) for row in cluster_rows])),
        "mean_dominated_return": _fmt(_mean([_d(row["mean_dominated_return"]) for row in cluster_rows])),
        "cluster_summaries": cluster_rows,
    }


def _axis_range(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("EMPTY_AXIS_RANGE")
    rates = [_d(row["summary"]["concordance_rate"]) for row in records]
    spreads = [_d(row["summary"]["mean_edge_return_spread"]) for row in records]
    return {
        "perturbation_count": len(records),
        "min_concordance_rate": _fmt(min(rates)),
        "max_concordance_rate": _fmt(max(rates)),
        "min_mean_edge_return_spread": _fmt(min(spreads)),
        "max_mean_edge_return_spread": _fmt(max(spreads)),
    }


def build_robustness_results() -> dict[str, Any]:
    contract = load_contract()
    contract_errors = validate_contract(contract)
    if contract_errors:
        raise ValueError("INVALID_R2E_ROBUSTNESS_CONTRACT:" + ";".join(contract_errors))

    state = _load(ROOT / "PROGRAM_STATE.json")
    current = _load(ROOT / "CURRENT_PHASE_STATUS.json")
    integrity_errors: list[str] = []

    if state.get("phase3e_r2_structural_support_gate_complete") is not True:
        integrity_errors.append("R2E_ROBUSTNESS_SUPPORT_GATE_NOT_COMPLETE")
    if state.get("phase3e_r2_structural_support_gate_status") != "PASS_R2_STRUCTURAL_SUPPORT_FOR_ROBUSTNESS":
        integrity_errors.append("R2E_ROBUSTNESS_SUPPORT_GATE_STATUS_DRIFT")
    if state.get("phase3e_r2_structural_support_gate_sha256") != contract["parent_support_gate"]["gate_sha256"]:
        integrity_errors.append("R2E_ROBUSTNESS_SUPPORT_GATE_SHA_DRIFT")
    if state.get("phase3e_r2_robustness_plan_frozen") is not True:
        integrity_errors.append("R2E_ROBUSTNESS_PLAN_NOT_FROZEN")
    if state.get("phase3e_r2_robustness_execution_start_allowed") is not True:
        integrity_errors.append("R2E_ROBUSTNESS_START_NOT_ALLOWED")
    closeout = state.get("phase3e_r2_complete") is True
    expected_started = closeout
    if state.get("phase3e_r2_started") is not expected_started or state.get("phase3e_r2_robustness_started") is not expected_started:
        integrity_errors.append("R2E_ROBUSTNESS_STATE_START_DRIFT")
    expected_current_phase = (
        "PHASE_3E_R2_ROBUSTNESS_EXECUTION"
        if closeout
        else current.get("current_phase")
    )
    if closeout and current.get("current_phase") != expected_current_phase:
        integrity_errors.append("R2E_ROBUSTNESS_CURRENT_PHASE_DRIFT")
    expected_next = (
        "REPEAT_PHASE_3F_HISTORICAL_PROMOTION_GATE"
        if closeout
        else "PHASE_3E_R2_ROBUSTNESS_EXECUTION"
    )
    if current.get("next_phase") != expected_next:
        integrity_errors.append("R2E_ROBUSTNESS_CURRENT_NEXT_DRIFT")

    performance = build_performance_measurement()
    if performance.get("status") != "COMPLETE_R2_DETERMINISTIC_PERFORMANCE_MEASUREMENT_DESCRIPTIVE_ONLY":
        integrity_errors.append("R2E_ROBUSTNESS_PARENT_MEASUREMENT_NOT_COMPLETE")
    if performance.get("measurement_sha256") != contract["parent_support_gate"]["measurement_sha256"]:
        integrity_errors.append("R2E_ROBUSTNESS_PARENT_MEASUREMENT_SHA_DRIFT")
    edge_rows = [dict(row) for row in performance.get("edge_measurements", [])]
    if len(edge_rows) != 162:
        integrity_errors.append("R2E_ROBUSTNESS_EDGE_HORIZON_COUNT_DRIFT")

    horizons = [1, 3, 5]
    checkpoints = sorted({row["checkpoint_id"] for row in edge_rows})
    securities = sorted({
        row["dominator_security_id"] for row in edge_rows
    } | {
        row["dominated_security_id"] for row in edge_rows
    })
    signatures = sorted({row["comparison_signature_sha256"] for row in edge_rows})
    if len(checkpoints) != 13:
        integrity_errors.append("R2E_ROBUSTNESS_CHECKPOINT_LEVEL_DRIFT")
    if len(securities) != 7:
        integrity_errors.append("R2E_ROBUSTNESS_SECURITY_LEVEL_DRIFT")
    if len(signatures) != 2:
        integrity_errors.append("R2E_ROBUSTNESS_SIGNATURE_LEVEL_DRIFT")

    horizon_stratification = _by_horizon(edge_rows)

    checkpoint_jackknife = []
    for checkpoint_id in checkpoints:
        retained = [row for row in edge_rows if row["checkpoint_id"] != checkpoint_id]
        summaries = _by_horizon(retained)
        checkpoint_jackknife.append({
            "omitted_checkpoint_id": checkpoint_id,
            "retained_distinct_edge_count": len({row["edge_id"] for row in retained}),
            "horizon_summary": summaries,
        })

    security_jackknife = []
    for security_id in securities:
        retained = [
            row for row in edge_rows
            if row["dominator_security_id"] != security_id
            and row["dominated_security_id"] != security_id
        ]
        if not retained:
            integrity_errors.append("R2E_ROBUSTNESS_SECURITY_JACKKNIFE_EMPTY:" + security_id)
            continue
        summaries = _by_horizon(retained)
        security_jackknife.append({
            "omitted_security_id": security_id,
            "retained_distinct_edge_count": len({row["edge_id"] for row in retained}),
            "horizon_summary": summaries,
        })

    signature_strata = []
    signature_jackknife = []
    for signature in signatures:
        stratum = [row for row in edge_rows if row["comparison_signature_sha256"] == signature]
        signature_strata.append({
            "comparison_signature_sha256": signature,
            "distinct_edge_count": len({row["edge_id"] for row in stratum}),
            "horizon_summary": _by_horizon(stratum),
        })
        retained = [row for row in edge_rows if row["comparison_signature_sha256"] != signature]
        if not retained:
            integrity_errors.append("R2E_ROBUSTNESS_SIGNATURE_JACKKNIFE_EMPTY:" + signature)
            continue
        signature_jackknife.append({
            "omitted_comparison_signature_sha256": signature,
            "retained_distinct_edge_count": len({row["edge_id"] for row in retained}),
            "horizon_summary": _by_horizon(retained),
        })

    weighting_sensitivity = []
    for horizon in horizons:
        rows = [row for row in edge_rows if int(row["horizon_sessions"]) == horizon]
        weighting_sensitivity.append({
            "horizon_sessions": horizon,
            "weighting_scheme": "EQUAL_EDGE",
            "summary": _edge_summary(rows),
        })
        weighting_sensitivity.append({
            "horizon_sessions": horizon,
            "weighting_scheme": "EQUAL_CHECKPOINT",
            "summary": _cluster_weighted_summary(rows, "checkpoint_id"),
        })
        weighting_sensitivity.append({
            "horizon_sessions": horizon,
            "weighting_scheme": "EQUAL_SIGNATURE",
            "summary": _cluster_weighted_summary(rows, "comparison_signature_sha256"),
        })

    checkpoint_axis_ranges = {}
    security_axis_ranges = {}
    signature_jackknife_axis_ranges = {}
    for horizon in horizons:
        h = str(horizon)
        checkpoint_axis_ranges[h] = _axis_range([
            {"summary": row["horizon_summary"][h]} for row in checkpoint_jackknife
        ])
        security_axis_ranges[h] = _axis_range([
            {"summary": row["horizon_summary"][h]} for row in security_jackknife
        ])
        signature_jackknife_axis_ranges[h] = _axis_range([
            {"summary": row["horizon_summary"][h]} for row in signature_jackknife
        ])

    if len(checkpoint_jackknife) != 13:
        integrity_errors.append("R2E_ROBUSTNESS_CHECKPOINT_JACKKNIFE_COUNT")
    if len(security_jackknife) != 7:
        integrity_errors.append("R2E_ROBUSTNESS_SECURITY_JACKKNIFE_COUNT")
    if len(signature_strata) != 2 or len(signature_jackknife) != 2:
        integrity_errors.append("R2E_ROBUSTNESS_SIGNATURE_TEST_COUNT")
    if len(weighting_sensitivity) != 9:
        integrity_errors.append("R2E_ROBUSTNESS_WEIGHTING_RECORD_COUNT")

    status = (
        contract["completion_rule"]["status"]
        if not integrity_errors
        else "FAIL_R2_PREDECLARED_ROBUSTNESS_EVALUATION_INTEGRITY"
    )
    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3E_R2",
        "subphase": "ROBUSTNESS_EXECUTION",
        "status": status,
        "source_phase3d_measurement_sha256": performance.get("measurement_sha256"),
        "source_support_gate_sha256": state.get("phase3e_r2_structural_support_gate_sha256"),
        "baseline_edge_horizon_record_count": len(edge_rows),
        "baseline_distinct_edge_count": len({row["edge_id"] for row in edge_rows}),
        "edge_bearing_checkpoint_count": len(checkpoints),
        "endpoint_security_count": len(securities),
        "exact_signature_count": len(signatures),
        "fixed_horizon_sessions": horizons,
        "horizon_stratification": horizon_stratification,
        "checkpoint_jackknife": checkpoint_jackknife,
        "checkpoint_jackknife_axis_ranges": checkpoint_axis_ranges,
        "security_jackknife": security_jackknife,
        "security_jackknife_axis_ranges": security_axis_ranges,
        "signature_strata": signature_strata,
        "signature_jackknife": signature_jackknife,
        "signature_jackknife_axis_ranges": signature_jackknife_axis_ranges,
        "aggregation_weighting_sensitivity": weighting_sensitivity,
        "completed_test_ids": [
            "R2E_HORIZON_STRATIFICATION",
            "R2E_CHECKPOINT_JACKKNIFE",
            "R2E_SECURITY_JACKKNIFE",
            "R2E_SIGNATURE_STRATIFICATION_AND_JACKKNIFE",
            "R2E_AGGREGATION_WEIGHTING_SENSITIVITY",
        ],
        "completed_test_count": 5,
        "checkpoint_jackknife_count": len(checkpoint_jackknife),
        "security_jackknife_count": len(security_jackknife),
        "signature_strata_count": len(signature_strata),
        "signature_jackknife_count": len(signature_jackknife),
        "aggregation_scheme_horizon_record_count": len(weighting_sensitivity),
        "robustness_pass_fail_threshold_defined": False,
        "positive_robustness_claimed": False,
        "economic_winner_selected": False,
        "statistical_significance_claimed": False,
        "confidence_interval_computed": False,
        "p_value_computed": False,
        "phase3e_r2_completion_is_evidence_completion_only": True,
        "repeat_phase3f_start_authorized_by_candidate": False,
        "phase4_promotion_claimed": False,
        "integrity_errors": sorted(set(integrity_errors)),
        "controls": dict(CONTROLS),
        "phase3e_r2_state_closeout_applied": False,
        "phase3e_r2_started": False,
        "phase3e_r2_complete": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    result["robustness_sha256"] = _sha256({k: v for k, v in result.items() if k != "robustness_sha256"})
    return result


def write_default(result: Mapping[str, Any]) -> Path:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUTPUT_FILE


if __name__ == "__main__":
    result = build_robustness_results()
    path = write_default(result)
    print(
        "PHASE3E_R2_ROBUSTNESS_RESULT "
        f"status={result['status']} tests={result['completed_test_count']}/5 "
        f"checkpoint_jackknife={result['checkpoint_jackknife_count']}/13 "
        f"security_jackknife={result['security_jackknife_count']}/7 "
        f"signature_jackknife={result['signature_jackknife_count']}/2 "
        f"weighting_records={result['aggregation_scheme_horizon_record_count']}/9 "
        "robustness_threshold=false positive_robustness_claim=false "
        "repeat_phase3f_started=false phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['robustness_sha256']} path={path}"
    )
