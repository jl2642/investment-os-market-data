from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
ENTRY_STATES = {"BUY_NOW", "ADD"}
EXIT_STATES = {"AVOID", "EXIT_REVIEW"}
PRE_BASELINE_LABEL = "PRE_BASELINE_INFRASTRUCTURE_ONLY"


def load_json(path: Path | None, default: Any = None) -> Any:
    if path is None or not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")


def canonical_hash(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def market_from_record(row: dict[str, Any]) -> str:
    market = str(row.get("market") or "")
    if market:
        return market
    sid = str(row.get("security_id") or "").upper()
    if sid.endswith((".SZ", ".SH", ".BJ")):
        return "A_SHARE"
    if sid.endswith(".HK") or sid.startswith("HKEX:"):
        return "H_SHARE"
    return "US_SHARE"


def clause_id(security_id: str, clause_type: str, text: str) -> str:
    return canonical_hash(
        {"security_id": security_id, "clause_type": clause_type, "text": text}
    )


def make_registry(recommendation: dict[str, Any], published_at: str) -> dict[str, Any]:
    clauses = []
    transition_rules = []
    for row in sorted(recommendation.get("records", []), key=lambda x: x["security_id"]):
        sid = str(row["security_id"])
        for idx, text in enumerate(row.get("triggers", []), start=1):
            clauses.append(
                {
                    "clause_id": clause_id(sid, "RECOMMENDATION_TRIGGER", str(text)),
                    "security_id": sid,
                    "security_name": row.get("security_name"),
                    "market": market_from_record(row),
                    "clause_type": "RECOMMENDATION_TRIGGER",
                    "ordinal": idx,
                    "clause_text": str(text),
                    "monitorability": "SEMANTIC_EVIDENCE_REQUIRED",
                    "state": "ARMED_EVIDENCE_REQUIRED",
                    "governed_evidence_required_to_fire": True,
                    "keyword_inference_authorized": False,
                }
            )
        for idx, text in enumerate(row.get("invalidation_conditions", []), start=1):
            clauses.append(
                {
                    "clause_id": clause_id(sid, "INVALIDATION_CONDITION", str(text)),
                    "security_id": sid,
                    "security_name": row.get("security_name"),
                    "market": market_from_record(row),
                    "clause_type": "INVALIDATION_CONDITION",
                    "ordinal": idx,
                    "clause_text": str(text),
                    "monitorability": "SEMANTIC_EVIDENCE_REQUIRED",
                    "state": "ARMED_EVIDENCE_REQUIRED",
                    "governed_evidence_required_to_fire": True,
                    "keyword_inference_authorized": False,
                }
            )
        transition_rules.append(
            {
                "security_id": sid,
                "current_recommendation_state": row.get("recommendation_state"),
                "monitorability": "STATE_TRANSITION_MACHINE_EVALUABLE",
                "entry_action_states": sorted(ENTRY_STATES),
                "exit_action_states": sorted(EXIT_STATES),
            }
        )

    trigger_count = sum(x["clause_type"] == "RECOMMENDATION_TRIGGER" for x in clauses)
    invalidation_count = sum(x["clause_type"] == "INVALIDATION_CONDITION" for x in clauses)
    return {
        "schema_version": "1.0.0",
        "surface_id": "P4_4_TRIGGER_REGISTRY_CURRENT",
        "recommendation_fingerprint": recommendation["recommendation_fingerprint"],
        "recommendation_published_at": published_at,
        "subject_count": len(recommendation.get("records", [])),
        "trigger_clause_count": trigger_count,
        "invalidation_clause_count": invalidation_count,
        "clauses": clauses,
        "state_transition_rules": transition_rules,
        "natural_language_keyword_inference_authorized": False,
        "trade_authority": TRADE_AUTHORITY,
    }


def default_subject(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "security_id": row["security_id"],
        "security_name": row.get("security_name"),
        "market": market_from_record(row),
        "position_state": "FLAT",
        "normalized_research_units": 0.0,
        "entry": None,
        "exit": None,
        "pending_action": None,
        "last_recommendation_state": None,
        "last_recommendation_fingerprint": None,
        "last_recommendation_published_at": None,
        "benchmark_binding_status": "BENCHMARK_BINDING_REQUIRED_BEFORE_ATTRIBUTION",
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }


def append_once(rows: list[dict[str, Any]], row: dict[str, Any]) -> bool:
    event_id = row["event_id"]
    if any(x.get("event_id") == event_id for x in rows):
        return False
    rows.append(row)
    return True


def recommendation_event(
    *,
    row: dict[str, Any],
    fingerprint: str,
    published_at: str,
) -> dict[str, Any]:
    payload = {
        "event_type": "RECOMMENDATION_STATE_OBSERVED",
        "security_id": row["security_id"],
        "recommendation_state": row["recommendation_state"],
        "recommendation_fingerprint": fingerprint,
        "available_at": published_at,
    }
    return {
        "event_id": canonical_hash(payload),
        **payload,
        "evaluation_eligibility": PRE_BASELINE_LABEL,
        "phase4_forward_observation_increment": 0,
        "phase4_realized_outcome_increment": 0,
    }


def action_signal_event(
    *,
    event_type: str,
    security_id: str,
    recommendation_event_id: str,
    recommendation_state: str,
    signal_available_at: str,
) -> dict[str, Any]:
    payload = {
        "event_type": event_type,
        "security_id": security_id,
        "recommendation_event_id": recommendation_event_id,
        "recommendation_state": recommendation_state,
        "signal_available_at": signal_available_at,
    }
    return {
        "event_id": canonical_hash(payload),
        **payload,
        "action_id": canonical_hash(
            {
                "security_id": security_id,
                "recommendation_event_id": recommendation_event_id,
                "event_type": event_type,
            }
        ),
        "normalized_research_units": 1.0,
        "capital_weight": None,
        "cash_consumed": 0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }


def cancel_event(
    *,
    action: dict[str, Any],
    reason: str,
    recommendation_event_id: str,
) -> dict[str, Any]:
    payload = {
        "event_type": reason,
        "security_id": action["security_id"],
        "action_id": action["action_id"],
        "recommendation_event_id": recommendation_event_id,
    }
    return {
        "event_id": canonical_hash(payload),
        **payload,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }


def eligible_mark(
    mark_packet: dict[str, Any],
    action: dict[str, Any],
) -> dict[str, Any] | None:
    signal_at = parse_ts(action["signal_available_at"])
    candidates = []
    for mark in mark_packet.get("marks", []):
        if str(mark.get("action_id")) != str(action["action_id"]):
            continue
        available_at = str(mark.get("available_at_utc") or "")
        if not available_at:
            continue
        if parse_ts(available_at) <= signal_at:
            continue
        if not mark.get("completed_session", False):
            continue
        candidates.append(mark)
    if not candidates:
        return None
    return min(candidates, key=lambda x: parse_ts(x["available_at_utc"]))


def fill_event(
    *,
    action: dict[str, Any],
    mark: dict[str, Any],
) -> dict[str, Any]:
    kind = "ENTRY_FILLED" if action["event_type"] == "ENTRY_SIGNAL" else "EXIT_FILLED"
    payload = {
        "event_type": kind,
        "security_id": action["security_id"],
        "action_id": action["action_id"],
        "mark_identity": mark["mark_identity"],
        "market_session": mark["market_session"],
        "available_at_utc": mark["available_at_utc"],
    }
    return {
        "event_id": canonical_hash(payload),
        **payload,
        "mark": mark["mark"],
        "provider": mark["provider"],
        "normalized_research_units": 1.0,
        "capital_weight": None,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }


def build(
    *,
    recommendation_path: Path,
    recommendation_domain_path: Path,
    prior_trigger_current_path: Path | None = None,
    prior_shadow_current_path: Path | None = None,
    prior_trigger_event_ledger_path: Path | None = None,
    prior_action_ledger_path: Path | None = None,
    mark_packet_path: Path | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat()

    rec = load_json(recommendation_path)
    rec_domain = load_json(recommendation_domain_path)
    prior_trigger = load_json(prior_trigger_current_path, {})
    prior_shadow = load_json(prior_shadow_current_path, {})
    trigger_events = load_jsonl(prior_trigger_event_ledger_path)
    action_ledger = load_jsonl(prior_action_ledger_path)
    mark_packet = load_json(
        mark_packet_path,
        {
            "packet_id": "EMPTY_NO_PENDING_ACTION",
            "status": "EMPTY_NO_PENDING_ACTION",
            "marks": [],
            "errors": [],
        },
    )

    fingerprint = str(rec["recommendation_fingerprint"])
    published_at = str(rec_domain["published_at_utc"])
    prior_published_at = prior_trigger.get("recommendation_published_at")
    prior_fingerprint = prior_trigger.get("recommendation_fingerprint")
    if (
        prior_published_at
        and prior_fingerprint != fingerprint
        and parse_ts(published_at) < parse_ts(str(prior_published_at))
    ):
        raise ValueError("P44_OUT_OF_ORDER_RECOMMENDATION_SOURCE")

    registry = make_registry(rec, published_at)
    prior_subjects = {
        str(x["security_id"]): deepcopy(x)
        for x in prior_shadow.get("subjects", [])
    }
    subjects = []
    action_signal_count_this_cycle = 0
    fill_count_this_cycle = 0
    cancel_count_this_cycle = 0

    for row in sorted(rec.get("records", []), key=lambda x: x["security_id"]):
        sid = str(row["security_id"])
        state = str(row["recommendation_state"])
        subject = prior_subjects.get(sid, default_subject(row))
        rec_event = recommendation_event(
            row=row,
            fingerprint=fingerprint,
            published_at=published_at,
        )
        append_once(trigger_events, rec_event)

        pending = subject.get("pending_action")
        if pending and pending.get("event_type") == "ENTRY_SIGNAL" and state not in ENTRY_STATES:
            ce = cancel_event(
                action=pending,
                reason="ENTRY_CANCELLED_BEFORE_MARK",
                recommendation_event_id=rec_event["event_id"],
            )
            if append_once(action_ledger, ce):
                cancel_count_this_cycle += 1
            subject["pending_action"] = None
            subject["position_state"] = "FLAT"
        elif pending and pending.get("event_type") == "EXIT_SIGNAL" and state not in EXIT_STATES:
            ce = cancel_event(
                action=pending,
                reason="EXIT_CANCELLED_BEFORE_MARK",
                recommendation_event_id=rec_event["event_id"],
            )
            if append_once(action_ledger, ce):
                cancel_count_this_cycle += 1
            subject["pending_action"] = None
            subject["position_state"] = "OPEN"

        if (
            state in ENTRY_STATES
            and subject["position_state"] in {"FLAT", "CLOSED"}
            and subject.get("pending_action") is None
        ):
            action = action_signal_event(
                event_type="ENTRY_SIGNAL",
                security_id=sid,
                recommendation_event_id=rec_event["event_id"],
                recommendation_state=state,
                signal_available_at=published_at,
            )
            if append_once(action_ledger, action):
                action_signal_count_this_cycle += 1
            subject["pending_action"] = action
            subject["position_state"] = "ENTRY_PENDING_MARK"

        if (
            state in EXIT_STATES
            and subject["position_state"] == "OPEN"
            and subject.get("pending_action") is None
        ):
            action = action_signal_event(
                event_type="EXIT_SIGNAL",
                security_id=sid,
                recommendation_event_id=rec_event["event_id"],
                recommendation_state=state,
                signal_available_at=published_at,
            )
            if append_once(action_ledger, action):
                action_signal_count_this_cycle += 1
            subject["pending_action"] = action
            subject["position_state"] = "EXIT_PENDING_MARK"

        pending = subject.get("pending_action")
        if pending:
            mark = eligible_mark(mark_packet, pending)
            if mark is not None:
                filled = fill_event(action=pending, mark=mark)
                if append_once(action_ledger, filled):
                    fill_count_this_cycle += 1
                if pending["event_type"] == "ENTRY_SIGNAL":
                    subject["position_state"] = "OPEN"
                    subject["normalized_research_units"] = 1.0
                    subject["entry"] = {
                        "action_id": pending["action_id"],
                        "signal_available_at": pending["signal_available_at"],
                        "fill_available_at": mark["available_at_utc"],
                        "market_session": mark["market_session"],
                        "mark": mark["mark"],
                        "mark_identity": mark["mark_identity"],
                        "provider": mark["provider"],
                    }
                    subject["exit"] = None
                else:
                    subject["position_state"] = "CLOSED"
                    subject["normalized_research_units"] = 0.0
                    subject["exit"] = {
                        "action_id": pending["action_id"],
                        "signal_available_at": pending["signal_available_at"],
                        "fill_available_at": mark["available_at_utc"],
                        "market_session": mark["market_session"],
                        "mark": mark["mark"],
                        "mark_identity": mark["mark_identity"],
                        "provider": mark["provider"],
                    }
                subject["pending_action"] = None

        subject["security_name"] = row.get("security_name")
        subject["market"] = market_from_record(row)
        subject["last_recommendation_state"] = state
        subject["last_recommendation_fingerprint"] = fingerprint
        subject["last_recommendation_published_at"] = published_at
        subject["evaluation_eligibility"] = PRE_BASELINE_LABEL
        subjects.append(subject)

    requests = []
    for subject in subjects:
        action = subject.get("pending_action")
        if not action:
            continue
        requests.append(
            {
                "action_id": action["action_id"],
                "action_kind": action["event_type"],
                "security_id": subject["security_id"],
                "security_name": subject.get("security_name"),
                "market": subject["market"],
                "signal_available_at": action["signal_available_at"],
                "required_mark_rule": "FIRST_COMPLETED_SESSION_MARK_STRICTLY_AVAILABLE_AFTER_SIGNAL",
                "adapter_status": "READY_A_SHARE_PUBLIC_KLINE"
                if subject["market"] == "A_SHARE"
                else "UNSUPPORTED_MARKET_ADAPTER_FAIL_CLOSED",
            }
        )

    source_snapshot = {
        "recommendation": {
            "identity": fingerprint,
            "published_at_utc": published_at,
            "source_commit_sha": rec_domain.get("source_commit_sha"),
        },
        "mark_packet": {
            "identity": mark_packet.get("packet_id", "EMPTY_NO_PENDING_ACTION"),
            "status": mark_packet.get("status"),
        },
    }
    source_fingerprint = canonical_hash(source_snapshot)
    prior_source_fingerprint = prior_trigger.get("source_fingerprint")
    cycle_action = (
        "ADVANCE_NEW_SOURCE_FINGERPRINT"
        if source_fingerprint != prior_source_fingerprint
        else "NO_OP_SAME_SOURCE_FINGERPRINT"
    )

    trigger_monitor = {
        "schema_version": "1.0.0",
        "surface_id": "P4_4_TRIGGER_MONITOR_CURRENT",
        "generated_at_utc": generated_at,
        "source_fingerprint": source_fingerprint,
        "prior_source_fingerprint": prior_source_fingerprint,
        "cycle_action": cycle_action,
        "recommendation_fingerprint": fingerprint,
        "recommendation_published_at": published_at,
        "registry_identity": canonical_hash(registry),
        "source_snapshot": source_snapshot,
        "summary": {
            "subject_count": registry["subject_count"],
            "trigger_clause_count": registry["trigger_clause_count"],
            "invalidation_clause_count": registry["invalidation_clause_count"],
            "semantic_evidence_required_count": len(registry["clauses"]),
            "machine_fired_semantic_clause_count": 0,
            "recommendation_event_count_total": len(trigger_events),
        },
        "controls": {
            "natural_language_keyword_inference": 0,
            "phase4_forward_observation_increment": 0,
            "phase4_realized_outcome_increment": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }

    open_count = sum(x["position_state"] == "OPEN" for x in subjects)
    entry_pending = sum(x["position_state"] == "ENTRY_PENDING_MARK" for x in subjects)
    exit_pending = sum(x["position_state"] == "EXIT_PENDING_MARK" for x in subjects)
    shadow_book = {
        "schema_version": "1.0.0",
        "surface_id": "P4_4_AUTONOMOUS_SHADOW_BOOK_CURRENT",
        "generated_at_utc": generated_at,
        "source_fingerprint": source_fingerprint,
        "recommendation_fingerprint": fingerprint,
        "recommendation_published_at": published_at,
        "subjects": subjects,
        "summary": {
            "subject_count": len(subjects),
            "open_position_count": open_count,
            "entry_pending_mark_count": entry_pending,
            "exit_pending_mark_count": exit_pending,
            "normalized_open_research_units": float(
                sum(float(x.get("normalized_research_units", 0.0)) for x in subjects)
            ),
            "action_signal_count_this_cycle": action_signal_count_this_cycle,
            "fill_count_this_cycle": fill_count_this_cycle,
            "cancel_count_this_cycle": cancel_count_this_cycle,
            "action_ledger_event_count_total": len(action_ledger),
        },
        "policy": {
            "entry_states": sorted(ENTRY_STATES),
            "exit_states": sorted(EXIT_STATES),
            "normalized_research_units_per_entry": 1.0,
            "units_are_capital_weights": False,
            "cash_budget_exists": False,
            "same_or_prior_mark_fill_forbidden": True,
            "semantic_trigger_keyword_execution_forbidden": True,
        },
        "benchmark_policy": {
            "fabrication_forbidden": True,
            "default_status": "BENCHMARK_BINDING_REQUIRED_BEFORE_ATTRIBUTION",
            "relative_performance_claim_blocked_without_binding": True,
        },
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "phase4_forward_observation_increment": 0,
            "phase4_realized_outcome_increment": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
        "evaluation_eligibility": PRE_BASELINE_LABEL,
    }

    mark_request = {
        "schema_version": "1.0.0",
        "surface_id": "P4_4_SHADOW_MARK_REQUEST_CURRENT",
        "recommendation_fingerprint": fingerprint,
        "request_count": len(requests),
        "requests": requests,
        "trade_authority": TRADE_AUTHORITY,
    }

    semantic_projection = {
        "trigger_monitor": {
            k: v
            for k, v in trigger_monitor.items()
            if k not in {"generated_at_utc", "cycle_action", "prior_source_fingerprint"}
        },
        "shadow_book": {
            k: v for k, v in shadow_book.items() if k != "generated_at_utc"
        },
        "registry": registry,
        "trigger_events": trigger_events,
        "action_ledger": action_ledger,
        "mark_request": mark_request,
    }
    semantic_hash = canonical_hash(semantic_projection)
    trigger_monitor["semantic_hash"] = semantic_hash
    shadow_book["semantic_hash"] = semantic_hash

    receipt = {
        "schema_version": "1.0.0",
        "source_fingerprint": source_fingerprint,
        "cycle_action": cycle_action,
        "generated_at_utc": generated_at,
        "semantic_hash": semantic_hash,
        "recommendation_fingerprint": fingerprint,
        "mark_packet_id": mark_packet.get("packet_id", "EMPTY_NO_PENDING_ACTION"),
        "subject_count": len(subjects),
        "trigger_clause_count": registry["trigger_clause_count"],
        "invalidation_clause_count": registry["invalidation_clause_count"],
        "shadow_action_signal_count_this_cycle": action_signal_count_this_cycle,
        "shadow_open_position_count": open_count,
        "phase4_forward_observation_increment": 0,
        "phase4_realized_outcome_increment": 0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return (
        registry,
        trigger_monitor,
        trigger_events,
        shadow_book,
        action_ledger,
        mark_request,
        receipt,
    )


def validate_payloads(
    registry: dict[str, Any],
    trigger_monitor: dict[str, Any],
    trigger_events: list[dict[str, Any]],
    shadow_book: dict[str, Any],
    action_ledger: list[dict[str, Any]],
    mark_request: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    e = []
    if registry.get("natural_language_keyword_inference_authorized") is not False:
        e.append("P44_NLP_INFERENCE")
    if any(x.get("keyword_inference_authorized") for x in registry.get("clauses", [])):
        e.append("P44_CLAUSE_NLP_INFERENCE")
    if trigger_monitor.get("controls", {}).get("machine_fired_semantic_clause_count", 0) != 0:
        e.append("P44_SEMANTIC_AUTO_FIRE")
    if shadow_book.get("policy", {}).get("units_are_capital_weights") is not False:
        e.append("P44_CAPITAL_WEIGHT")
    if shadow_book.get("policy", {}).get("cash_budget_exists") is not False:
        e.append("P44_CASH_BUDGET")
    for controls in (shadow_book.get("controls", {}),):
        for key in (
            "candidate_membership_mutations",
            "real_account_mutations",
            "simulation_mutations",
            "target_portfolio_writebacks",
            "phase4_forward_observation_increment",
            "phase4_realized_outcome_increment",
            "orders",
        ):
            if int(controls.get(key, 0)) != 0:
                e.append(f"P44_PROTECTED_NONZERO:{key}")
        if controls.get("trade_authority") != TRADE_AUTHORITY:
            e.append("P44_TRADE_AUTHORITY")
    ids = [x.get("event_id") for x in trigger_events]
    if len(ids) != len(set(ids)):
        e.append("P44_TRIGGER_EVENT_DUPLICATE")
    aids = [x.get("event_id") for x in action_ledger]
    if len(aids) != len(set(aids)):
        e.append("P44_ACTION_EVENT_DUPLICATE")
    for subject in shadow_book.get("subjects", []):
        if subject.get("position_state") not in {
            "FLAT", "ENTRY_PENDING_MARK", "OPEN", "EXIT_PENDING_MARK", "CLOSED"
        }:
            e.append("P44_POSITION_STATE")
    if receipt.get("source_fingerprint") != trigger_monitor.get("source_fingerprint"):
        e.append("P44_RECEIPT_SOURCE")
    if receipt.get("semantic_hash") != trigger_monitor.get("semantic_hash"):
        e.append("P44_RECEIPT_SEMANTIC")
    if receipt.get("semantic_hash") != shadow_book.get("semantic_hash"):
        e.append("P44_SHADOW_SEMANTIC")
    if mark_request.get("trade_authority") != TRADE_AUTHORITY:
        e.append("P44_MARK_REQUEST_AUTHORITY")
    return sorted(set(e))


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--recommendation-current", required=True)
    p.add_argument("--recommendation-domain", required=True)
    p.add_argument("--prior-trigger-current")
    p.add_argument("--prior-shadow-current")
    p.add_argument("--prior-trigger-event-ledger")
    p.add_argument("--prior-action-ledger")
    p.add_argument("--mark-packet")
    p.add_argument("--output-dir", default=".p4_4_output")
    p.add_argument("--now")
    args=p.parse_args()
    now=datetime.fromisoformat(args.now.replace("Z","+00:00")) if args.now else None
    payloads=build(
        recommendation_path=Path(args.recommendation_current),
        recommendation_domain_path=Path(args.recommendation_domain),
        prior_trigger_current_path=Path(args.prior_trigger_current) if args.prior_trigger_current else None,
        prior_shadow_current_path=Path(args.prior_shadow_current) if args.prior_shadow_current else None,
        prior_trigger_event_ledger_path=Path(args.prior_trigger_event_ledger) if args.prior_trigger_event_ledger else None,
        prior_action_ledger_path=Path(args.prior_action_ledger) if args.prior_action_ledger else None,
        mark_packet_path=Path(args.mark_packet) if args.mark_packet else None,
        now=now,
    )
    errors=validate_payloads(*payloads)
    if errors:
        raise SystemExit("\n".join(errors))
    out=Path(args.output_dir)
    names=[
        "TRIGGER_REGISTRY_CURRENT.json",
        "TRIGGER_MONITOR_CURRENT.json",
        "TRIGGER_EVENT_LEDGER.jsonl",
        "SHADOW_BOOK_CURRENT.json",
        "SHADOW_ACTION_LEDGER.jsonl",
        "MARK_REQUEST_CURRENT.json",
        "cycle_receipt.json",
    ]
    for name,payload in zip(names,payloads):
        if name.endswith(".jsonl"):
            write_jsonl(out/name,payload)
        else:
            write_json(out/name,payload)
    print(json.dumps({
        "source_fingerprint": payloads[1]["source_fingerprint"],
        "cycle_action": payloads[1]["cycle_action"],
        "subjects": payloads[3]["summary"]["subject_count"],
        "triggers": payloads[0]["trigger_clause_count"],
        "invalidations": payloads[0]["invalidation_clause_count"],
        "open": payloads[3]["summary"]["open_position_count"],
        "pending_marks": payloads[5]["request_count"],
        "actions_this_cycle": payloads[3]["summary"]["action_signal_count_this_cycle"],
        "observations": 0,
        "outcomes": 0,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
