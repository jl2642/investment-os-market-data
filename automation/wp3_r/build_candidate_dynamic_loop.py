#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

CANDIDATE_PATH = Path("investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
LEDGER_PATH = Path("investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_DYNAMIC_LEDGER_CURRENT.json")
PROPOSAL_PATH = Path("investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_CHANGE_PROPOSAL_CURRENT.json")
LOOP_PATH = Path("investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_DYNAMIC_LOOP_CURRENT.json")
EVIDENCE_ROOT = Path("investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_R/DYNAMIC_PROPOSALS")
SCREENING_MANIFEST = Path("outputs/screens/current/SCREENING_MANIFEST.json")
SCREENING_LONGLIST = Path("outputs/screens/current/SCREENING_LONGLIST.csv")
ROUTE_FIELDS = (
    "candidate_core_members",
    "shadow_track_members",
    "research_queue_members",
    "ready_for_user_decision_members",
)
PROTECTED_ROUTE_FIELDS = (
    "candidate_core_members",
    "shadow_track_members",
    "ready_for_user_decision_members",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_longlist(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("SCREENING_LONGLIST_EMPTY")
    required = {
        "as_of_date",
        "overall_rank",
        "research_priority",
        "symbol",
        "name",
        "primary_sleeve",
        "investability_status",
        "factor_record_quality",
        "confidence_grade",
        "aggregate_score",
        "longlist_row_hash",
    }
    missing = sorted(required - set(rows[0]))
    if missing:
        raise SystemExit("SCREENING_LONGLIST_SCHEMA_MISSING:" + ",".join(missing))
    return rows


def membership_index(candidate: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in ROUTE_FIELDS:
        rows = candidate.get(field, [])
        if not isinstance(rows, list):
            raise SystemExit(f"CANDIDATE_ROUTE_NOT_LIST:{field}")
        for row in rows:
            security_id = str(row.get("security_id", "")).strip()
            if not security_id:
                raise SystemExit(f"CANDIDATE_MEMBER_MISSING_SECURITY_ID:{field}")
            if security_id in result:
                raise SystemExit(f"DUPLICATE_CANDIDATE_MEMBERSHIP:{security_id}")
            result[security_id] = field
    return result


def screening_date(rows: list[dict[str, str]], manifest: dict[str, Any]) -> date:
    dates = {str(row["as_of_date"]) for row in rows}
    if len(dates) != 1:
        raise SystemExit("LONGLIST_MULTIPLE_AS_OF_DATES")
    value = next(iter(dates))
    manifest_value = str(manifest.get("as_of_date") or manifest.get("accepted_session") or "")
    if manifest_value and manifest_value != value:
        raise SystemExit(f"SCREENING_DATE_MISMATCH:{manifest_value}:{value}")
    return date.fromisoformat(value)


def is_weekly_due(as_of: date, force_weekly: bool) -> bool:
    return force_weekly or as_of.weekday() == 4


def _prior_ledger_map(prior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = prior.get("rows", []) if isinstance(prior, dict) else []
    return {str(row["security_id"]): deepcopy(row) for row in rows if row.get("security_id")}


def update_ledger(
    prior: dict[str, Any],
    longlist: list[dict[str, str]],
    candidate: dict[str, Any],
    as_of: date,
    manifest_hash: str,
) -> dict[str, Any]:
    prior_map = _prior_ledger_map(prior)
    current_routes = membership_index(candidate)
    longlist_map = {row["symbol"]: row for row in longlist}
    same_session = prior.get("last_processed_as_of_date") == as_of.isoformat()
    security_ids = sorted(set(prior_map) | set(longlist_map) | set(current_routes))
    rows: list[dict[str, Any]] = []
    for security_id in security_ids:
        old = prior_map.get(security_id, {})
        screen = longlist_map.get(security_id)
        if same_session:
            appearance = int(old.get("appearance_streak", 0))
            absence = int(old.get("absence_streak", 0))
        elif screen is not None:
            appearance = int(old.get("appearance_streak", 0)) + 1
            absence = 0
        else:
            appearance = 0
            absence = int(old.get("absence_streak", 0)) + 1 if security_id in current_routes else 0
        rows.append(
            {
                "security_id": security_id,
                "security_name": (screen or old).get("name") or old.get("security_name"),
                "current_candidate_route": current_routes.get(security_id),
                "in_current_candidate": security_id in current_routes,
                "in_current_longlist": screen is not None,
                "appearance_streak": appearance,
                "absence_streak": absence,
                "last_seen_as_of_date": as_of.isoformat() if screen is not None else old.get("last_seen_as_of_date"),
                "overall_rank": int(screen["overall_rank"]) if screen is not None else old.get("overall_rank"),
                "research_priority": screen.get("research_priority") if screen is not None else old.get("research_priority"),
                "primary_sleeve": screen.get("primary_sleeve") if screen is not None else old.get("primary_sleeve"),
                "aggregate_score": float(screen["aggregate_score"]) if screen is not None else old.get("aggregate_score"),
                "confidence_grade": screen.get("confidence_grade") if screen is not None else old.get("confidence_grade"),
                "factor_record_quality": screen.get("factor_record_quality") if screen is not None else old.get("factor_record_quality"),
                "investability_status": screen.get("investability_status") if screen is not None else old.get("investability_status"),
                "longlist_row_hash": screen.get("longlist_row_hash") if screen is not None else old.get("longlist_row_hash"),
            }
        )
    cycle_dates = list(prior.get("completed_weekly_cycle_dates", []))
    if not same_session and as_of.isoformat() not in cycle_dates:
        cycle_dates.append(as_of.isoformat())
    cycle_dates = sorted(cycle_dates)[-12:]
    return {
        "state_id": "ROUND2_CANDIDATE_DYNAMIC_LEDGER_CURRENT",
        "schema_version": "1.0.0",
        "last_processed_as_of_date": as_of.isoformat(),
        "screening_manifest_sha256": manifest_hash,
        "completed_weekly_cycle_dates": cycle_dates,
        "completed_weekly_cycle_count": len(cycle_dates),
        "rows": rows,
        "candidate_membership_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def eligible_for_admission(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    screening = policy["screening"]
    hysteresis = policy["hysteresis"]
    return (
        not row["in_current_candidate"]
        and row["in_current_longlist"]
        and int(row["overall_rank"]) <= int(screening["admission_rank_ceiling"])
        and row["research_priority"] in screening["allowed_research_priorities"]
        and row["investability_status"] in screening["allowed_investability_statuses"]
        and row["factor_record_quality"] in screening["allowed_factor_record_quality"]
        and row["confidence_grade"] in screening["allowed_confidence_grades"]
        and int(row["appearance_streak"]) >= int(hysteresis["minimum_consecutive_longlist_appearances"])
    )


def select_admissions(
    ledger: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    capacity = policy["capacity"]
    queue_size = len(candidate["research_queue_members"])
    available = max(0, int(capacity["maximum_research_queue_size"]) - queue_size)
    limit = min(int(capacity["maximum_weekly_admissions"]), available)
    candidates = sorted(
        (row for row in ledger["rows"] if eligible_for_admission(row, policy)),
        key=lambda row: (int(row["overall_rank"]), row["security_id"]),
    )
    selected: list[dict[str, Any]] = []
    sleeve_counts: Counter[str] = Counter()
    per_sleeve = int(capacity["maximum_admissions_per_primary_sleeve"])
    for row in candidates:
        sleeve = str(row.get("primary_sleeve") or "UNCLASSIFIED")
        if sleeve_counts[sleeve] >= per_sleeve:
            continue
        selected.append(row)
        sleeve_counts[sleeve] += 1
        if len(selected) >= limit:
            break
    return selected


def select_dynamic_exits(
    ledger: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    capacity = policy["capacity"]
    hysteresis = policy["hysteresis"]
    queue = {row["security_id"]: row for row in candidate["research_queue_members"]}
    dynamic: list[dict[str, Any]] = []
    legacy_review: list[dict[str, Any]] = []
    for row in ledger["rows"]:
        if row.get("current_candidate_route") != "research_queue_members":
            continue
        member = queue[row["security_id"]]
        absence = int(row.get("absence_streak", 0))
        if member.get("dynamic_candidate_source") == "FULL_MARKET_SCREEN":
            if absence >= int(hysteresis["dynamic_exit_absence_streak"]):
                dynamic.append(row)
        elif absence >= int(hysteresis["legacy_exit_review_absence_streak"]):
            legacy_review.append(row)
    max_exits = int(capacity["maximum_weekly_dynamic_exits"])
    minimum_size = int(capacity["minimum_research_queue_size"])
    removable = max(0, len(queue) - minimum_size)
    dynamic = sorted(dynamic, key=lambda row: (-int(row["absence_streak"]), row["security_id"]))[: min(max_exits, removable)]
    legacy_review = sorted(legacy_review, key=lambda row: (-int(row["absence_streak"]), row["security_id"]))
    return dynamic, legacy_review


def new_research_queue_member(row: dict[str, Any], as_of: date, proposal_id: str) -> dict[str, Any]:
    security_id = row["security_id"]
    code = security_id.split(".", 1)[0]
    payload: dict[str, Any] = {
        "benchmark": None,
        "buy_signal": "NO",
        "candidate_state_change_requires_human_merge": True,
        "core20_review_disposition": None,
        "dynamic_admission_as_of": f"{as_of.isoformat()}_CLOSE",
        "dynamic_candidate_proposal_id": proposal_id,
        "dynamic_candidate_source": "FULL_MARKET_SCREEN",
        "entry_baseline_id": f"ROUND2-ENTRY-{security_id}",
        "entry_baseline_status": "MISSING",
        "historical_core20": False,
        "historical_lifecycle_state": "NONE",
        "portfolio_role": None,
        "proposed_candidate_route": "RESEARCH_QUEUE_DYNAMIC",
        "proposed_lifecycle_state": "NONE",
        "ready_for_user_decision": False,
        "real_account_permission": False,
        "research_decision_grade": False,
        "research_gap_count": 5,
        "research_id": f"ROUND2-RSCH-{security_id}",
        "research_lifecycle_state": "TRIAGE",
        "screening_aggregate_score": row.get("aggregate_score"),
        "screening_overall_rank": row.get("overall_rank"),
        "security_code": code,
        "security_id": security_id,
        "security_name": row.get("security_name"),
        "simulation_admission_permission": False,
        "strategy_sleeve": row.get("primary_sleeve"),
        "thesis_id": f"ROUND2-TH-{security_id}",
        "thesis_status": "MISSING_RESEARCH_REQUIRED",
        "trade_authority": "NONE",
        "valuation_id": f"ROUND2-VAL-{security_id}",
        "valuation_status": "DRAFT",
        "workplan_lane": "B_STRUCTURED_RESEARCH",
    }
    payload["semantic_hash"] = canonical_hash(payload)
    return payload


def apply_research_queue_delta(
    candidate: dict[str, Any],
    admissions: list[dict[str, Any]],
    dynamic_exits: list[dict[str, Any]],
    as_of: date,
    proposal_id: str,
    completed_cycles: int,
    acceptance_cycles: int,
) -> dict[str, Any]:
    updated = deepcopy(candidate)
    for field in PROTECTED_ROUTE_FIELDS:
        if field not in updated:
            raise SystemExit(f"PROTECTED_CANDIDATE_ROUTE_MISSING:{field}")
    exit_ids = {row["security_id"] for row in dynamic_exits}
    queue_before = list(updated.get("research_queue_members", []))
    removed = [row for row in queue_before if row["security_id"] in exit_ids]
    queue = [row for row in queue_before if row["security_id"] not in exit_ids]
    queue.extend(new_research_queue_member(row, as_of, proposal_id) for row in admissions)
    queue.sort(key=lambda row: row["security_id"])
    updated["research_queue_members"] = queue
    archive = list(updated.get("dynamic_research_queue_archive", []))
    for row in removed:
        archived = deepcopy(row)
        archived["dynamic_exit_as_of"] = f"{as_of.isoformat()}_CLOSE"
        archived["dynamic_exit_proposal_id"] = proposal_id
        archive.append(archived)
    if archive:
        updated["dynamic_research_queue_archive"] = archive
    counts = deepcopy(updated.get("counts", {}))
    counts["candidate_core"] = len(updated["candidate_core_members"])
    counts["shadow_track"] = len(updated["shadow_track_members"])
    counts["research_queue"] = len(updated["research_queue_members"])
    counts["ready_for_user_decision"] = len(updated["ready_for_user_decision_members"])
    updated["counts"] = counts
    accepted = completed_cycles >= acceptance_cycles
    updated["continuous_candidate_engine_complete"] = accepted
    updated["current_operating_stage"] = (
        "ROUND2_DYNAMIC_RESEARCH_QUEUE_ACTIVE_CORE_READY_GOVERNED"
        if accepted
        else "ROUND2_DYNAMIC_CANDIDATE_OPERATING_OBSERVATION"
    )
    updated["dynamic_candidate_loop"] = {
        "proposal_id": proposal_id,
        "as_of": f"{as_of.isoformat()}_CLOSE",
        "completed_weekly_cycle_count": completed_cycles,
        "admissions": [row["security_id"] for row in admissions],
        "dynamic_exits": [row["security_id"] for row in dynamic_exits],
        "legacy_exit_reviews_are_proposal_only": True,
        "core_shadow_ready_automatic_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "canonical_authority": "MERGE_OF_GOVERNED_PR_ONLY",
    }
    hash_input = deepcopy(updated)
    hash_input.pop("semantic_hash", None)
    updated["semantic_hash"] = canonical_hash(hash_input)
    return updated


def assert_protected_routes_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    for field in PROTECTED_ROUTE_FIELDS:
        if before.get(field) != after.get(field):
            raise SystemExit(f"FORBIDDEN_AUTOMATIC_ROUTE_MUTATION:{field}")


def build_proposal(
    ledger: dict[str, Any],
    candidate_before: dict[str, Any],
    candidate_after: dict[str, Any],
    admissions: list[dict[str, Any]],
    dynamic_exits: list[dict[str, Any]],
    legacy_exit_reviews: list[dict[str, Any]],
    policy: dict[str, Any],
    as_of: date,
    proposal_id: str,
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    promotion_ceiling = int(policy["screening"]["promotion_review_rank_ceiling"])
    promotion_reviews = [
        row
        for row in ledger["rows"]
        if row.get("current_candidate_route") == "research_queue_members"
        and row.get("in_current_longlist")
        and int(row.get("overall_rank") or 999999) <= promotion_ceiling
    ]
    return {
        "proposal_id": proposal_id,
        "schema_version": "1.0.0",
        "as_of": f"{as_of.isoformat()}_CLOSE",
        "status": "GOVERNED_CANDIDATE_DELTA_PROPOSED",
        "source_hashes": source_hashes,
        "candidate_counts_before": candidate_before.get("counts"),
        "candidate_counts_after": candidate_after.get("counts"),
        "admission_proposals": [
            {
                "action": "ADMIT_RESEARCH_QUEUE",
                "security_id": row["security_id"],
                "security_name": row.get("security_name"),
                "overall_rank": row.get("overall_rank"),
                "appearance_streak": row.get("appearance_streak"),
                "primary_sleeve": row.get("primary_sleeve"),
                "aggregate_score": row.get("aggregate_score"),
            }
            for row in admissions
        ],
        "dynamic_exit_proposals": [
            {
                "action": "REMOVE_DYNAMIC_RESEARCH_QUEUE",
                "security_id": row["security_id"],
                "security_name": row.get("security_name"),
                "absence_streak": row.get("absence_streak"),
            }
            for row in dynamic_exits
        ],
        "legacy_exit_reviews": [
            {
                "action": "EXIT_REVIEW_LEGACY_RESEARCH_QUEUE",
                "security_id": row["security_id"],
                "security_name": row.get("security_name"),
                "absence_streak": row.get("absence_streak"),
                "automatic_mutation": False,
            }
            for row in legacy_exit_reviews
        ],
        "promotion_reviews": [
            {
                "action": "SHADOW_PROMOTION_REVIEW_ONLY",
                "security_id": row["security_id"],
                "security_name": row.get("security_name"),
                "overall_rank": row.get("overall_rank"),
                "automatic_mutation": False,
            }
            for row in promotion_reviews
        ],
        "controls": {
            "candidate_core_mutations": 0,
            "shadow_track_mutations": 0,
            "ready_for_user_decision_mutations": 0,
            "legacy_research_queue_automatic_exits": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "decision_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
            "canonical_authority": "MERGE_OF_GOVERNED_PR_ONLY",
        },
    }


def run(root: Path, policy_path: Path, force_weekly: bool = False) -> dict[str, Any]:
    policy = read_json(root / policy_path)
    manifest = read_json(root / SCREENING_MANIFEST)
    longlist = load_longlist(root / SCREENING_LONGLIST)
    candidate_before = read_json(root / CANDIDATE_PATH)
    as_of = screening_date(longlist, manifest)
    if not is_weekly_due(as_of, force_weekly):
        return {
            "status": "NOOP_NOT_WEEKLY_CADENCE",
            "as_of": as_of.isoformat(),
            "due": False,
            "orders": 0,
            "trade_authority": "NONE",
        }
    prior = read_json(root / LEDGER_PATH) if (root / LEDGER_PATH).exists() else {}
    source_hashes = {
        "screening_manifest_sha256": file_hash(root / SCREENING_MANIFEST),
        "screening_longlist_sha256": file_hash(root / SCREENING_LONGLIST),
        "candidate_current_before_sha256": file_hash(root / CANDIDATE_PATH),
        "policy_sha256": file_hash(root / policy_path),
    }
    ledger = update_ledger(prior, longlist, candidate_before, as_of, source_hashes["screening_manifest_sha256"])
    admissions = select_admissions(ledger, candidate_before, policy)
    dynamic_exits, legacy_exit_reviews = select_dynamic_exits(ledger, candidate_before, policy)
    proposal_id = f"ROUND2_CANDIDATE_DELTA_{as_of.strftime('%Y%m%d')}"
    candidate_after = apply_research_queue_delta(
        candidate_before,
        admissions,
        dynamic_exits,
        as_of,
        proposal_id,
        int(ledger["completed_weekly_cycle_count"]),
        int(policy["hysteresis"]["completed_weekly_cycles_for_production_acceptance"]),
    )
    assert_protected_routes_unchanged(candidate_before, candidate_after)
    proposal = build_proposal(
        ledger,
        candidate_before,
        candidate_after,
        admissions,
        dynamic_exits,
        legacy_exit_reviews,
        policy,
        as_of,
        proposal_id,
        source_hashes,
    )
    loop = {
        "state_id": "ROUND2_CANDIDATE_DYNAMIC_LOOP_CURRENT",
        "schema_version": "1.0.0",
        "proposal_id": proposal_id,
        "as_of": f"{as_of.isoformat()}_CLOSE",
        "status": (
            "ROUND2_PRODUCTION_ACCEPTED"
            if candidate_after["continuous_candidate_engine_complete"]
            else "ROUND2_OPERATING_OBSERVATION"
        ),
        "completed_weekly_cycle_count": ledger["completed_weekly_cycle_count"],
        "admission_count": len(admissions),
        "dynamic_exit_count": len(dynamic_exits),
        "legacy_exit_review_count": len(legacy_exit_reviews),
        "candidate_current_changed": candidate_before != candidate_after,
        "candidate_core_mutations": 0,
        "shadow_track_mutations": 0,
        "ready_for_user_decision_mutations": 0,
        "portfolio_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "canonical_authority": "MERGE_OF_GOVERNED_PR_ONLY",
    }
    write_json(root / LEDGER_PATH, ledger)
    write_json(root / PROPOSAL_PATH, proposal)
    write_json(root / LOOP_PATH, loop)
    write_json(root / CANDIDATE_PATH, candidate_after)
    evidence_dir = root / EVIDENCE_ROOT / proposal_id
    write_json(evidence_dir / "CANDIDATE_CHANGE_PROPOSAL.json", proposal)
    write_json(evidence_dir / "CANDIDATE_DYNAMIC_LEDGER_SNAPSHOT.json", ledger)
    write_json(
        evidence_dir / "CANDIDATE_DYNAMIC_MANIFEST.json",
        {
            "proposal_id": proposal_id,
            "as_of": f"{as_of.isoformat()}_CLOSE",
            "source_hashes": source_hashes,
            "candidate_current_after_sha256": file_hash(root / CANDIDATE_PATH),
            "proposal_sha256": file_hash(root / PROPOSAL_PATH),
            "ledger_sha256": file_hash(root / LEDGER_PATH),
            "candidate_membership_scope": "RESEARCH_QUEUE_ONLY",
            "orders": 0,
            "trade_authority": "NONE",
        },
    )
    return {**loop, "due": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="automation/wp3_r/candidate_dynamic_policy.json")
    parser.add_argument("--force-weekly", action="store_true")
    args = parser.parse_args()
    result = run(Path(args.repo_root).resolve(), Path(args.policy), force_weekly=args.force_weekly)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
