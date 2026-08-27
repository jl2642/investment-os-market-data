"""Build the R2 independent point-in-time Holdout H1 candidate ledger.

H1 performs selection only. It traverses the frozen protected-main ancestry,
constructs point-in-time source identities for the H0-frozen evidence families,
and selects the census of eligible commits where the decision-evidence
fingerprint genuinely changes on that commit.

H1 MUST NOT compute R2 profiles, execute Pareto replay, load Phase 3D realized
outcomes, use future returns, or tune selection from model results.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
CONTRACT_FILE = ROOT / "PHASE3_R2_HOLDOUT_SELECTION_CONTRACT.json"
REGISTRY_FILE = ROOT / "PHASE3A_EVIDENCE_REGISTRY.json"
OUTPUT_FILE = ROOT / "generated/PHASE3_R2_HOLDOUT_SELECTION_LEDGER.json"

FALSE_CONTROLS = {
    "realized_outcomes_read": False,
    "phase3d_results_read": False,
    "r2_profile_values_computed": False,
    "r2_pareto_replay_executed": False,
    "r2_replayability_used_for_selection": False,
    "future_returns_used_for_selection": False,
    "regret_or_calibration_used_for_selection": False,
    "discretionary_subsampling_used": False,
    "random_sampling_used": False,
    "manual_cherry_pick_used": False,
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


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            "GIT_COMMAND_FAILED:" + " ".join(args) + ":" + proc.stderr.strip()
        )
    return proc.stdout.strip()


def _parse_time(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _commit_time(repo: Path, sha: str) -> str:
    return _git(repo, "show", "-s", "--format=%cI", sha)


def _commit_subject(repo: Path, sha: str) -> str:
    return _git(repo, "show", "-s", "--format=%s", sha)


def _blob_at(repo: Path, sha: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{sha}:{path}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _last_change_commit(repo: Path, sha: str, path: str) -> str:
    value = _git(repo, "log", "-1", "--format=%H", sha, "--", path)
    if not value:
        raise AssertionError("H1_SOURCE_PRESENT_WITHOUT_CHANGE_COMMIT:" + path)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_family_catalog(
    registry: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    permitted = set(contract["frozen_evidence_families"]["required_base_families"])
    permitted.update(contract["frozen_evidence_families"]["context_families"])
    permitted.update(contract["frozen_evidence_families"]["research_or_decision_families"])

    catalog: dict[str, dict[str, Any]] = {}
    for record in registry["records"]:
        family = record["evidence_key"]
        if family not in permitted:
            continue
        entry = catalog.setdefault(
            family,
            {
                "family_id": family,
                "evidence_classes": set(),
                "security_ids": set(),
                "paths": set(),
            },
        )
        entry["evidence_classes"].add(record["evidence_class"])
        entry["security_ids"].update(record.get("security_ids", []))
        entry["paths"].add(record["source"]["path"])

    missing = permitted - set(catalog)
    if missing:
        raise AssertionError("H1_FROZEN_FAMILY_NOT_IN_PHASE3A_REGISTRY:" + ",".join(sorted(missing)))

    out: dict[str, dict[str, Any]] = {}
    for family, entry in sorted(catalog.items()):
        out[family] = {
            "family_id": family,
            "evidence_classes": sorted(entry["evidence_classes"]),
            "security_ids": sorted(entry["security_ids"]),
            "paths": sorted(entry["paths"]),
        }
    return out


def _active_source_for_family(
    repo: Path,
    checkpoint_sha: str,
    family: Mapping[str, Any],
) -> dict[str, Any] | None:
    present: list[dict[str, Any]] = []
    for path in family["paths"]:
        blob_sha = _blob_at(repo, checkpoint_sha, path)
        if blob_sha is None:
            continue
        source_commit_sha = _last_change_commit(repo, checkpoint_sha, path)
        available_at = _commit_time(repo, source_commit_sha)
        present.append(
            {
                "path": path,
                "blob_sha": blob_sha,
                "source_commit_sha": source_commit_sha,
                "available_at": available_at,
            }
        )
    if not present:
        return None
    present.sort(
        key=lambda row: (
            _parse_time(row["available_at"]),
            row["source_commit_sha"],
            row["path"],
        )
    )
    return deepcopy(present[-1])


def build_source_snapshot(
    repo: Path,
    checkpoint_sha: str,
    *,
    family_catalog: Mapping[str, Mapping[str, Any]],
    opportunity_security_ids: list[str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    family_rows: list[dict[str, Any]] = []
    for family_id in sorted(family_catalog):
        family = family_catalog[family_id]
        active = _active_source_for_family(repo, checkpoint_sha, family)
        if active is None:
            continue
        family_rows.append(
            {
                "family_id": family_id,
                "evidence_classes": list(family["evidence_classes"]),
                "security_ids": list(family["security_ids"]),
                "active_source": active,
            }
        )

    family_ids = [row["family_id"] for row in family_rows]
    research_families = set(
        contract["frozen_evidence_families"]["research_or_decision_families"]
    )
    research_count = sum(family_id in research_families for family_id in family_ids)
    candidate_present = "CANDIDATE_STATE" in family_ids

    source_identity_payload = [
        {
            "family_id": row["family_id"],
            "path": row["active_source"]["path"],
            "blob_sha": row["active_source"]["blob_sha"],
            "source_commit_sha": row["active_source"]["source_commit_sha"],
        }
        for row in family_rows
    ]
    source_identity_set_sha256 = _sha256(source_identity_payload)
    fingerprint_payload = {
        "source_identities": source_identity_payload,
        "opportunity_security_ids": sorted(opportunity_security_ids),
    }
    decision_evidence_fingerprint_sha256 = _sha256(fingerprint_payload)
    evidence_regime_family_ids = sorted(family_ids)
    evidence_regime_signature = _sha256(evidence_regime_family_ids)

    return {
        "family_rows": family_rows,
        "family_ids": family_ids,
        "candidate_state_present": candidate_present,
        "research_or_decision_family_count": research_count,
        "source_identity_set_sha256": source_identity_set_sha256,
        "decision_evidence_fingerprint_sha256": decision_evidence_fingerprint_sha256,
        "evidence_regime_family_ids": evidence_regime_family_ids,
        "evidence_regime_signature": evidence_regime_signature,
    }


def _universe_commits(repo: Path, start_sha: str, end_sha: str) -> list[str]:
    parent = _git(repo, "rev-parse", f"{start_sha}^")
    raw = _git(
        repo,
        "rev-list",
        "--ancestry-path",
        f"{parent}..{end_sha}",
    )
    commits = [line for line in raw.splitlines() if line]
    if start_sha not in commits or end_sha not in commits:
        raise AssertionError("H1_FROZEN_UNIVERSE_ENDPOINT_MISSING")
    commits.sort(key=lambda sha: (_parse_time(_commit_time(repo, sha)), sha))
    return commits


def _evaluate_sufficiency(
    checkpoints: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    q = contract["quantitative_sufficiency_gate"]
    dates = Counter(row["utc_date"] for row in checkpoints)
    weeks = Counter(row["iso_week"] for row in checkpoints)
    regimes = Counter(row["evidence_regime_signature"] for row in checkpoints)
    securities = sorted(
        {
            security_id
            for row in checkpoints
            for security_id in row["opportunity_security_ids"]
        }
    )
    profile_instances = sum(len(row["opportunity_security_ids"]) for row in checkpoints)
    seed_first = _parse_time(contract["seed_firewall"]["seed_first_at"])
    seed_last = _parse_time(contract["seed_firewall"]["seed_last_at"])
    outside = sum(
        _parse_time(row["at"]) < seed_first or _parse_time(row["at"]) > seed_last
        for row in checkpoints
    )
    total = len(checkpoints)
    max_date_fraction = max(dates.values(), default=0) / total if total else 0.0
    max_regime_fraction = max(regimes.values(), default=0) / total if total else 0.0

    observed = {
        "holdout_checkpoints": total,
        "distinct_utc_dates": len(dates),
        "distinct_iso_weeks": len(weeks),
        "distinct_evidence_regime_signatures": len(regimes),
        "unique_securities": len(securities),
        "opportunity_profile_instances": profile_instances,
        "checkpoints_strictly_outside_seed_time_span": outside,
        "maximum_single_utc_date_fraction": max_date_fraction,
        "maximum_single_evidence_regime_fraction": max_regime_fraction,
    }
    checks = {
        "minimum_holdout_checkpoints": total >= q["minimum_holdout_checkpoints"],
        "minimum_distinct_utc_dates": len(dates) >= q["minimum_distinct_utc_dates"],
        "minimum_distinct_iso_weeks": len(weeks) >= q["minimum_distinct_iso_weeks"],
        "minimum_distinct_evidence_regime_signatures": (
            len(regimes) >= q["minimum_distinct_evidence_regime_signatures"]
        ),
        "minimum_unique_securities": len(securities) >= q["minimum_unique_securities"],
        "minimum_opportunity_profile_instances": (
            profile_instances >= q["minimum_opportunity_profile_instances"]
        ),
        "minimum_checkpoints_strictly_outside_seed_time_span": (
            outside >= q["minimum_checkpoints_strictly_outside_seed_time_span"]
        ),
        "maximum_single_utc_date_fraction": (
            max_date_fraction <= q["maximum_single_utc_date_fraction"]
        ),
        "maximum_single_evidence_regime_fraction": (
            max_regime_fraction <= q["maximum_single_evidence_regime_fraction"]
        ),
    }
    return {
        "observed": observed,
        "checks": checks,
        "all_thresholds_passed": all(checks.values()),
        "date_counts": dict(sorted(dates.items())),
        "iso_week_counts": dict(sorted(weeks.items())),
        "evidence_regime_counts": dict(sorted(regimes.items())),
        "unique_security_ids": securities,
    }


def build_holdout_h1_ledger(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT.parent
    contract = _load_json(CONTRACT_FILE)
    registry = _load_json(REGISTRY_FILE)

    if contract["status"] != "FROZEN_BEFORE_HOLDOUT_SELECTION_OR_R2_REPLAY_WITH_PRESELECTION_FEASIBILITY_CORRECTION":
        raise AssertionError("H1_REQUIRES_ACCEPTED_H0_1_CONTRACT")
    if contract["outcome_and_model_firewall"]["r2_pareto_replay_may_run_during_selection"] is not False:
        raise AssertionError("H1_R2_FIREWALL_OPEN")
    if contract["outcome_and_model_firewall"]["realized_outcomes_may_be_read_during_selection"] is not False:
        raise AssertionError("H1_OUTCOME_FIREWALL_OPEN")

    start_sha = contract["frozen_repository_universe"]["start_commit_inclusive"]
    end_sha = contract["frozen_repository_universe"]["end_commit_inclusive"]
    family_catalog = build_family_catalog(registry, contract)
    opportunity_security_ids = sorted(registry["scope_security_ids"])
    if not opportunity_security_ids:
        raise AssertionError("H1_EMPTY_PHASE3A_SCOPE_SECURITY_IDS")

    seed_commits = set(contract["seed_firewall"]["excluded_commit_shas"])
    seed_source_identity_sets: set[str] = set()
    for seed_sha in sorted(seed_commits):
        seed_snapshot = build_source_snapshot(
            repo,
            seed_sha,
            family_catalog=family_catalog,
            opportunity_security_ids=opportunity_security_ids,
            contract=contract,
        )
        seed_source_identity_sets.add(seed_snapshot["source_identity_set_sha256"])

    commits = _universe_commits(repo, start_sha, end_sha)
    selected: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    previous_main_fingerprint: str | None = None
    previous_selected_fingerprint: str | None = None

    for sha in commits:
        at = _commit_time(repo, sha)
        parsed = _parse_time(at)
        snapshot = build_source_snapshot(
            repo,
            sha,
            family_catalog=family_catalog,
            opportunity_security_ids=opportunity_security_ids,
            contract=contract,
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
            >= contract["deterministic_selector"]["minimum_research_or_decision_family_count"]
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
                "HOLDOUT_CP_"
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
                    "checkpoint_type": "INDEPENDENT_HOLDOUT_PIT_CHECKPOINT",
                    "opportunity_scope_policy": "PHASE3A_REGISTRY_SCOPE_SECURITY_IDS_FIXED",
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

        previous_main_fingerprint = fingerprint

    sufficiency = _evaluate_sufficiency(selected, contract)
    status = (
        "PASS_SELECTION_SUFFICIENCY"
        if sufficiency["all_thresholds_passed"]
        else "FAIL_SELECTION_SUFFICIENCY"
    )
    exclusion_counts = Counter(
        row["exclusion_reason"] or "SELECTED" for row in audit_rows
    )

    result = {
        "schema_version": "1.0.0",
        "phase": "PHASE_3_R2_INDEPENDENT_POINT_IN_TIME_HOLDOUT",
        "subphase": "H1_HOLDOUT_CANDIDATE_LEDGER_BUILD_AND_SELECTION_ACCEPTANCE",
        "status": status,
        "holdout_id": contract["holdout_identity"]["holdout_id"],
        "selector_mode": contract["deterministic_selector"]["mode"],
        "model_form_frozen_but_not_executed": contract["model_form"],
        "model_version_frozen_but_not_executed": contract["model_version"],
        "frozen_universe": {
            "start_commit_inclusive": start_sha,
            "end_commit_inclusive": end_sha,
            "commit_count": len(commits),
        },
        "phase3a_scope_security_ids": opportunity_security_ids,
        "seed_exclusion_count": len(seed_commits),
        "family_catalog": family_catalog,
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


def write_default(result: Mapping[str, Any], path: str | Path = OUTPUT_FILE) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    result = build_holdout_h1_ledger()
    target = write_default(result)
    observed = result["sufficiency"]["observed"]
    print(
        "PHASE3_R2_HOLDOUT_H1_LEDGER_BUILT "
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
