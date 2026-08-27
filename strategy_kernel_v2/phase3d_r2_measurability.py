from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.phase3_r2_independent_holdout_replay import build_holdout_replay

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CONTRACT_FILE = ROOT / "PHASE3D_R2_MEASURABILITY_CONTRACT.json"
OUTPUT_FILE = ROOT / "generated" / "PHASE3D_R2_ROUND1_EVIDENCE_AUDIT.json"

ROUND1_PASS = "PASS_R2_MEASURABILITY_CONTRACT_FROZEN_EVIDENCE_ACQUISITION_REQUIRED"
ROUND1_FAIL = "FAIL_R2_MEASURABILITY_CONTRACT_OR_PARENT_AUDIT"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    return _load(CONTRACT_FILE)


def _git_path_exists(commit_sha: str, relative_path: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}:{relative_path}"],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "FROZEN_BEFORE_R2_OUTCOME_EVIDENCE_ACQUISITION":
        errors.append("PHASE3D_R2_CONTRACT_NOT_FROZEN")
    parent = contract.get("parent_holdout", {})
    if parent.get("pr") != 325:
        errors.append("PHASE3D_R2_PARENT_PR_DRIFT")
    if parent.get("final_head") != "4ac3d7d25ed65fd77747addbcbbd21ea47679332":
        errors.append("PHASE3D_R2_PARENT_HEAD_DRIFT")
    if parent.get("replay_status") != "PASS_INDEPENDENT_HOLDOUT_REPLAY_OPERATIONAL":
        errors.append("PHASE3D_R2_PARENT_REPLAY_STATUS_DRIFT")
    if contract.get("horizons", {}).get("fixed_sessions") != [1, 3, 5]:
        errors.append("PHASE3D_R2_HORIZON_DRIFT")
    if contract.get("horizons", {}).get("primary_session") != 5:
        errors.append("PHASE3D_R2_PRIMARY_HORIZON_DRIFT")

    semantic = contract.get("semantic_scope", {})
    if semantic.get("dominance_edge_is_not_a_hypothetical_trade") is not True:
        errors.append("PHASE3D_R2_EDGE_TRADE_GUARD_MISSING")
    if semantic.get("pareto_frontier_is_not_a_target_portfolio") is not True:
        errors.append("PHASE3D_R2_FRONTIER_PORTFOLIO_GUARD_MISSING")
    if semantic.get("r2_output_is_portfolio_or_trade_instruction") is not False:
        errors.append("PHASE3D_R2_OUTPUT_AUTHORITY_DRIFT")

    eval_units = contract.get("evaluation_units", {})
    if eval_units.get("primary_structural_unit") != "CHECKPOINT_LOCAL_EXACT_SIGNATURE_DOMINANCE_EDGE":
        errors.append("PHASE3D_R2_EVALUATION_UNIT_DRIFT")
    if eval_units.get("cross_checkpoint_comparison_allowed") is not False:
        errors.append("PHASE3D_R2_CROSS_CHECKPOINT_ALLOWED")
    if eval_units.get("cross_signature_comparison_allowed") is not False:
        errors.append("PHASE3D_R2_CROSS_SIGNATURE_ALLOWED")

    forbidden = contract.get("forbidden_metrics_or_claims", {})
    for key in (
        "synthetic_trade_return",
        "portfolio_return",
        "target_weight_return",
        "regret_without_contemporaneous_counterfactual_allocation",
        "probability_calibration",
        "scalar_cross_model_score",
        "global_ranking",
        "winner_selection",
    ):
        if forbidden.get(key) is not True:
            errors.append("PHASE3D_R2_FORBIDDEN_GUARD_FALSE:" + key)

    gate = contract.get("performance_evidence_sufficiency_gate", {})
    if gate.get("primary_horizon") != 5:
        errors.append("PHASE3D_R2_GATE_PRIMARY_HORIZON_DRIFT")
    for key in (
        "minimum_measurable_dominance_edge_fraction_primary_horizon",
        "minimum_measurable_comparable_group_fraction_primary_horizon",
        "minimum_measurable_comparable_checkpoint_fraction_primary_horizon",
    ):
        value = gate.get(key)
        if not isinstance(value, (int, float)) or not (0 < value <= 1):
            errors.append("PHASE3D_R2_INVALID_COVERAGE_THRESHOLD:" + key)

    freeze = contract.get("freeze_order", {})
    for key in (
        "contract_must_precede_r2_outcome_evidence_acquisition",
        "contract_must_precede_r2_realized_outcome_loading",
        "outcome_availability_may_not_change_model_or_holdout_membership",
        "outcome_availability_may_not_change_horizons_or_metric_semantics",
    ):
        if freeze.get(key) is not True:
            errors.append("PHASE3D_R2_FREEZE_GUARD_FALSE:" + key)
    for key in (
        "realized_outcomes_read_at_freeze",
        "future_returns_computed_at_freeze",
        "performance_metrics_computed_at_freeze",
    ):
        if freeze.get(key) is not False:
            errors.append("PHASE3D_R2_PREMATURE_OUTCOME_ACTIVITY:" + key)

    auth = contract.get("authority_boundaries", {})
    for key in (
        "effective_core_static_changes",
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "investment_recommendations_generated",
        "orders",
    ):
        if auth.get(key) != 0:
            errors.append("PHASE3D_R2_AUTHORITY_NONZERO:" + key)
    if auth.get("trade_authority") != "NONE":
        errors.append("PHASE3D_R2_TRADE_AUTHORITY_CHANGED")
    return errors


def _structural_counts(replay: Mapping[str, Any]) -> dict[str, Any]:
    comparable_checkpoints: set[str] = set()
    comparable_signatures: set[str] = set()
    edge_endpoint_securities: set[str] = set()
    edge_count = 0
    for checkpoint in replay.get("checkpoints", []):
        cp_has_comparable = False
        for group in checkpoint.get("groups", []):
            if group.get("status") != "COMPARABLE_EXACT_SIGNATURE":
                continue
            cp_has_comparable = True
            comparable_signatures.add(group["comparison_signature_sha256"])
            for dominated, dominators in group.get("dominated_by", {}).items():
                for dominator in dominators:
                    edge_count += 1
                    edge_endpoint_securities.add(dominator)
                    edge_endpoint_securities.add(dominated)
        if cp_has_comparable:
            comparable_checkpoints.add(checkpoint["checkpoint_id"])
    return {
        "comparable_checkpoint_count": len(comparable_checkpoints),
        "distinct_comparable_signature_count": len(comparable_signatures),
        "dominance_edge_count_recounted": edge_count,
        "edge_endpoint_security_count": len(edge_endpoint_securities),
        "edge_endpoint_security_ids": sorted(edge_endpoint_securities),
    }


def build_round1_evidence_audit(repo_root: str | Path | None = None) -> dict[str, Any]:
    contract = load_contract()
    contract_errors = validate_contract(contract)
    replay = build_holdout_replay(REPO)
    structural = _structural_counts(replay)

    parent = contract["parent_holdout"]
    parent_sha = parent["final_head"]
    r2_manifest = contract["outcome_source_contract"]["required_r2_manifest"]
    legacy_manifest = contract["outcome_source_contract"]["legacy_phase3d_manifest_is_not_r2_authority"]

    r2_manifest_preexisted = _git_path_exists(parent_sha, r2_manifest)
    legacy_manifest_preexisted = _git_path_exists(parent_sha, legacy_manifest)

    audit_errors = list(contract_errors)
    if replay.get("status") != parent["replay_status"]:
        audit_errors.append("PHASE3D_R2_PARENT_REPLAY_NOT_ACCEPTED")

    expected_counts = {
        "checkpoint_count": parent["checkpoint_count"],
        "r2_profile_instances": parent["r2_profile_count"],
        "comparable_exact_signature_group_instances": parent["comparable_group_count"],
        "comparable_profile_instances": parent["comparable_profile_count"],
        "dominance_edge_count": parent["dominance_edge_count"],
    }
    for key, expected in expected_counts.items():
        if replay.get(key) != expected:
            audit_errors.append("PHASE3D_R2_PARENT_COUNT_DRIFT:" + key)

    if structural["dominance_edge_count_recounted"] != parent["dominance_edge_count"]:
        audit_errors.append("PHASE3D_R2_EDGE_RECOUNT_DRIFT")
    if r2_manifest_preexisted:
        audit_errors.append("PHASE3D_R2_OUTCOME_MANIFEST_PREEXISTED_CONTRACT_FREEZE")
    if not legacy_manifest_preexisted:
        audit_errors.append("PHASE3D_R2_LEGACY_OUTCOME_MANIFEST_EXPECTED_BUT_MISSING")

    status = ROUND1_FAIL if audit_errors else ROUND1_PASS
    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3D_R2",
        "round": "ROUND_1_MEASURABILITY_CONTRACT_AND_EVIDENCE_AUDIT",
        "status": status,
        "measurability_status": (
            "PENDING_OUTCOME_EVIDENCE_ACQUISITION"
            if status == ROUND1_PASS
            else "BLOCKED_BY_CONTRACT_OR_PARENT_AUDIT"
        ),
        "economic_performance_measurement_status": "NOT_AUTHORIZED_IN_ROUND_1",
        "parent_holdout_replay_sha256": replay.get("replay_sha256"),
        "checkpoint_count": replay.get("checkpoint_count"),
        "r2_profile_count": replay.get("r2_profile_instances"),
        "comparable_group_count": replay.get("comparable_exact_signature_group_instances"),
        "comparable_profile_count": replay.get("comparable_profile_instances"),
        "dominance_edge_count": replay.get("dominance_edge_count"),
        **structural,
        "required_r2_outcome_manifest": r2_manifest,
        "r2_outcome_manifest_present_at_parent_freeze": r2_manifest_preexisted,
        "legacy_phase3d_outcome_manifest_present_at_parent_freeze": legacy_manifest_preexisted,
        "legacy_phase3d_outcome_manifest_authorized_for_r2": False,
        "outcome_manifest_content_read_count": 0,
        "realized_outcome_value_read_count": 0,
        "future_return_compute_count": 0,
        "performance_metric_compute_count": 0,
        "synthetic_trade_count": 0,
        "portfolio_return_metric_count": 0,
        "winner_selection_count": 0,
        "audit_errors": sorted(set(audit_errors)),
        "next_step": (
            "PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION_UNDER_FROZEN_CONTRACT"
            if status == ROUND1_PASS
            else "PHASE_3D_R2_GOVERNANCE_REVIEW"
        ),
        "phase3e_r2_start_allowed": False,
        "repeat_phase3f_start_allowed": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
        "orders": 0,
        "trade_authority": "NONE",
    }

    payload = {k: v for k, v in result.items() if k != "audit_sha256"}
    result["audit_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_round1_evidence_audit()
    target = write_default(result)
    if result["status"] != ROUND1_PASS:
        raise AssertionError(";".join(result["audit_errors"]))
    print(
        "PHASE3D_R2_ROUND1_EVIDENCE_AUDIT_PASS "
        f"checkpoints={result['checkpoint_count']} profiles={result['r2_profile_count']} "
        f"comparable_groups={result['comparable_group_count']} "
        f"comparable_checkpoints={result['comparable_checkpoint_count']} "
        f"dominance_edges={result['dominance_edge_count']} "
        f"edge_securities={result['edge_endpoint_security_count']} "
        "r2_manifest_preexisting=false outcomes_read=0 performance=0 "
        "next=PHASE_3D_R2_OUTCOME_EVIDENCE_ACQUISITION_UNDER_FROZEN_CONTRACT "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['audit_sha256']} path={target}"
    )
