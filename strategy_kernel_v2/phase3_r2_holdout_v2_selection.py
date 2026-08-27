"""Build Holdout V2 deterministic selection ledger under the accepted pre-result contract.

V2 changes only model-neutral historical coverage: the protected-main time
universe, first-parent census selector, seed firewall and quantitative gates
remain the accepted H0/H0.1 rules. No R2 profile, Pareto replay, realized
outcome, future return, regret or calibration data is read here.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_kernel_v2.phase3_r2_holdout_h1 import (
    FALSE_CONTROLS as H1_FALSE_CONTROLS,
    _commit_subject,
    _commit_time,
    _evaluate_sufficiency,
    _load_json,
    _parse_time,
    _sha256,
    _universe_commits,
    build_family_catalog,
    build_source_snapshot,
)

ROOT = Path(__file__).resolve().parent
H0_CONTRACT_FILE = ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json"
V2_CONTRACT_FILE = ROOT / "PHASE3_R2_HOLDOUT_COVERAGE_EXPANSION_V2_CONTRACT.json"
REGISTRY_FILE = ROOT / "PHASE3A_EVIDENCE_REGISTRY.json"
OUTPUT_FILE = ROOT / "generated/PHASE3_R2_HOLDOUT_V2_SELECTION_LEDGER.json"

FALSE_CONTROLS = deepcopy(H1_FALSE_CONTROLS)
FALSE_CONTROLS.update(
    {
        "v1_h1_result_used_to_relax_threshold": False,
        "v1_h1_result_used_to_select_family": False,
        "v1_h1_result_used_to_select_security": False,
        "v2_contract_mutated_during_selection": False,
    }
)


def load_v2_contract() -> dict[str, Any]:
    return _load_json(V2_CONTRACT_FILE)


def _selection_contract(h0: Mapping[str, Any], v2: Mapping[str, Any]) -> dict[str, Any]:
    contract = deepcopy(h0)
    research = list(contract["frozen_evidence_families"]["research_or_decision_families"])
    for row in v2["coverage_expansion"]["added_substantive_families"]:
        if row["family_id"] not in research:
            research.append(row["family_id"])
    contract["frozen_evidence_families"]["research_or_decision_families"] = research
    return contract


def build_v2_family_catalog(
    registry: Mapping[str, Any],
    h0: Mapping[str, Any],
    v2: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    catalog = build_family_catalog(registry, h0)
    for row in v2["coverage_expansion"]["added_substantive_families"]:
        family_id = row["family_id"]
        if family_id in catalog:
            raise AssertionError("V2_ADDED_FAMILY_COLLIDES_WITH_V1:" + family_id)
        catalog[family_id] = {
            "family_id": family_id,
            "evidence_classes": [row["classification"]],
            "security_ids": [],
            "paths": [row["path"]],
            "coverage_expansion_v2": True,
            "contributes_to_security_scope": row["contributes_to_security_scope"],
        }
    return dict(sorted(catalog.items()))


def build_holdout_v2_selection_ledger(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    h0 = _load_json(H0_CONTRACT_FILE)
    v2 = load_v2_contract()
    registry = _load_json(REGISTRY_FILE)

    if v2["status"] != "FROZEN_PRE_RESULT_COVERAGE_EXPANSION_NO_R2_NO_OUTCOMES":
        raise AssertionError("V2_SELECTION_REQUIRES_ACCEPTED_PRE_RESULT_CONTRACT")
    if v2["pre_result_firewall"]["v2_selection_started"] is not False:
        raise AssertionError("V2_CONTRACT_ALREADY_MARKS_SELECTION_STARTED")
    if v2["pre_result_firewall"]["r2_holdout_replay_count"] != 0:
        raise AssertionError("V2_CONTRACT_R2_REPLAY_NONZERO")
    if v2["pre_result_firewall"]["realized_outcome_read_count"] != 0:
        raise AssertionError("V2_CONTRACT_OUTCOME_READ_NONZERO")
    if v2["parent_h1"]["threshold_relaxation_after_result_allowed"] is not False:
        raise AssertionError("V2_POST_H1_THRESHOLD_RELAXATION_OPEN")

    start_sha = v2["unchanged_v1_contract"]["protected_main_universe"]["start_commit_inclusive"]
    end_sha = v2["unchanged_v1_contract"]["protected_main_universe"]["end_commit_inclusive"]
    if start_sha != h0["frozen_repository_universe"]["start_commit_inclusive"]:
        raise AssertionError("V2_SELECTION_UNIVERSE_START_DRIFT")
    if end_sha != h0["frozen_repository_universe"]["end_commit_inclusive"]:
        raise AssertionError("V2_SELECTION_UNIVERSE_END_DRIFT")

    selection_contract = _selection_contract(h0, v2)
    family_catalog = build_v2_family_catalog(registry, h0, v2)
    if len(family_catalog) != v2["coverage_expansion"]["expected_total_family_count_after_expansion"]:
        raise AssertionError("V2_FAMILY_CATALOG_COUNT_DRIFT")

    opportunity_security_ids = list(v2["v2_security_scope"]["security_ids"])
    if len(opportunity_security_ids) != v2["v2_security_scope"]["security_count"]:
        raise AssertionError("V2_SECURITY_SCOPE_COUNT_DRIFT")
    if opportunity_security_ids != sorted(opportunity_security_ids):
        raise AssertionError("V2_SECURITY_SCOPE_NOT_SORTED")

    seed_commits = set(h0["seed_firewall"]["excluded_commit_shas"])
    seed_source_identity_sets: set[str] = set()
    for seed_sha in sorted(seed_commits):
        seed_snapshot = build_source_snapshot(
            repo,
            seed_sha,
            family_catalog=family_catalog,
            opportunity_security_ids=opportunity_security_ids,
            contract=selection_contract,
        )
        seed_source_identity_sets.add(seed_snapshot["source_identity_set_sha256"])

    commits = _universe_commits(repo, start_sha, end_sha)
    selected: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    previous_main_fingerprint: str | None = None
    previous_selected_fingerprint: str | None = None
    selected_fingerprints: set[str] = set()

    for sha in commits:
        at = _commit_time(repo, sha)
        parsed = _parse_time(at)
        snapshot = build_source_snapshot(
            repo,
            sha,
            family_catalog=family_catalog,
            opportunity_security_ids=opportunity_security_ids,
            contract=selection_contract,
        )
        fingerprint = snapshot["decision_evidence_fingerprint_sha256"]
        changed_from_previous_main = (
            previous_main_fingerprint is None or fingerprint != previous_main_fingerprint
        )
        differs_from_previous_selected = (
            previous_selected_fingerprint is None
            or fingerprint != previous_selected_fingerprint
        )
        eligible_structure = (
            snapshot["candidate_state_present"]
            and bool(opportunity_security_ids)
            and snapshot["research_or_decision_family_count"]
            >= h0["deterministic_selector"]["minimum_research_or_decision_family_count"]
        )

        reason = None
        if not eligible_structure:
            reason = "INELIGIBLE_STRUCTURE"
        elif sha in seed_commits:
            reason = "EXCLUDED_SEED_COMMIT"
        elif not changed_from_previous_main:
            reason = "NO_FINGERPRINT_CHANGE_ON_THIS_MAIN_COMMIT"
        elif not differs_from_previous_selected:
            reason = "NO_CHANGE_FROM_PREVIOUS_SELECTED_CHECKPOINT"
        elif fingerprint in selected_fingerprints:
            reason = "DUPLICATE_PREVIOUSLY_SELECTED_FINGERPRINT"
        elif snapshot["source_identity_set_sha256"] in seed_source_identity_sets:
            reason = "EXACT_SEED_SOURCE_IDENTITY_SET_REUSE"

        is_selected = reason is None
        audit_rows.append(
            {
                "commit_sha": sha,
                "at": at,
                "eligible_structure": eligible_structure,
                "candidate_state_present": snapshot["candidate_state_present"],
                "research_or_decision_family_count": snapshot["research_or_decision_family_count"],
                "fingerprint_changed_from_previous_main_commit": changed_from_previous_main,
                "fingerprint_differs_from_previous_selected_checkpoint": differs_from_previous_selected,
                "source_identity_set_matches_seed": (
                    snapshot["source_identity_set_sha256"] in seed_source_identity_sets
                ),
                "seed_commit": sha in seed_commits,
                "selected": is_selected,
                "exclusion_reason": reason,
                "decision_evidence_fingerprint_sha256": fingerprint,
            }
        )

        if is_selected:
            checkpoint_id = (
                "HOLDOUT_V2_CP_"
                + parsed.strftime("%Y%m%dT%H%M%SZ")
                + "_"
                + sha[:8].upper()
            )
            selected.append(
                {
                    "checkpoint_id": checkpoint_id,
                    "at": at,
                    "utc_date": parsed.date().isoformat(),
                    "iso_week": f"{parsed.isocalendar().year}-W{parsed.isocalendar().week:02d}",
                    "canonical_commit_sha": sha,
                    "commit_subject": _commit_subject(repo, sha),
                    "checkpoint_type": "INDEPENDENT_HOLDOUT_V2_PIT_CHECKPOINT",
                    "opportunity_scope_policy": "V2_FROZEN_RESEARCH_SECURITY_SCOPE_18",
                    "opportunity_security_ids": opportunity_security_ids,
                    "available_frozen_evidence_family_ids": snapshot["family_ids"],
                    "research_or_decision_family_count": snapshot["research_or_decision_family_count"],
                    "evidence_regime_family_ids": snapshot["evidence_regime_family_ids"],
                    "evidence_regime_signature": snapshot["evidence_regime_signature"],
                    "source_identity_set_sha256": snapshot["source_identity_set_sha256"],
                    "decision_evidence_fingerprint_sha256": fingerprint,
                    "source_identities": snapshot["family_rows"],
                }
            )
            previous_selected_fingerprint = fingerprint
            selected_fingerprints.add(fingerprint)

        previous_main_fingerprint = fingerprint

    sufficiency = _evaluate_sufficiency(selected, h0)
    status = (
        "PASS_SELECTION_SUFFICIENCY"
        if sufficiency["all_thresholds_passed"]
        else "FAIL_SELECTION_SUFFICIENCY"
    )
    exclusion_counts = Counter(row["exclusion_reason"] or "SELECTED" for row in audit_rows)

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3_R2_INDEPENDENT_POINT_IN_TIME_HOLDOUT",
        "subphase": "HOLDOUT_COVERAGE_EXPANSION_V2_DETERMINISTIC_SELECTION",
        "status": status,
        "v2_contract_id": v2["contract_id"],
        "parent_h1_result": v2["parent_h1"]["result"],
        "parent_h1_checkpoint_count": v2["parent_h1"]["selected_checkpoint_count"],
        "selector_mode": h0["deterministic_selector"]["mode"],
        "frozen_universe": {
            "start_commit_inclusive": start_sha,
            "end_commit_inclusive": end_sha,
            "commit_count": len(commits),
        },
        "v2_security_scope_ids": opportunity_security_ids,
        "v2_security_scope_count": len(opportunity_security_ids),
        "family_catalog": family_catalog,
        "family_catalog_count": len(family_catalog),
        "seed_exclusion_count": len(seed_commits),
        "universe_commit_audit_count": len(audit_rows),
        "selected_checkpoint_count": len(selected),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "sufficiency": sufficiency,
        "selected_checkpoints": selected,
        "universe_commit_audit": audit_rows,
        "realized_outcomes_read_count": 0,
        "phase3d_results_read_count": 0,
        "r2_profile_compute_count": 0,
        "r2_pareto_replay_count": 0,
        "future_return_read_count": 0,
        "regret_or_calibration_read_count": 0,
        "discretionary_subsampling_count": 0,
        "manual_cherry_pick_count": 0,
        "h2_start_allowed": sufficiency["all_thresholds_passed"],
        "h2_started": False,
        "phase3_historical_validation_complete": False,
        "phase4_entry_allowed": False,
        "controls": deepcopy(FALSE_CONTROLS),
    }
    result["selection_ledger_sha256"] = _sha256(
        {k: v for k, v in result.items() if k != "selection_ledger_sha256"}
    )
    return result


def write_default(
    result: Mapping[str, Any],
    path: str | Path = OUTPUT_FILE,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_holdout_v2_selection_ledger()
    target = write_default(result)
    observed = result["sufficiency"]["observed"]
    print(
        "PHASE3_R2_HOLDOUT_V2_SELECTION_LEDGER_BUILT "
        f"status={result['status']} checkpoints={observed['holdout_checkpoints']} "
        f"dates={observed['distinct_utc_dates']} weeks={observed['distinct_iso_weeks']} "
        f"regimes={observed['distinct_evidence_regime_signatures']} "
        f"securities={observed['unique_securities']} profiles={observed['opportunity_profile_instances']} "
        f"outside_seed={observed['checkpoints_strictly_outside_seed_time_span']} "
        f"max_date_fraction={observed['maximum_single_utc_date_fraction']:.6f} "
        f"max_regime_fraction={observed['maximum_single_evidence_regime_fraction']:.6f} "
        "outcomes_read=0 r2_replays=0 "
        f"h2_start_allowed={str(result['h2_start_allowed']).lower()} "
        "phase4_entry_allowed=false orders=0 trade_authority=NONE "
        f"sha256={result['selection_ledger_sha256']} path={target}"
    )
