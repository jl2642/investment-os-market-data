"""Phase 3D-R2 Round 1: measurability and outcome-evidence readiness audit.

This round freezes economic outcome semantics before any R2 performance
calculation. It rebuilds the accepted independent Holdout replay, freezes the
entire dominance-edge population, and audits only pre-existing governed outcome
source coverage/semantics. It does not calculate returns or performance.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.phase3_r2_independent_holdout_replay import build_holdout_replay

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3D_R2_MEASURABILITY_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated/PHASE3D_R2_MEASURABILITY_AUDIT.json"

OUTCOME_MANIFEST = ROOT / "PHASE3D_OUTCOME_SOURCE_MANIFEST.json"
PRICE_LEDGER = ROOT.parent / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_PRICE_LEDGER.jsonl"
DAILY_MANIFEST = ROOT.parent / "outputs/current/DAILY_MARKET_SNAPSHOT_MANIFEST.json"

CONTROLS = {
    "return_calculation_count": 0,
    "performance_metric_count": 0,
    "portfolio_pnl_count": 0,
    "regret_metric_count": 0,
    "calibration_metric_count": 0,
    "model_mutation_count": 0,
    "holdout_population_mutation_count": 0,
    "dominance_relation_mutation_count": 0,
    "result_based_drop_count": 0,
    "external_outcome_fetch_count": 0,
    "orders": 0,
    "trade_authority": "NONE",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_contract(path: str | Path = CONTRACT_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_R2_OUTCOME_PERFORMANCE_CALCULATION":
        errors.append("R2_3D_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_holdout", {})
    if parent.get("final_head") != "4ac3d7d25ed65fd77747addbcbbd21ea47679332":
        errors.append("R2_3D_PARENT_HEAD_DRIFT")
    if parent.get("status") != "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL":
        errors.append("R2_3D_PARENT_NOT_PASS")
    if parent.get("replay_sha256") != "5b66a60eabe2c294d2a396b5fbae74ba19769376d01f5fec77a012461e1a4aaa":
        errors.append("R2_3D_PARENT_REPLAY_SHA_DRIFT")
    if parent.get("checkpoint_count") != 14 or parent.get("dominance_edge_count") != 54:
        errors.append("R2_3D_PARENT_COUNTS_DRIFT")

    model = contract.get("model_identity", {})
    if model.get("model_form") != "EVIDENCE_NATIVE_APPLICABILITY_AWARE_PARETO_R2":
        errors.append("R2_3D_MODEL_FORM_DRIFT")
    if model.get("model_version") != "R2.0.1_RESEARCH":
        errors.append("R2_3D_MODEL_VERSION_DRIFT")
    for key in (
        "model_contract_may_change_in_phase3d_r2",
        "transform_catalog_may_change_in_phase3d_r2",
        "comparison_signature_may_change_in_phase3d_r2",
        "holdout_checkpoint_population_may_change_in_phase3d_r2",
        "holdout_dominance_relations_may_change_from_outcomes",
    ):
        if model.get(key) is not False:
            errors.append("R2_3D_MODEL_FIREWALL_OPEN:" + key)

    outcome = contract.get("outcome_definition", {})
    if outcome.get("fixed_sessions") != [1, 3, 5]:
        errors.append("R2_3D_HORIZON_DRIFT")
    if outcome.get("primary_security_outcome") != "LOCAL_CURRENCY_PRICE_RETURN":
        errors.append("R2_3D_OUTCOME_DRIFT")
    if outcome.get("pairwise_edge_metric") != "DOMINATOR_RETURN_MINUS_DOMINATED_RETURN":
        errors.append("R2_3D_EDGE_METRIC_DRIFT")

    gate = contract.get("evidence_readiness_gate", {})
    for key in (
        "all_edges_required_no_result_based_dropping",
        "all_fixed_horizons_required",
        "entry_and_horizon_close_required_for_every_endpoint",
        "exchange_session_schedule_required_for_every_endpoint",
        "corporate_action_status_required_for_every_evaluation_window",
        "source_semantics_and_lineage_required",
    ):
        if gate.get(key) is not True:
            errors.append("R2_3D_EVIDENCE_GATE_FALSE:" + key)
    if gate.get("partial_coverage_may_support_r2_performance_claim") is not False:
        errors.append("R2_3D_PARTIAL_COVERAGE_PERFORMANCE_OPEN")
    if gate.get("missing_evidence_may_be_filled_with_proxy") is not False:
        errors.append("R2_3D_PROXY_FILL_OPEN")

    inventory = contract.get("preexisting_governed_outcome_inventory", {})
    if inventory.get("audit_only_no_return_calculation") is not True:
        errors.append("R2_3D_ROUND1_NOT_AUDIT_ONLY")
    if inventory.get("external_or_new_outcome_source_acquisition_in_round1") is not False:
        errors.append("R2_3D_ROUND1_EXTERNAL_FETCH_OPEN")
    if inventory.get("round1_return_calculation_allowed") is not False:
        errors.append("R2_3D_ROUND1_RETURN_CALC_OPEN")

    allowed = contract.get("allowed_if_evidence_ready", {})
    for key in (
        "portfolio_pnl",
        "sharpe_ratio",
        "assumed_trade_hit_rate",
        "regret_without_explicit_counterfactual",
        "probability_calibration",
        "scalar_model_score",
        "global_winner_selection",
        "statistical_significance_claim",
    ):
        if allowed.get(key) is not False:
            errors.append("R2_3D_FORBIDDEN_METRIC_OPEN:" + key)

    boundary = contract.get("phase_boundary", {})
    if boundary.get("phase4_entry_allowed") is not False:
        errors.append("R2_3D_PREMATURE_PHASE4")
    if boundary.get("phase3d_r2_performance_started") is not False:
        errors.append("R2_3D_PREMATURE_PERFORMANCE")
    return errors


def _load_inventory() -> dict[str, Any]:
    source_security_dates: dict[str, set[str]] = {}
    source_records: list[dict[str, Any]] = []

    if OUTCOME_MANIFEST.exists():
        manifest = json.loads(OUTCOME_MANIFEST.read_text(encoding="utf-8"))
        for src in manifest.get("external_sources", []):
            source_records.append({
                "artifact": OUTCOME_MANIFEST.name,
                "security_id": src.get("security_id"),
                "source_kind": src.get("source_kind"),
                "provider": src.get("provider"),
                "close_semantics": src.get("close_semantics"),
                "historical_range_loaded": src.get("historical_range_loaded"),
                "corporate_action_status_explicit": False,
                "exchange_session_schedule_explicit": False,
            })
        for sid, row in manifest.get("price_series", {}).items():
            source_security_dates.setdefault(sid, set()).update(row.get("observations", {}).keys())

    if PRICE_LEDGER.exists():
        for raw in PRICE_LEDGER.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            sid = row.get("security_id")
            date = row.get("trade_date")
            if sid and date:
                source_security_dates.setdefault(sid, set()).add(date)
            source_records.append({
                "artifact": str(PRICE_LEDGER.relative_to(ROOT.parent)),
                "security_id": sid,
                "source_kind": row.get("source_role"),
                "provider": row.get("provider"),
                "close_semantics": "close",
                "historical_range_loaded": [date, date] if date else None,
                "corporate_action_status_explicit": False,
                "exchange_session_schedule_explicit": False,
            })

    daily = None
    if DAILY_MANIFEST.exists():
        daily = json.loads(DAILY_MANIFEST.read_text(encoding="utf-8"))

    return {
        "security_dates": {k: sorted(v) for k, v in source_security_dates.items()},
        "source_records": source_records,
        "daily_snapshot_manifest": {
            "as_of_date": daily.get("as_of_date") if daily else None,
            "row_count": daily.get("row_count") if daily else None,
            "publication_status": daily.get("publication_status") if daily else None,
            "is_single_date_snapshot": True if daily else None,
        },
    }


def _edge_population(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for checkpoint in replay["checkpoints"]:
        for group in checkpoint["groups"]:
            if group["status"] != "COMPARABLE_EXACT_SIGNATURE":
                continue
            for dominated, dominators in sorted(group.get("dominated_by", {}).items()):
                for dominator in sorted(dominators):
                    edges.append({
                        "checkpoint_id": checkpoint["checkpoint_id"],
                        "checkpoint_at": checkpoint["at"],
                        "comparison_signature_sha256": group["comparison_signature_sha256"],
                        "dominator_security_id": dominator,
                        "dominated_security_id": dominated,
                    })
    return edges


def build_measurability_audit(repo_root: str | Path | None = None) -> dict[str, Any]:
    contract = load_contract()
    contract_errors = validate_contract(contract)
    if contract_errors:
        raise ValueError("INVALID_PHASE3D_R2_MEASURABILITY_CONTRACT:" + ";".join(contract_errors))

    replay = build_holdout_replay(repo_root if repo_root is not None else ROOT.parent)
    parent = contract["parent_holdout"]
    audit_errors: list[str] = []
    if replay.get("status") != parent["status"]:
        audit_errors.append("R2_3D_HOLDOUT_STATUS_DRIFT")
    if replay.get("replay_sha256") != parent["replay_sha256"]:
        audit_errors.append("R2_3D_HOLDOUT_SHA_DRIFT")

    edges = _edge_population(replay)
    if len(edges) != replay.get("dominance_edge_count"):
        audit_errors.append("R2_3D_EDGE_RECONSTRUCTION_COUNT_DRIFT")

    required_pairs = sorted({
        (edge["checkpoint_id"], edge["dominator_security_id"])
        for edge in edges
    } | {
        (edge["checkpoint_id"], edge["dominated_security_id"])
        for edge in edges
    })
    required_securities = sorted({sid for _, sid in required_pairs})
    inventory = _load_inventory()
    any_price_securities = sorted(set(required_securities) & set(inventory["security_dates"]))
    no_price_securities = sorted(set(required_securities) - set(inventory["security_dates"]))

    # Round 1 deliberately does not infer a trading calendar or corporate-action
    # state from sparse close observations. Those are separate readiness gates.
    session_schedule_ready_securities: list[str] = []
    corporate_action_ready_securities: list[str] = []

    endpoint_readiness: dict[tuple[str, str], bool] = {}
    for pair in required_pairs:
        _, sid = pair
        endpoint_readiness[pair] = (
            sid in any_price_securities
            and sid in session_schedule_ready_securities
            and sid in corporate_action_ready_securities
        )

    complete_edges = sum(
        endpoint_readiness[(edge["checkpoint_id"], edge["dominator_security_id"])]
        and endpoint_readiness[(edge["checkpoint_id"], edge["dominated_security_id"])]
        for edge in edges
    )

    structural_measurable = len(edges) > 0
    evidence_ready = (
        structural_measurable
        and complete_edges == len(edges)
        and len(edges) == parent["dominance_edge_count"]
        and not audit_errors
    )

    statuses = contract["round1_classification"]
    if audit_errors:
        status = statuses["fail_status"]
    elif not structural_measurable:
        status = statuses["not_measurable_status"]
    elif evidence_ready:
        status = statuses["pass_status"]
    else:
        status = statuses["partial_status"]

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3D_R2",
        "round": "R1_MEASURABILITY_CONTRACT_AND_EVIDENCE_AUDIT",
        "status": status,
        "model_form": replay["model_form"],
        "model_version": replay["model_version"],
        "parent_holdout_replay_sha256": replay["replay_sha256"],
        "checkpoint_count": replay["checkpoint_count"],
        "r2_profile_count": replay["r2_profile_instances"],
        "comparable_group_count": replay["comparable_exact_signature_group_instances"],
        "comparable_profile_count": replay["comparable_profile_instances"],
        "frozen_dominance_edge_count": len(edges),
        "required_edge_endpoint_instances": len(required_pairs),
        "required_edge_endpoint_security_count": len(required_securities),
        "required_edge_endpoint_security_ids": required_securities,
        "preexisting_price_observation_security_count": len(any_price_securities),
        "preexisting_price_observation_security_ids": any_price_securities,
        "missing_any_price_observation_security_count": len(no_price_securities),
        "missing_any_price_observation_security_ids": no_price_securities,
        "exchange_session_schedule_ready_security_count": len(session_schedule_ready_securities),
        "corporate_action_status_ready_security_count": len(corporate_action_ready_securities),
        "complete_evidence_edge_count": complete_edges,
        "incomplete_evidence_edge_count": len(edges) - complete_edges,
        "structurally_measurable": structural_measurable,
        "complete_outcome_evidence_ready": evidence_ready,
        "performance_calculation_authorized": evidence_ready,
        "partial_result_is_economic_underperformance": False,
        "not_measurable_result_is_economic_underperformance": False,
        "outcome_inventory": inventory,
        "frozen_edge_population": edges,
        "audit_errors": sorted(set(audit_errors)),
        "phase3d_r2_governed_state_started": False,
        "phase3d_r2_performance_started": False,
        "phase3e_r2_started": False,
        "repeat_phase3f_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
        "controls": deepcopy(CONTROLS),
    }
    result["audit_sha256"] = _sha256({k: v for k, v in result.items() if k != "audit_sha256"})
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_measurability_audit()
    target = write_default(result)
    print(
        "PHASE3D_R2_MEASURABILITY_AUDIT_RESULT "
        f"status={result['status']} checkpoints={result['checkpoint_count']} "
        f"edges={result['frozen_dominance_edge_count']} endpoint_instances={result['required_edge_endpoint_instances']} "
        f"endpoint_securities={result['required_edge_endpoint_security_count']} "
        f"price_securities={result['preexisting_price_observation_security_count']} "
        f"complete_edges={result['complete_evidence_edge_count']} "
        f"incomplete_edges={result['incomplete_evidence_edge_count']} "
        f"performance_authorized={str(result['performance_calculation_authorized']).lower()} "
        "returns=0 performance=0 phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['audit_sha256']} path={target}"
    )
