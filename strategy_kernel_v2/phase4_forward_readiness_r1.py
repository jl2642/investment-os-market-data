"""Phase 4 P4-1 forward observation readiness / deterministic discovery audit.

This module discovers genuinely-forward canonical checkpoints only. It does not
run Legacy or R2, compute Pareto relations, read outcomes, or start Phase 4
empirical execution. The audit is frozen to an explicitly captured protected-main
head so the result is reproducible.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.phase3_r2_holdout_h1 import (
    _commit_subject,
    _commit_time,
    _git,
    _load_json,
    _parse_time,
    _sha256,
    build_source_snapshot,
)
from strategy_kernel_v2.phase3_r2_holdout_v2_selection import (
    _selection_contract,
    build_v2_family_catalog,
    load_v2_contract,
)

ROOT = Path(__file__).resolve().parent
ADAPTER_FILE = ROOT / "PHASE4_FORWARD_READINESS_R1_CONTRACT.json"
H0_FILE = ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json"
REGISTRY_FILE = ROOT / "PHASE3A_EVIDENCE_REGISTRY.json"
OUTPUT_FILE = ROOT / "generated/PHASE4_FORWARD_READINESS_R1_AUDIT.json"

FALSE_CONTROLS = {
    "legacy_runner_executed": False,
    "r2_profile_values_computed": False,
    "r2_pareto_replay_executed": False,
    "realized_outcomes_read": False,
    "future_returns_read": False,
    "result_based_checkpoint_selection_used": False,
    "model_specific_evidence_fetch_used": False,
    "later_input_backfill_used": False,
    "candidate_membership_mutation_allowed": False,
    "real_position_mutation_allowed": False,
    "simulation_position_mutation_allowed": False,
    "target_portfolio_writeback_allowed": False,
    "user_decision_generation_allowed": False,
    "investment_recommendation_generation_allowed": False,
    "order_authorized": False,
    "orders": 0,
    "trade_authority": "NONE",
}


def load_adapter() -> dict[str, Any]:
    return _load_json(ADAPTER_FILE)


def _first_parent_commits(repo: Path, end_sha: str) -> list[str]:
    raw = _git(repo, "rev-list", "--first-parent", "--reverse", end_sha)
    return [line for line in raw.splitlines() if line]


def _substantive_trigger_rows(
    snapshot: Mapping[str, Any],
    *,
    checkpoint_sha: str,
    cutoff: str,
    research_family_ids: set[str],
) -> list[dict[str, Any]]:
    cutoff_dt = _parse_time(cutoff)
    substantive = {"CANDIDATE_STATE"} | research_family_ids
    rows: list[dict[str, Any]] = []
    for row in snapshot["family_rows"]:
        if row["family_id"] not in substantive:
            continue
        active = row["active_source"]
        if active["source_commit_sha"] != checkpoint_sha:
            continue
        if _parse_time(active["available_at"]) <= cutoff_dt:
            continue
        rows.append(
            {
                "family_id": row["family_id"],
                "path": active["path"],
                "blob_sha": active["blob_sha"],
                "source_commit_sha": active["source_commit_sha"],
                "available_at": active["available_at"],
            }
        )
    return rows


def build_forward_readiness_audit(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    adapter = load_adapter()
    if adapter["status"] != "FROZEN_BEFORE_P4_1_DISCOVERY_AUDIT":
        raise AssertionError("P4_R1_ADAPTER_NOT_FROZEN")

    h0 = _load_json(H0_FILE)
    v2 = load_v2_contract()
    registry = _load_json(REGISTRY_FILE)
    selection_contract = _selection_contract(h0, v2)
    family_catalog = build_v2_family_catalog(registry, h0, v2)
    security_ids = list(adapter["inherited_model_neutral_catalog"]["security_scope_ids"])

    if len(family_catalog) != adapter["inherited_model_neutral_catalog"]["family_catalog_count"]:
        raise AssertionError("P4_R1_FAMILY_CATALOG_DRIFT")
    if security_ids != v2["v2_security_scope"]["security_ids"]:
        raise AssertionError("P4_R1_SECURITY_SCOPE_DRIFT")

    cutoff = adapter["frozen_phase4_contract"]["future_cutoff_utc"]
    cutoff_dt = _parse_time(cutoff)
    end_sha = adapter["source_universe"]["as_of_protected_main_head"]
    end_at = _commit_time(repo, end_sha)
    if _parse_time(end_at) != _parse_time(adapter["source_universe"]["as_of_protected_main_head_commit_time_utc"]):
        raise AssertionError("P4_R1_AS_OF_MAIN_HEAD_TIME_DRIFT")

    commits = _first_parent_commits(repo, end_sha)
    pre_cutoff = [sha for sha in commits if _parse_time(_commit_time(repo, sha)) <= cutoff_dt]
    post_cutoff = [sha for sha in commits if _parse_time(_commit_time(repo, sha)) > cutoff_dt]
    if not pre_cutoff:
        raise AssertionError("P4_R1_NO_PRE_CUTOFF_BASELINE_COMMIT")

    baseline_sha = pre_cutoff[-1]
    baseline_snapshot = build_source_snapshot(
        repo,
        baseline_sha,
        family_catalog=family_catalog,
        opportunity_security_ids=security_ids,
        contract=selection_contract,
    )
    previous_main_fingerprint = baseline_snapshot["decision_evidence_fingerprint_sha256"]
    previous_selected_fingerprint: str | None = None
    selected_fingerprints: set[str] = set()
    research_family_ids = set(selection_contract["frozen_evidence_families"]["research_or_decision_families"])

    audit_rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for sha in post_cutoff:
        at = _commit_time(repo, sha)
        snapshot = build_source_snapshot(
            repo,
            sha,
            family_catalog=family_catalog,
            opportunity_security_ids=security_ids,
            contract=selection_contract,
        )
        fingerprint = snapshot["decision_evidence_fingerprint_sha256"]
        changed_from_previous_main = fingerprint != previous_main_fingerprint
        differs_from_previous_selected = (
            previous_selected_fingerprint is None
            or fingerprint != previous_selected_fingerprint
        )
        triggers = _substantive_trigger_rows(
            snapshot,
            checkpoint_sha=sha,
            cutoff=cutoff,
            research_family_ids=research_family_ids,
        )
        eligible_structure = (
            snapshot["candidate_state_present"]
            and snapshot["research_or_decision_family_count"]
            >= adapter["selector_semantics"]["minimum_research_or_decision_family_count"]
        )

        reason = None
        if not eligible_structure:
            reason = "INELIGIBLE_STRUCTURE"
        elif not changed_from_previous_main:
            reason = "NO_DECISION_EVIDENCE_FINGERPRINT_CHANGE_ON_MAIN_COMMIT"
        elif not triggers:
            reason = "NO_POST_CUTOFF_SUBSTANTIVE_TRIGGER_CHANGED_ON_COMMIT"
        elif not differs_from_previous_selected:
            reason = "NO_CHANGE_FROM_PREVIOUS_SELECTED_FORWARD_CHECKPOINT"
        elif fingerprint in selected_fingerprints:
            reason = "DUPLICATE_PREVIOUSLY_SELECTED_FORWARD_FINGERPRINT"

        is_selected = reason is None
        audit_rows.append(
            {
                "commit_sha": sha,
                "at": at,
                "commit_subject": _commit_subject(repo, sha),
                "eligible_structure": eligible_structure,
                "candidate_state_present": snapshot["candidate_state_present"],
                "research_or_decision_family_count": snapshot["research_or_decision_family_count"],
                "fingerprint_changed_from_previous_main_commit": changed_from_previous_main,
                "fingerprint_differs_from_previous_selected_checkpoint": differs_from_previous_selected,
                "post_cutoff_substantive_trigger_count": len(triggers),
                "post_cutoff_substantive_triggers": triggers,
                "selected": is_selected,
                "exclusion_reason": reason,
                "decision_evidence_fingerprint_sha256": fingerprint,
                "evidence_regime_signature": snapshot["evidence_regime_signature"],
            }
        )
        if is_selected:
            parsed = _parse_time(at)
            selected.append(
                {
                    "checkpoint_id": "P4_FWD_CP_" + parsed.strftime("%Y%m%dT%H%M%SZ") + "_" + sha[:8].upper(),
                    "canonical_main_commit_sha": sha,
                    "at": at,
                    "utc_date": parsed.date().isoformat(),
                    "iso_week": f"{parsed.isocalendar().year}-W{parsed.isocalendar().week:02d}",
                    "opportunity_security_ids": security_ids,
                    "evidence_regime_signature": snapshot["evidence_regime_signature"],
                    "decision_evidence_fingerprint_sha256": fingerprint,
                    "post_cutoff_substantive_triggers": triggers,
                    "source_identities": snapshot["family_rows"],
                }
            )
            previous_selected_fingerprint = fingerprint
            selected_fingerprints.add(fingerprint)
        previous_main_fingerprint = fingerprint

    if not post_cutoff:
        status = "WAITING_FOR_FIRST_POST_CUTOFF_CANONICAL_MAIN_COMMIT"
    elif not selected:
        status = "WAITING_FOR_ELIGIBLE_FORWARD_CHECKPOINT"
    else:
        status = "FORWARD_CHECKPOINTS_DISCOVERED_READY_FOR_PARALLEL_REPLAY"

    exclusion_counts = Counter(row["exclusion_reason"] or "SELECTED" for row in audit_rows)
    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_4",
        "subphase": "P4_1_FORWARD_OBSERVATION_READINESS_AND_SELECTOR",
        "status": status,
        "frozen_cutoff_utc": cutoff,
        "as_of_protected_main_head": end_sha,
        "as_of_protected_main_head_commit_time_utc": end_at,
        "baseline_main_commit_at_or_before_cutoff": baseline_sha,
        "baseline_main_commit_time_utc": _commit_time(repo, baseline_sha),
        "post_cutoff_first_parent_commit_count": len(post_cutoff),
        "post_cutoff_commit_audit_count": len(audit_rows),
        "selected_forward_checkpoint_count": len(selected),
        "selected_forward_checkpoints": selected,
        "post_cutoff_commit_audit": audit_rows,
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "family_catalog_count": len(family_catalog),
        "security_scope_count": len(security_ids),
        "legacy_runner_execution_count": 0,
        "r2_profile_compute_count": 0,
        "r2_pareto_compute_count": 0,
        "realized_outcome_read_count": 0,
        "future_return_read_count": 0,
        "phase4_parallel_replay_start_allowed_from_this_audit": bool(selected),
        "phase4_started": False,
        "phase4_forward_validation_complete": False,
        "phase5_migration_allowed": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
    result["readiness_audit_sha256"] = _sha256(
        {k: v for k, v in result.items() if k != "readiness_audit_sha256"}
    )
    return result


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_forward_readiness_audit()
    path = write_default(result)
    print(
        "PHASE4_FORWARD_READINESS_R1 "
        f"status={result['status']} main_head={result['as_of_protected_main_head']} "
        f"main_time={result['as_of_protected_main_head_commit_time_utc']} "
        f"cutoff={result['frozen_cutoff_utc']} post_cutoff_commits={result['post_cutoff_first_parent_commit_count']} "
        f"selected={result['selected_forward_checkpoint_count']} "
        "legacy_runs=0 r2_profiles=0 r2_pareto=0 outcomes=0 "
        "phase4_started=false phase5=false orders=0 trade_authority=NONE "
        f"sha256={result['readiness_audit_sha256']} path={path}"
    )
