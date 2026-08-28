from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SCREENING_MANIFEST = ROOT / "outputs/screens/current/SCREENING_MANIFEST.json"
SCREENING_REPORT = ROOT / "outputs/screens/current/FMDL2C_RUN_REPORT.json"
SCREENING_LONGLIST = ROOT / "outputs/screens/current/SCREENING_LONGLIST.csv"
FUNNEL_CONTRACT = ROOT / "investment_os_runtime/00_CONTROL/RESEARCH_FUNNEL_CONTRACT_CURRENT.json"
CANDIDATE_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
WEEKLY_SCREEN = ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/WEEKLY_PRICE_SCREEN_CURRENT.json"
DYNAMIC_LEDGER = ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_DYNAMIC_LEDGER_CURRENT.json"
CANDIDATE_REFRESH = ROOT / "investment_os_runtime/30_STATE_CURRENT/45_CANDIDATE_OPERATIONS/CANDIDATE_REFRESH_CURRENT.json"
D1_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D1_CURRENT.json"
D2_MAIN_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"

D1_CAPACITY = 5
D2_CAPACITY = 3
TRADE_AUTHORITY = "NONE"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_longlist(path: Path = SCREENING_LONGLIST) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_hash(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_identity_snapshot(
    *,
    screening_manifest: dict[str, Any],
    candidate: dict[str, Any],
    weekly: dict[str, Any],
    ledger: dict[str, Any],
    refresh: dict[str, Any],
    d1: dict[str, Any],
    d2: dict[str, Any],
    d2_domain: dict[str, Any] | None,
) -> dict[str, Any]:
    d2_domain = d2_domain or {}
    return {
        "FULL_MARKET_SCREEN": {
            "source_identity": screening_manifest.get("aggregate_sha256") or screening_manifest.get("run_id"),
            "source_watermark": screening_manifest.get("as_of_date"),
        },
        "CANDIDATE_CURRENT": {
            "source_identity": candidate.get("semantic_hash") or candidate.get("state_id"),
            "source_watermark": candidate.get("as_of"),
        },
        "CANDIDATE_WEEKLY_SCREEN": {
            "source_identity": canonical_hash({
                "as_of_date": weekly.get("as_of_date"),
                "covered_count": weekly.get("covered_count"),
                "rows": [
                    {
                        "security_id": row.get("security_id"),
                        "candidate_route": row.get("candidate_route"),
                        "price_as_of": row.get("price_as_of"),
                    }
                    for row in weekly.get("rows", [])
                ],
            }),
            "source_watermark": weekly.get("as_of_date"),
        },
        "CANDIDATE_DYNAMIC_LEDGER": {
            "source_identity": ledger.get("screening_manifest_sha256") or ledger.get("state_id"),
            "source_watermark": ledger.get("last_processed_as_of_date"),
        },
        "CANDIDATE_REFRESH": {
            "source_identity": refresh.get("state_id"),
            "source_watermark": refresh.get("as_of_date"),
        },
        "D1": {
            "source_identity": d1.get("state_id"),
            "source_watermark": d1.get("as_of"),
        },
        "D2": {
            "source_identity": d2_domain.get("source_commit_sha") or d2.get("state_id"),
            "source_watermark": d2_domain.get("data_watermark") or d2.get("as_of"),
            "operating_status": d2_domain.get("status") or d2.get("status"),
            "operating_qc_status": d2_domain.get("qc_status"),
        },
    }


def select_d1_work_queue(candidate: dict[str, Any], d1: dict[str, Any]) -> list[dict[str, Any]]:
    processed = set(d1.get("priority_order", []))
    research_queue = list(candidate.get("research_queue_members", []))
    lane_order = {"B_STRUCTURED_RESEARCH": 0, "C_WATCH_AND_EVIDENCE_FILL": 1}
    indexed = list(enumerate(research_queue))
    indexed.sort(key=lambda pair: (lane_order.get(str(pair[1].get("workplan_lane")), 99), pair[0]))
    selected: list[dict[str, Any]] = []
    for _, row in indexed:
        security_id = str(row.get("security_id") or "")
        if not security_id or security_id in processed:
            continue
        selected.append({
            "security_id": security_id,
            "security_name": row.get("security_name"),
            "workplan_lane": row.get("workplan_lane"),
            "strategy_sleeve": row.get("strategy_sleeve"),
            "research_gap_count": row.get("research_gap_count"),
            "work_status": "PENDING_SEMANTIC_D1_TRIAGE",
            "reason_code": "BOUNDED_ROTATION_NEXT_UNPROCESSED_RESEARCH_QUEUE_MEMBER",
            "next_trigger": "SEMANTIC_D1_TRIAGE_COMPLETION_OR_GOVERNED_D1_CURRENT_CHANGE",
        })
        if len(selected) == D1_CAPACITY:
            break
    return selected


def stage(
    stage_id: str,
    *,
    input_count: int,
    output_count: int,
    held_count: int,
    rejected_count: int,
    near_miss_count: int,
    reason_distribution: dict[str, int],
    source_watermark: Any,
    source_identity: Any,
    note: str | None = None,
) -> dict[str, Any]:
    result = {
        "stage_id": stage_id,
        "input_count": int(input_count),
        "output_count": int(output_count),
        "held_count": int(held_count),
        "rejected_count": int(rejected_count),
        "near_miss_count": int(near_miss_count),
        "reason_distribution": reason_distribution,
        "source_watermark": source_watermark,
        "source_identity": source_identity,
    }
    if note:
        result["note"] = note
    return result


def build_near_miss(
    *,
    longlist: list[dict[str, str]],
    candidate: dict[str, Any],
    weekly: dict[str, Any],
    d1: dict[str, Any],
    d2: dict[str, Any],
    d1_work_queue: list[dict[str, Any]],
    sources: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_routes: dict[str, str] = {}
    for row in weekly.get("rows", []):
        sid = str(row.get("security_id") or "")
        if sid:
            candidate_routes[sid] = str(row.get("candidate_route") or "")

    current_d1_ids = {str(x.get("security_id")) for x in d1.get("research_objects", [])}
    d1_work_ids = {str(x.get("security_id")) for x in d1_work_queue}
    d2_by_id = {str(x.get("security_id")): x for x in d2.get("queue", [])}
    rows: list[dict[str, Any]] = []

    for row in longlist:
        sid = str(row.get("symbol") or "")
        if not sid:
            continue
        route = candidate_routes.get(sid)
        if route:
            continue
        rows.append({
            "security_id": sid,
            "security_name": row.get("name"),
            "last_reached_stage": "RESEARCH_LONGLIST",
            "disposition": "NOT_IN_CURRENT_CANDIDATE_OPERATING_SET",
            "reason_code": "LONGLIST_NOT_IN_73_NAME_CANDIDATE_OPERATING_SET",
            "next_trigger": "NEXT_GOVERNED_CANDIDATE_REBUILD_OR_SCREENING_CYCLE",
            "source_watermarks": {
                "longlist": sources["FULL_MARKET_SCREEN"]["source_watermark"],
                "candidate_weekly": sources["CANDIDATE_WEEKLY_SCREEN"]["source_watermark"],
            },
        })

    for row in candidate.get("research_queue_members", []):
        sid = str(row.get("security_id") or "")
        if not sid or sid in current_d1_ids or sid in d1_work_ids:
            continue
        rows.append({
            "security_id": sid,
            "security_name": row.get("security_name"),
            "last_reached_stage": "RESEARCH_QUEUE",
            "disposition": "WAITING_BOUNDED_D1_CAPACITY",
            "reason_code": "D1_BATCH_CAPACITY_5_NOT_YET_SERVED",
            "next_trigger": "ENTER_D1_WORK_QUEUE_AFTER_GOVERNED_D1_CURRENT_ADVANCES",
            "source_watermarks": {
                "candidate": sources["CANDIDATE_CURRENT"]["source_watermark"],
                "candidate_weekly": sources["CANDIDATE_WEEKLY_SCREEN"]["source_watermark"],
                "d1": sources["D1"]["source_watermark"],
            },
        })

    for row in d1.get("research_objects", []):
        sid = str(row.get("security_id") or "")
        disposition = str(row.get("d1_disposition") or "")
        if disposition.startswith("ADVANCE_TO_D2"):
            continue
        rows.append({
            "security_id": sid,
            "security_name": row.get("security_name"),
            "last_reached_stage": "D1",
            "disposition": disposition or "HOLD_IN_D1",
            "reason_code": disposition or "D1_HOLD",
            "next_trigger": "REASSESS_ON_RELEVANT_EVIDENCE_OR_GOVERNED_D1_REFRESH",
            "source_watermarks": {
                "d1": sources["D1"]["source_watermark"],
                "candidate_weekly": sources["CANDIDATE_WEEKLY_SCREEN"]["source_watermark"],
            },
        })

    for sid, row in d2_by_id.items():
        status = str(row.get("status") or "")
        if status == "D2_RESEARCH_COMPLETE":
            disposition = str(row.get("research_disposition") or "")
            if disposition and "NO_DECISION" not in disposition:
                continue
            reason = "D2_RESEARCH_COMPLETE_NO_DECISION_PROMOTION"
        elif status == "D2_RESEARCH_HOLD_EVIDENCE_GAP":
            reason = "D2_EVIDENCE_GAP"
        else:
            reason = status or "D2_NOT_COMPLETE"
        rows.append({
            "security_id": sid,
            "security_name": row.get("security_name"),
            "last_reached_stage": "D2",
            "disposition": row.get("research_disposition") or status,
            "reason_code": reason,
            "next_trigger": row.get("next_gate") or "NEXT_D2_EVIDENCE_OR_RESEARCH_CYCLE",
            "source_watermarks": {
                "d1": sources["D1"]["source_watermark"],
                "d2": sources["D2"]["source_watermark"],
            },
        })

    rows.sort(key=lambda item: (item["last_reached_stage"], item["security_id"]))
    return rows


def build(
    *,
    d2_path: Path | None = None,
    d2_domain_path: Path | None = None,
    prior_current_path: Path | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat()

    contract = load_json(FUNNEL_CONTRACT)
    screening_manifest = load_json(SCREENING_MANIFEST)
    screening_report = load_json(SCREENING_REPORT)
    longlist = read_longlist()
    candidate = load_json(CANDIDATE_CURRENT)
    weekly = load_json(WEEKLY_SCREEN)
    ledger = load_json(DYNAMIC_LEDGER)
    refresh = load_json(CANDIDATE_REFRESH)
    d1 = load_json(D1_CURRENT)
    d2 = load_json(d2_path if d2_path and d2_path.exists() else D2_MAIN_CURRENT)
    d2_domain = load_json(d2_domain_path) if d2_domain_path and d2_domain_path.exists() else None

    metrics = screening_report.get("metrics", {})
    sources = source_identity_snapshot(
        screening_manifest=screening_manifest,
        candidate=candidate,
        weekly=weekly,
        ledger=ledger,
        refresh=refresh,
        d1=d1,
        d2=d2,
        d2_domain=d2_domain,
    )
    cycle_fingerprint = canonical_hash(sources)
    prior_current = (
        load_json(prior_current_path)
        if prior_current_path and prior_current_path.exists()
        else {}
    )
    prior_cycle_fingerprint = prior_current.get("cycle_fingerprint")
    source_cycle_changed = prior_cycle_fingerprint != cycle_fingerprint
    cycle_action = (
        "ADVANCE_NEW_SOURCE_FINGERPRINT"
        if source_cycle_changed
        else "NO_OP_SAME_SOURCE_FINGERPRINT"
    )

    d1_work_queue = select_d1_work_queue(candidate, d1)
    near_miss_rows = build_near_miss(
        longlist=longlist,
        candidate=candidate,
        weekly=weekly,
        d1=d1,
        d2=d2,
        d1_work_queue=d1_work_queue,
        sources=sources,
    )

    weekly_routes = Counter(str(row.get("candidate_route") or "UNKNOWN") for row in weekly.get("rows", []))
    candidate_core_count = len(candidate.get("candidate_core_members", []))
    research_queue_count = len(candidate.get("research_queue_members", []))
    shadow_count = len(candidate.get("shadow_track_members", []))
    ready_count = len(candidate.get("ready_for_user_decision_members", []))
    d1_advance = sum(1 for row in d1.get("research_objects", []) if str(row.get("d1_disposition", "")).startswith("ADVANCE_TO_D2"))
    d1_holds = len(d1.get("research_objects", [])) - d1_advance
    d2_summary = d2.get("summary", {})
    d2_completed = int(d2_summary.get("completed_count", 0))
    d2_hold_gap = int(d2_summary.get("hold_evidence_gap_count", 0))
    d2_pending = int(d2_summary.get("pending_count", 0))

    longlist_set = {str(row.get("symbol") or "") for row in longlist}
    weekly_set = {str(row.get("security_id") or "") for row in weekly.get("rows", [])}
    longlist_not_in_weekly = len([sid for sid in longlist_set if sid and sid not in weekly_set])

    stages = [
        stage(
            "UNIVERSE",
            input_count=int(metrics.get("universe_symbols", 0)),
            output_count=int(metrics.get("universe_symbols", 0)),
            held_count=0,
            rejected_count=0,
            near_miss_count=0,
            reason_distribution={"FULL_MARKET_ROWS": int(metrics.get("universe_symbols", 0))},
            source_watermark=sources["FULL_MARKET_SCREEN"]["source_watermark"],
            source_identity=sources["FULL_MARKET_SCREEN"]["source_identity"],
        ),
        stage(
            "ELIGIBILITY_AND_EXCLUSIONS",
            input_count=int(metrics.get("universe_symbols", 0)),
            output_count=int(metrics.get("core_investable", 0)),
            held_count=int(metrics.get("watch_eligible", 0)) + int(metrics.get("review_only", 0)),
            rejected_count=int(metrics.get("excluded", 0)),
            near_miss_count=int(metrics.get("watch_eligible", 0)) + int(metrics.get("review_only", 0)),
            reason_distribution={
                "ELIGIBLE_CORE": int(metrics.get("core_investable", 0)),
                "WATCH_ELIGIBLE": int(metrics.get("watch_eligible", 0)),
                "REVIEW_ONLY": int(metrics.get("review_only", 0)),
                "EXCLUDED": int(metrics.get("excluded", 0)),
            },
            source_watermark=sources["FULL_MARKET_SCREEN"]["source_watermark"],
            source_identity=sources["FULL_MARKET_SCREEN"]["source_identity"],
        ),
        stage(
            "MULTI_DIMENSIONAL_SCREEN",
            input_count=int(metrics.get("core_investable", 0)),
            output_count=int(metrics.get("distinct_sleeve_candidates", 0)),
            held_count=max(int(metrics.get("core_investable", 0)) - int(metrics.get("distinct_sleeve_candidates", 0)), 0),
            rejected_count=0,
            near_miss_count=max(int(metrics.get("core_investable", 0)) - int(metrics.get("distinct_sleeve_candidates", 0)), 0),
            reason_distribution={
                "DISTINCT_SLEEVE_CANDIDATES": int(metrics.get("distinct_sleeve_candidates", 0)),
                "RAW_SLEEVE_HITS": int(metrics.get("raw_sleeve_hits", 0)),
                "NO_SLEEVE_SELECTION": max(int(metrics.get("core_investable", 0)) - int(metrics.get("distinct_sleeve_candidates", 0)), 0),
            },
            source_watermark=sources["FULL_MARKET_SCREEN"]["source_watermark"],
            source_identity=sources["FULL_MARKET_SCREEN"]["source_identity"],
        ),
        stage(
            "RESEARCH_LONGLIST",
            input_count=int(metrics.get("distinct_sleeve_candidates", 0)),
            output_count=len(longlist),
            held_count=max(int(metrics.get("distinct_sleeve_candidates", 0)) - len(longlist), 0),
            rejected_count=0,
            near_miss_count=max(int(metrics.get("distinct_sleeve_candidates", 0)) - len(longlist), 0),
            reason_distribution={
                "LONGLIST_SELECTED": len(longlist),
                "OUTSIDE_TOP_100_RESEARCH_CAPACITY": max(int(metrics.get("distinct_sleeve_candidates", 0)) - len(longlist), 0),
            },
            source_watermark=sources["FULL_MARKET_SCREEN"]["source_watermark"],
            source_identity=sources["FULL_MARKET_SCREEN"]["source_identity"],
        ),
        stage(
            "RESEARCH_QUEUE",
            input_count=len(longlist),
            output_count=research_queue_count,
            held_count=max(len(longlist) - research_queue_count, 0),
            rejected_count=0,
            near_miss_count=max(len(longlist) - research_queue_count, 0),
            reason_distribution={
                "RESEARCH_QUEUE_MEMBERS": research_queue_count,
                "SHADOW_TRACK_CONTEXT": shadow_count,
                "CANDIDATE_CORE_CONTEXT": candidate_core_count,
                "LONGLIST_NOT_IN_CURRENT_73_NAME_OPERATING_SET": longlist_not_in_weekly,
            },
            source_watermark={
                "longlist": sources["FULL_MARKET_SCREEN"]["source_watermark"],
                "candidate": sources["CANDIDATE_CURRENT"]["source_watermark"],
                "weekly": sources["CANDIDATE_WEEKLY_SCREEN"]["source_watermark"],
            },
            source_identity={
                "candidate": sources["CANDIDATE_CURRENT"]["source_identity"],
                "weekly": sources["CANDIDATE_WEEKLY_SCREEN"]["source_identity"],
            },
            note="Counts bridge source-specific watermarks; no common as-of is synthesized.",
        ),
        stage(
            "D1",
            input_count=research_queue_count,
            output_count=len(d1_work_queue),
            held_count=max(research_queue_count - len(d1_work_queue), 0),
            rejected_count=0,
            near_miss_count=max(research_queue_count - len(d1_work_queue), 0),
            reason_distribution={
                "ACTIVE_BOUNDED_WORK_QUEUE": len(d1_work_queue),
                "PRIOR_D1_ADVANCED_TO_D2": d1_advance,
                "PRIOR_D1_HELD": d1_holds,
                "WAITING_BOUNDED_CAPACITY": max(research_queue_count - len(d1_work_queue) - len(d1.get("priority_order", [])), 0),
            },
            source_watermark={
                "candidate": sources["CANDIDATE_CURRENT"]["source_watermark"],
                "d1": sources["D1"]["source_watermark"],
            },
            source_identity={
                "candidate": sources["CANDIDATE_CURRENT"]["source_identity"],
                "d1": sources["D1"]["source_identity"],
            },
            note="Work queue is deterministic routing only. New names remain pending semantic D1 triage and are not auto-promoted to D2.",
        ),
        stage(
            "D2",
            input_count=d1_advance,
            output_count=d2_completed,
            held_count=d2_hold_gap + d2_pending,
            rejected_count=0,
            near_miss_count=d2_hold_gap + d2_pending,
            reason_distribution={
                "D2_RESEARCH_COMPLETE": d2_completed,
                "D2_HOLD_EVIDENCE_GAP": d2_hold_gap,
                "D2_PENDING": d2_pending,
            },
            source_watermark={
                "d1": sources["D1"]["source_watermark"],
                "d2": sources["D2"]["source_watermark"],
            },
            source_identity={
                "d1": sources["D1"]["source_identity"],
                "d2": sources["D2"]["source_identity"],
            },
        ),
        stage(
            "CANDIDATE_CORE_CONTEXT",
            input_count=candidate_core_count,
            output_count=candidate_core_count,
            held_count=0,
            rejected_count=0,
            near_miss_count=0,
            reason_distribution={"CONTEXT_ONLY_EXISTING_CANDIDATE_CORE": candidate_core_count},
            source_watermark=sources["CANDIDATE_CURRENT"]["source_watermark"],
            source_identity=sources["CANDIDATE_CURRENT"]["source_identity"],
            note="Context only; P4-2 performs no Candidate membership mutation.",
        ),
        stage(
            "READY_FOR_USER_DECISION_CONTEXT",
            input_count=candidate_core_count,
            output_count=ready_count,
            held_count=max(candidate_core_count - ready_count, 0),
            rejected_count=0,
            near_miss_count=max(candidate_core_count - ready_count, 0),
            reason_distribution={
                "READY_FOR_USER_DECISION": ready_count,
                "NO_CURRENT_READY_MEMBER": max(candidate_core_count - ready_count, 0),
            },
            source_watermark=sources["CANDIDATE_CURRENT"]["source_watermark"],
            source_identity=sources["CANDIDATE_CURRENT"]["source_identity"],
            note="Context only; Recommendation Engine is explicitly out of P4-2 scope.",
        ),
    ]

    d2_operating_status = str(sources["D2"].get("operating_status") or "")
    if not source_cycle_changed:
        overall_status = "NO_NEW_THROUGHPUT_EXPLICITLY_EXPLAINED"
    elif d2_operating_status == "BLOCKED":
        overall_status = "BLOCKED_SOURCE_GAP"
    else:
        watermarks = [str(v.get("source_watermark") or "") for v in sources.values()]
        overall_status = "PARTIAL_STALE_UPSTREAM" if len(set(watermarks)) > 1 else "CURRENT"

    near_reason_counts = Counter(row["reason_code"] for row in near_miss_rows)
    current = {
        "schema_version": "1.0.0",
        "surface_id": "P4_2_CONTINUOUS_OPPORTUNITY_FUNNEL",
        "generated_at_utc": generated_at,
        "overall_status": overall_status,
        "cycle_fingerprint": cycle_fingerprint,
        "prior_cycle_fingerprint": prior_cycle_fingerprint,
        "cycle_action": cycle_action,
        "source_snapshot": sources,
        "watermark_policy": {
            "synthetic_single_as_of_forbidden": True,
            "source_specific_watermarks_preserved": True,
            "relative_staleness_is_not_exchange_session_truth": True,
        },
        "stages": stages,
        "bounded_rotation": {
            "d1_batch_capacity": D1_CAPACITY,
            "d2_batch_capacity": D2_CAPACITY,
            "d1_selection_policy": "EXISTING_WORKPLAN_LANE_ORDER_B_THEN_C_PRESERVE_CANDIDATE_ORDER_EXCLUDE_ALREADY_SERVED_D1",
            "d1_work_queue": d1_work_queue,
            "automatic_d2_promotion_from_work_queue": False,
            "rotation_trigger": "GOVERNED_D1_CURRENT_CHANGE_OR_RESEARCH_QUEUE_MEMBERSHIP_CHANGE",
        },
        "near_miss_summary": {
            "count": len(near_miss_rows),
            "reason_distribution": dict(sorted(near_reason_counts.items())),
        },
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "user_decisions_generated": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "contract_binding": {
            "research_funnel_contract_id": contract.get("contract_id"),
            "p4_2_contract_pr": 342,
            "recommendation_engine_authorized": False,
            "forward_outcome_read_authorized": False,
        },
    }

    semantic_projection = dict(current)
    semantic_projection.pop("generated_at_utc", None)
    current["semantic_hash"] = canonical_hash(semantic_projection)

    near_miss = {
        "schema_version": "1.0.0",
        "surface_id": "P4_2_OPPORTUNITY_NEAR_MISS",
        "generated_at_utc": generated_at,
        "cycle_fingerprint": cycle_fingerprint,
        "rows": near_miss_rows,
        "controls": current["controls"],
    }
    work_queue = {
        "schema_version": "1.0.0",
        "surface_id": "P4_2_D1_BOUNDED_WORK_QUEUE",
        "generated_at_utc": generated_at,
        "cycle_fingerprint": cycle_fingerprint,
        "capacity": D1_CAPACITY,
        "queue": d1_work_queue,
        "served_d1_state_id": d1.get("state_id"),
        "served_d1_ids": list(d1.get("priority_order", [])),
        "automatic_candidate_membership_mutation": False,
        "automatic_d2_promotion": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    receipt = {
        "schema_version": "1.0.0",
        "cycle_fingerprint": cycle_fingerprint,
        "prior_cycle_fingerprint": prior_cycle_fingerprint,
        "cycle_action": cycle_action,
        "generated_at_utc": generated_at,
        "source_snapshot": sources,
        "semantic_hash": current["semantic_hash"],
        "overall_status": overall_status,
        "d1_work_queue_ids": [row["security_id"] for row in d1_work_queue],
        "near_miss_count": len(near_miss_rows),
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return current, near_miss, work_queue, receipt


def validate_payloads(
    current: dict[str, Any],
    near_miss: dict[str, Any],
    work_queue: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    required_stages = {
        "UNIVERSE",
        "ELIGIBILITY_AND_EXCLUSIONS",
        "MULTI_DIMENSIONAL_SCREEN",
        "RESEARCH_LONGLIST",
        "RESEARCH_QUEUE",
        "D1",
        "D2",
        "CANDIDATE_CORE_CONTEXT",
        "READY_FOR_USER_DECISION_CONTEXT",
    }
    present = {row.get("stage_id") for row in current.get("stages", [])}
    if present != required_stages:
        errors.append("P42_REQUIRED_STAGES_MISMATCH")
    for row in current.get("stages", []):
        for field in (
            "stage_id", "input_count", "output_count", "held_count", "rejected_count",
            "near_miss_count", "reason_distribution", "source_watermark", "source_identity",
        ):
            if field not in row:
                errors.append(f"P42_STAGE_FIELD_MISSING:{row.get('stage_id')}:{field}")
        if int(row.get("output_count", 0)) == 0 and not row.get("reason_distribution"):
            errors.append(f"P42_ZERO_OUTPUT_UNEXPLAINED:{row.get('stage_id')}")
    if len(work_queue.get("queue", [])) > D1_CAPACITY:
        errors.append("P42_D1_CAPACITY_EXCEEDED")
    d2_stage = next((x for x in current.get("stages", []) if x.get("stage_id") == "D2"), {})
    if int(d2_stage.get("input_count", 0)) > D2_CAPACITY:
        errors.append("P42_D2_CAPACITY_EXCEEDED")
    for row in near_miss.get("rows", []):
        for field in ("security_id", "last_reached_stage", "disposition", "reason_code", "next_trigger", "source_watermarks"):
            if field not in row:
                errors.append(f"P42_NEAR_MISS_FIELD_MISSING:{row.get('security_id')}:{field}")
    controls = current.get("controls", {})
    if any(int(controls.get(key, 0)) != 0 for key in (
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "orders",
    )):
        errors.append("P42_PROTECTED_STATE_MUTATION")
    if controls.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("P42_TRADE_AUTHORITY")
    if receipt.get("cycle_fingerprint") != current.get("cycle_fingerprint"):
        errors.append("P42_RECEIPT_FINGERPRINT_MISMATCH")
    if receipt.get("semantic_hash") != current.get("semantic_hash"):
        errors.append("P42_RECEIPT_SEMANTIC_HASH_MISMATCH")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d2-current")
    parser.add_argument("--d2-domain")
    parser.add_argument("--prior-current")
    parser.add_argument("--output-dir", default=".p4_2_output")
    parser.add_argument("--now")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    current, near_miss, work_queue, receipt = build(
        d2_path=Path(args.d2_current) if args.d2_current else None,
        d2_domain_path=Path(args.d2_domain) if args.d2_domain else None,
        prior_current_path=Path(args.prior_current) if args.prior_current else None,
        now=now,
    )
    errors = validate_payloads(current, near_miss, work_queue, receipt)
    if errors:
        raise SystemExit("\n".join(errors))

    output_dir = Path(args.output_dir)
    write_json(output_dir / "OPPORTUNITY_FUNNEL_CURRENT.json", current)
    write_json(output_dir / "OPPORTUNITY_NEAR_MISS_CURRENT.json", near_miss)
    write_json(output_dir / "D1_WORK_QUEUE_CURRENT.json", work_queue)
    write_json(output_dir / "cycle_receipt.json", receipt)

    print(json.dumps({
        "status": current["overall_status"],
        "cycle_fingerprint": current["cycle_fingerprint"],
        "semantic_hash": current["semantic_hash"],
        "cycle_action": current["cycle_action"],
        "d1_work_queue": [row["security_id"] for row in work_queue["queue"]],
        "near_miss_count": len(near_miss["rows"]),
        "protected_mutations": 0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
