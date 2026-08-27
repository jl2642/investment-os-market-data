"""Phase 3D-R2 deterministic performance measurement.

Consumes only the frozen compact outcome-evidence pack accepted by PR #328.
No market data are fetched here. The output is descriptive performance evidence
for the 54 frozen checkpoint-local exact-signature dominance edges and fixed
1/3/5-session horizons.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from strategy_kernel_v2.phase3d_r2_measurability import build_measurability_audit
ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3D_R2_PERFORMANCE_MEASUREMENT_CONTRACT.json"
FROZEN_PACK_FILE = ROOT / "PHASE3D_R2_OUTCOME_EVIDENCE_FROZEN_COMPACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3D_R2_PERFORMANCE_MEASUREMENT.json"

getcontext().prec = 28
Q = Decimal("0.000000000001")

CONTROLS = {
    "model_mutations": 0,
    "transform_mutations": 0,
    "comparison_signature_mutations": 0,
    "holdout_population_mutations": 0,
    "dominance_relation_mutations": 0,
    "candidate_membership_mutations": 0,
    "real_account_mutations": 0,
    "simulation_mutations": 0,
    "target_portfolio_writebacks": 0,
    "user_decisions_generated": 0,
    "investment_recommendations_generated": 0,
    "external_outcome_fetch_count": 0,
    "orders": 0,
    "trade_authority": "NONE",
}


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


def load_contract(path: str | Path = CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_frozen_pack(path: str | Path = FROZEN_PACK_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def edge_population_sha256(audit: Mapping[str, Any]) -> str:
    rows = [
        {
            "checkpoint_id": row["checkpoint_id"],
            "checkpoint_at": row["checkpoint_at"],
            "comparison_signature_sha256": row["comparison_signature_sha256"],
            "dominator_security_id": row["dominator_security_id"],
            "dominated_security_id": row["dominated_security_id"],
        }
        for row in audit["frozen_edge_population"]
    ]
    return _sha256(rows)


def validate_frozen_pack(pack: Mapping[str, Any], audit: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if pack.get("pack_id") != "PHASE3D_R2_OUTCOME_EVIDENCE_FROZEN_COMPACT_V1":
        errors.append("R2_PERF_PACK_ID_DRIFT")
    if pack.get("status") != "PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE":
        errors.append("R2_PERF_PACK_STATUS_DRIFT")
    if pack.get("source_ledger_sha256") != "300db34b408e7ca2cfeb188b8c6177b62bdff70743a2cf6fb2c833bf3bda1d1b":
        errors.append("R2_PERF_PACK_LEDGER_SHA_DRIFT")
    if pack.get("parent_round1_audit_sha256") != audit.get("audit_sha256"):
        errors.append("R2_PERF_PACK_ROUND1_SHA_DRIFT")
    if pack.get("holdout_replay_sha256") != audit.get("parent_holdout_replay_sha256"):
        errors.append("R2_PERF_PACK_HOLDOUT_SHA_DRIFT")
    if pack.get("edge_population_sha256") != edge_population_sha256(audit):
        errors.append("R2_PERF_PACK_EDGE_SHA_DRIFT")
    if pack.get("frozen_dominance_edge_count") != 54:
        errors.append("R2_PERF_PACK_EDGE_COUNT_DRIFT")
    if pack.get("required_edge_endpoint_instances") != 55 or pack.get("complete_endpoint_count") != 55:
        errors.append("R2_PERF_PACK_ENDPOINT_COUNT_DRIFT")
    if pack.get("complete_evidence_edge_count") != 54:
        errors.append("R2_PERF_PACK_COMPLETE_EDGE_DRIFT")
    if pack.get("performance_calculation_authorized") is not True:
        errors.append("R2_PERF_PACK_PERFORMANCE_NOT_AUTHORIZED")
    if pack.get("return_calculation_count") != 0 or pack.get("performance_metric_count") != 0:
        errors.append("R2_PERF_PACK_PREMEASURED")
    if pack.get("corporate_action_status_counts") != {
        "NO_ADJUSTMENT_FACTOR_CHANGE_OBSERVED": 55,
        "ADJUSTMENT_FACTOR_CHANGE_OBSERVED": 0,
        "CORPORATE_ACTION_STATUS_UNRESOLVED": 0,
    }:
        errors.append("R2_PERF_PACK_CA_STATUS_DRIFT")
    if pack.get("support_reconciliation_disagreement_endpoint_count") != 0:
        errors.append("R2_PERF_PACK_RECONCILIATION_DISAGREEMENT")
    if pack.get("phase4_entry_allowed") is not False:
        errors.append("R2_PERF_PACK_PREMATURE_PHASE4")
    if pack.get("orders") != 0 or pack.get("trade_authority") != "NONE":
        errors.append("R2_PERF_PACK_AUTHORITY_DRIFT")
    return errors


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_FIRST_DETERMINISTIC_MEASUREMENT_RESULT":
        errors.append("R2_PERF_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_outcome_evidence", {})
    expected_parent = {
        "final_head": "59359979a5db17181b3fd93d6be8ef6fe5295877",
        "status": "PASS_R2_OUTCOME_EVIDENCE_READY_FOR_PERFORMANCE",
        "source_ledger_sha256": "300db34b408e7ca2cfeb188b8c6177b62bdff70743a2cf6fb2c833bf3bda1d1b",
        "frozen_pack_git_blob_sha": "175d83b52754a04fccefd6475fc2c1b82f130b01",
        "holdout_replay_sha256": "5b66a60eabe2c294d2a396b5fbae74ba19769376d01f5fec77a012461e1a4aaa",
        "round1_audit_sha256": "f1cc459b3d739afb12d55efa341783b69b8a8a647e209a020a6f8ee11662ad92",
        "edge_population_sha256": "caaf32a11adcac2febdefadc6bcbaace4d03647f1dd6b637fb2228f627fcf09f",
        "frozen_dominance_edge_count": 54,
        "required_edge_endpoint_instances": 55,
        "complete_evidence_edge_count": 54,
    }
    for key, value in expected_parent.items():
        if parent.get(key) != value:
            errors.append("R2_PERF_PARENT_DRIFT:" + key)

    pop = contract.get("measurement_population", {})
    if pop.get("fixed_horizon_sessions") != [1, 3, 5]:
        errors.append("R2_PERF_HORIZON_DRIFT")
    if pop.get("expected_endpoint_return_records") != 165:
        errors.append("R2_PERF_ENDPOINT_COUNT_CONTRACT_DRIFT")
    if pop.get("expected_edge_horizon_records") != 162:
        errors.append("R2_PERF_EDGE_COUNT_CONTRACT_DRIFT")
    for key in (
        "result_based_edge_dropping_allowed",
        "result_based_checkpoint_dropping_allowed",
        "result_based_signature_dropping_allowed",
        "security_scope_expansion_allowed",
        "outcome_refetch_allowed",
        "outcome_source_replacement_allowed",
    ):
        if pop.get(key) is not False:
            errors.append("R2_PERF_POPULATION_FIREWALL_OPEN:" + key)

    endpoint = contract.get("endpoint_return_definition", {})
    if endpoint.get("formula") != "horizon_close / entry_close - 1":
        errors.append("R2_PERF_RETURN_FORMULA_DRIFT")
    if endpoint.get("entry_and_horizon_closes_source") != "FROZEN_COMPACT_EVIDENCE_PACK_ONLY":
        errors.append("R2_PERF_EVIDENCE_SOURCE_DRIFT")
    if endpoint.get("total_return_claim_allowed") is not False:
        errors.append("R2_PERF_TOTAL_RETURN_CLAIM_OPEN")

    edge = contract.get("edge_measurement_definition", {})
    if edge.get("spread_formula") != "dominator_return - dominated_return":
        errors.append("R2_PERF_SPREAD_FORMULA_DRIFT")
    if edge.get("concordance_rule") != "dominator_return >= dominated_return":
        errors.append("R2_PERF_CONCORDANCE_DRIFT")
    if edge.get("tie_is_concordant") is not True:
        errors.append("R2_PERF_TIE_RULE_DRIFT")

    agg = contract.get("descriptive_aggregation", {})
    if agg.get("dependence_warning_required") is not True:
        errors.append("R2_PERF_DEPENDENCE_WARNING_NOT_REQUIRED")
    for key in ("statistical_significance_claim_allowed", "confidence_interval_allowed", "p_value_allowed"):
        if agg.get(key) is not False:
            errors.append("R2_PERF_INFERENCE_OPEN:" + key)

    boundary = contract.get("economic_interpretation_boundary", {})
    for key in (
        "measurement_result_may_select_global_winner",
        "measurement_result_may_create_scalar_model_score",
        "measurement_result_may_claim_portfolio_performance",
        "measurement_result_may_claim_sharpe_alpha_or_drawdown",
        "measurement_result_may_trigger_model_tuning",
        "measurement_result_may_mutate_dominance_relations",
        "phase3e_r2_support_threshold_defined_here",
        "phase3e_r2_start_may_be_authorized_from_this_measurement_alone",
    ):
        if boundary.get(key) is not False:
            errors.append("R2_PERF_INTERPRETATION_FIREWALL_OPEN:" + key)
    if boundary.get("support_gate_must_be_frozen_before_using_measurement_result_to_decide_phase3e_r2") is not True:
        errors.append("R2_PERF_SUPPORT_GATE_DISCIPLINE_MISSING")

    controls = contract.get("authority_boundaries", {})
    for key, value in controls.items():
        if key == "trade_authority":
            if value != "NONE":
                errors.append("R2_PERF_TRADE_AUTHORITY_DRIFT")
        elif value != 0:
            errors.append("R2_PERF_AUTHORITY_NONZERO:" + key)
    return errors


def endpoint_return(entry_close: Any, horizon_close: Any) -> Decimal:
    entry = _d(entry_close)
    horizon = _d(horizon_close)
    if entry <= 0 or horizon <= 0:
        raise ValueError("NONPOSITIVE_CLOSE")
    return horizon / entry - Decimal("1")


def edge_measurement(dominator_return: Decimal, dominated_return: Decimal) -> tuple[Decimal, bool]:
    spread = dominator_return - dominated_return
    return spread, dominator_return >= dominated_return


def _summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = list(rows)
    if not data:
        raise ValueError("EMPTY_SUMMARY_GROUP")
    spreads = [_d(row["edge_return_spread"]) for row in data]
    dom = [_d(row["dominator_return"]) for row in data]
    sub = [_d(row["dominated_return"]) for row in data]
    concordant = sum(bool(row["concordant"]) for row in data)
    n = len(data)
    return {
        "edge_count": n,
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


def build_performance_measurement() -> dict[str, Any]:
    contract = load_contract()
    contract_errors = validate_contract(contract)
    if contract_errors:
        raise ValueError("INVALID_R2_PERFORMANCE_CONTRACT:" + ";".join(contract_errors))

    audit = build_measurability_audit()
    pack = load_frozen_pack()
    pack_errors = validate_frozen_pack(pack, audit)
    integrity_errors: list[str] = list(pack_errors)

    parent = contract["parent_outcome_evidence"]
    if audit.get("audit_sha256") != parent["round1_audit_sha256"]:
        integrity_errors.append("R2_PERF_ROUND1_AUDIT_SHA_DRIFT")
    if audit.get("parent_holdout_replay_sha256") != parent["holdout_replay_sha256"]:
        integrity_errors.append("R2_PERF_HOLDOUT_SHA_DRIFT")
    if edge_population_sha256(audit) != parent["edge_population_sha256"]:
        integrity_errors.append("R2_PERF_EDGE_POPULATION_SHA_DRIFT")
    if pack.get("source_ledger_sha256") != parent["source_ledger_sha256"]:
        integrity_errors.append("R2_PERF_SOURCE_LEDGER_SHA_DRIFT")

    edges = [dict(row) for row in audit["frozen_edge_population"]]
    endpoint_pairs = sorted({
        (edge["checkpoint_id"], edge["dominator_security_id"]) for edge in edges
    } | {
        (edge["checkpoint_id"], edge["dominated_security_id"]) for edge in edges
    })
    if len(edges) != 54:
        integrity_errors.append("R2_PERF_EDGE_COUNT_DRIFT")
    if len(endpoint_pairs) != 55:
        integrity_errors.append("R2_PERF_ENDPOINT_PAIR_COUNT_DRIFT")

    horizons = [1, 3, 5]
    endpoint_rows: list[dict[str, Any]] = []
    endpoint_lookup: dict[tuple[str, str, int], Decimal] = {}
    for checkpoint_id, security_id in endpoint_pairs:
        schedule = pack["checkpoint_observation_dates"].get(checkpoint_id)
        evidence = pack["security_evidence"].get(security_id)
        if not schedule or not evidence:
            integrity_errors.append("R2_PERF_MISSING_ENDPOINT_INPUT:" + checkpoint_id + ":" + security_id)
            continue
        entry_date = schedule["entry_date"]
        closes = evidence["required_closes"]
        if entry_date not in closes:
            integrity_errors.append("R2_PERF_MISSING_ENTRY_CLOSE:" + checkpoint_id + ":" + security_id)
            continue
        for horizon in horizons:
            hdate = schedule[f"horizon_{horizon}_date"]
            if hdate not in closes:
                integrity_errors.append(
                    "R2_PERF_MISSING_HORIZON_CLOSE:" + checkpoint_id + ":" + security_id + ":" + str(horizon)
                )
                continue
            ret = endpoint_return(closes[entry_date], closes[hdate])
            endpoint_lookup[(checkpoint_id, security_id, horizon)] = ret
            endpoint_rows.append({
                "checkpoint_id": checkpoint_id,
                "checkpoint_at": schedule["checkpoint_at"],
                "security_id": security_id,
                "horizon_sessions": horizon,
                "entry_date": entry_date,
                "horizon_date": hdate,
                "entry_close": str(closes[entry_date]),
                "horizon_close": str(closes[hdate]),
                "forward_price_return": _fmt(ret),
                "price_semantics": "UNADJUSTED_LOCAL_CURRENCY_CLOSE",
                "currency": "CNY",
                "source_provider_id": evidence["selected_provider_id"],
                "source_series_sha256": evidence["selected_series_sha256"],
                "corporate_action_status": evidence["corporate_action_status"],
            })

    edge_rows: list[dict[str, Any]] = []
    for edge_index, edge in enumerate(edges, start=1):
        for horizon in horizons:
            dom_key = (edge["checkpoint_id"], edge["dominator_security_id"], horizon)
            sub_key = (edge["checkpoint_id"], edge["dominated_security_id"], horizon)
            if dom_key not in endpoint_lookup or sub_key not in endpoint_lookup:
                integrity_errors.append("R2_PERF_EDGE_ENDPOINT_RETURN_MISSING:" + str(edge_index) + ":" + str(horizon))
                continue
            dom_ret = endpoint_lookup[dom_key]
            sub_ret = endpoint_lookup[sub_key]
            spread, concordant = edge_measurement(dom_ret, sub_ret)
            edge_rows.append({
                "edge_id": f"R2D_EDGE_{edge_index:03d}",
                "checkpoint_id": edge["checkpoint_id"],
                "checkpoint_at": edge["checkpoint_at"],
                "comparison_signature_sha256": edge["comparison_signature_sha256"],
                "dominator_security_id": edge["dominator_security_id"],
                "dominated_security_id": edge["dominated_security_id"],
                "horizon_sessions": horizon,
                "dominator_return": _fmt(dom_ret),
                "dominated_return": _fmt(sub_ret),
                "edge_return_spread": _fmt(spread),
                "concordant": concordant,
            })

    expected_endpoint = contract["measurement_population"]["expected_endpoint_return_records"]
    expected_edges = contract["measurement_population"]["expected_edge_horizon_records"]
    if len(endpoint_rows) != expected_endpoint:
        integrity_errors.append(f"R2_PERF_ENDPOINT_RECORD_COUNT:{len(endpoint_rows)}")
    if len(edge_rows) != expected_edges:
        integrity_errors.append(f"R2_PERF_EDGE_RECORD_COUNT:{len(edge_rows)}")

    horizon_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    checkpoint_groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    signature_groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in edge_rows:
        h = int(row["horizon_sessions"])
        horizon_groups[h].append(row)
        checkpoint_groups[(row["checkpoint_id"], h)].append(row)
        signature_groups[(row["comparison_signature_sha256"], h)].append(row)

    horizon_summary = {
        str(h): _summary(horizon_groups[h]) for h in horizons if horizon_groups[h]
    }
    checkpoint_horizon_summary = [
        {
            "checkpoint_id": checkpoint_id,
            "horizon_sessions": horizon,
            **_summary(rows),
        }
        for (checkpoint_id, horizon), rows in sorted(checkpoint_groups.items())
    ]
    signature_horizon_summary = [
        {
            "comparison_signature_sha256": signature,
            "horizon_sessions": horizon,
            **_summary(rows),
        }
        for (signature, horizon), rows in sorted(signature_groups.items())
    ]
    pooled = _summary(edge_rows) if edge_rows else {}

    status = (
        contract["classification"]["fail_status"]
        if integrity_errors
        else contract["classification"]["complete_status"]
    )
    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3D_R2",
        "subphase": "PERFORMANCE_MEASUREMENT",
        "status": status,
        "model_form": audit["model_form"],
        "model_version": audit["model_version"],
        "source_outcome_evidence_ledger_sha256": pack["source_ledger_sha256"],
        "source_round1_audit_sha256": audit["audit_sha256"],
        "source_holdout_replay_sha256": audit["parent_holdout_replay_sha256"],
        "source_edge_population_sha256": edge_population_sha256(audit),
        "frozen_dominance_edge_count": len(edges),
        "checkpoint_security_endpoint_instance_count": len(endpoint_pairs),
        "distinct_edge_checkpoint_count": len({edge["checkpoint_id"] for edge in edges}),
        "distinct_edge_signature_count": len({edge["comparison_signature_sha256"] for edge in edges}),
        "fixed_horizon_sessions": horizons,
        "endpoint_return_record_count": len(endpoint_rows),
        "edge_horizon_record_count": len(edge_rows),
        "endpoint_return_calculation_count": len(endpoint_rows),
        "edge_spread_calculation_count": len(edge_rows),
        "concordance_calculation_count": len(edge_rows),
        "endpoint_returns": endpoint_rows,
        "edge_measurements": edge_rows,
        "horizon_summary": horizon_summary,
        "checkpoint_horizon_summary": checkpoint_horizon_summary,
        "signature_horizon_summary": signature_horizon_summary,
        "pooled_all_horizons_summary": pooled,
        "dependence_warning": contract["descriptive_aggregation"]["dependence_warning"],
        "statistical_significance_claimed": False,
        "confidence_interval_computed": False,
        "p_value_computed": False,
        "portfolio_pnl_computed": False,
        "sharpe_computed": False,
        "scalar_model_score_computed": False,
        "global_winner_selected": False,
        "phase3e_r2_support_threshold_defined": False,
        "phase3e_r2_support_decision_made": False,
        "phase3e_r2_start_authorized": False,
        "integrity_errors": sorted(set(integrity_errors)),
        "controls": dict(CONTROLS),
        "phase3d_r2_performance_measurement_executed": True,
        "phase3d_r2_state_closeout_applied": False,
        "phase3e_r2_started": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
    }
    result["measurement_sha256"] = _sha256({k: v for k, v in result.items() if k != "measurement_sha256"})
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_performance_measurement()
    path = write_default(result)
    h1 = result.get("horizon_summary", {}).get("1", {})
    h3 = result.get("horizon_summary", {}).get("3", {})
    h5 = result.get("horizon_summary", {}).get("5", {})
    print(
        "PHASE3D_R2_PERFORMANCE_MEASUREMENT "
        f"status={result['status']} endpoints={result['endpoint_return_record_count']}/165 "
        f"edge_horizons={result['edge_horizon_record_count']}/162 "
        f"h1_concordance={h1.get('concordance_rate')} "
        f"h3_concordance={h3.get('concordance_rate')} "
        f"h5_concordance={h5.get('concordance_rate')} "
        "phase3e_support_decision=false phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['measurement_sha256']} path={path}"
    )
