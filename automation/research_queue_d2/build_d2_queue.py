from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
D1_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D1_CURRENT.json"
D1_EVIDENCE_DIR = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/RESEARCH_QUEUE_D1"
D2_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json"
D2_LIVENESS = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json"
D2_EVIDENCE_DIR = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/RESEARCH_QUEUE_D2"

BATCH_SIZE = 3
TRADE_AUTHORITY = "NONE"
CNINFO_MAX_ATTEMPTS = 2
SEMANTIC_TERMINAL_STATUSES = {"D2_RESEARCH_COMPLETE", "D2_RESEARCH_HOLD_EVIDENCE_GAP"}
SEMANTIC_COMPLETE_STATUS = "D2_RESEARCH_COMPLETE"
EXPLICIT_SEMANTIC_REFRESH_FLAGS = ("semantic_refresh_required", "fresh_d2_required", "reunderwrite_required")
SEMANTIC_PASSTHROUGH_FIELDS = (
    "research_disposition",
    "semantic_artifact",
    "first_rejection_test",
    "next_gate",
    "evidence_gap",
    "manual_user_input_required",
    "underwriting",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def underwriting_complete(row: dict[str, Any]) -> bool:
    underwriting = row.get("underwriting")
    if not isinstance(underwriting, dict):
        return False
    if underwriting.get("current_price") in (None, ""):
        return False
    if underwriting.get("entry_price") in (None, ""):
        return False
    if str(underwriting.get("confidence") or "").upper() not in {
        "HIGH", "MEDIUM", "MEDIUM_HIGH", "HIGH_MEDIUM"
    }:
        return False
    scenarios = underwriting.get("scenarios")
    if not isinstance(scenarios, list):
        return False
    names = {str(x.get("name") or "").upper() for x in scenarios if isinstance(x, dict)}
    return {"BEAR", "BASE", "BULL"}.issubset(names)


def latest_d1_evidence() -> dict[str, Any]:
    candidates = sorted(D1_EVIDENCE_DIR.glob("RESEARCH_QUEUE_D1_EVIDENCE_*.json"))
    if not candidates:
        return {"sources": [], "known_limitations": ["D1 evidence file missing"]}
    return load_json(candidates[-1])


def routed_objects(d1: dict[str, Any]) -> list[dict[str, Any]]:
    routed: list[dict[str, Any]] = []
    for row in d1.get("research_objects", []):
        disposition = str(row.get("d1_disposition", ""))
        if disposition.startswith("ADVANCE_TO_D2"):
            routed.append(row)
    return sorted(routed, key=lambda item: (int(item.get("d1_rank", 999999)), str(item.get("security_id", ""))))


def baseline_sources(evidence: dict[str, Any], security_id: str) -> list[dict[str, Any]]:
    return [source for source in evidence.get("sources", []) if source.get("security_id") == security_id]


def _cninfo_error(exc: Exception) -> str:
    return f"CNINFO_DISCOVERY_FAILED:{type(exc).__name__}:ATTEMPTS_{CNINFO_MAX_ATTEMPTS}"


def discover_cninfo(security_id: str, *, start_date: str, end_date: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import akshare as ak
    except Exception as exc:  # pragma: no cover - environment dependent
        return [], f"AKSHARE_IMPORT_FAILED:{type(exc).__name__}"

    symbol = security_id.split(".")[0]
    frame = None
    last_error: Exception | None = None
    for _attempt in range(1, CNINFO_MAX_ATTEMPTS + 1):
        try:
            frame = ak.stock_zh_a_disclosure_report_cninfo(
                symbol=symbol,
                market="沪深京",
                keyword="",
                category="",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            last_error = None
            break
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc

    if last_error is not None:
        return [], _cninfo_error(last_error)
    if frame is None or frame.empty:
        return [], "CNINFO_DISCOVERY_EMPTY"

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        title = str(row.get("公告标题") or "")
        url = str(row.get("公告链接") or "")
        when = row.get("公告时间")
        if hasattr(when, "isoformat"):
            when = when.isoformat()
        records.append({
            "source_type": "CNINFO_DISCLOSURE",
            "security_id": security_id,
            "title": title,
            "publication_time": str(when or ""),
            "url": url,
            "primary_source": True,
        })

    keywords = (
        "年度报告", "半年度报告", "季度报告", "业绩预告", "利润分配", "分红",
        "募集资金", "可转换公司债券", "投资者关系", "调研", "关联交易",
        "对外投资", "重大合同", "经营情况", "发电", "来水", "利用率",
    )
    records.sort(
        key=lambda item: (
            sum(keyword in item["title"] for keyword in keywords),
            item["publication_time"],
            item["title"],
        ),
        reverse=True,
    )
    return records[:20], None


def provider_incident_summary(discovery_errors: list[dict[str, str]], routed_count: int) -> dict[str, Any]:
    """Promote identical batch-wide source failures to a provider incident.

    This changes observability only: the mechanical consumer still fails closed and
    semantic completion must supply governed primary-source provenance separately.
    """
    if routed_count <= 1 or len(discovery_errors) != routed_count:
        return {"active": False}
    signatures = {str(row.get("error") or "") for row in discovery_errors}
    if len(signatures) != 1:
        return {"active": False}
    signature = next(iter(signatures))
    if not signature.startswith(("CNINFO_DISCOVERY_FAILED:", "AKSHARE_IMPORT_FAILED:")):
        return {"active": False}
    return {
        "active": True,
        "provider": "CNINFO_VIA_AKSHARE",
        "scope": "BATCH_LEVEL",
        "affected_count": routed_count,
        "error_signature": signature,
        "classification": "PROVIDER_INTERFACE_OR_ACCESS_FAILURE",
        "semantic_fallback_allowed": True,
        "mechanical_consumer_fail_closed": True,
    }


def explicit_semantic_refresh_required(obj: dict[str, Any]) -> bool:
    """Only an explicit material-refresh signal may invalidate completed semantic D2.

    Routine D1 reranking and daily market-signal changes are not semantic research events;
    downstream S2 already rebases completed underwriting to current portfolio marks.
    """
    if any(obj.get(flag) is True for flag in EXPLICIT_SEMANTIC_REFRESH_FLAGS):
        return True
    disposition = str(obj.get("d1_disposition") or "").upper()
    return any(token in disposition for token in ("REUNDERWRITE", "REFRESH_D2", "FRESH_D2_REQUIRED"))


def semantic_input_projection(obj: dict[str, Any]) -> dict[str, Any]:
    """Stable research-contract fields; intentionally excludes rank and daily market signals."""
    return {
        "security_id": obj.get("security_id"),
        "archetype": obj.get("archetype"),
        "d1_disposition": obj.get("d1_disposition"),
        "d2_questions": obj.get("d2_questions", []),
        "first_rejection": obj.get("first_rejection"),
        "variant_wedge": obj.get("variant_wedge"),
    }


def semantic_input_watermark(obj: dict[str, Any]) -> str:
    return canonical_hash(semantic_input_projection(obj))


def _artifact_sort_key(path: Path) -> tuple[str, int, str]:
    match = re.search(r"_(\d{8})_R(\d+)\.json$", path.name)
    if match:
        return (match.group(1), int(match.group(2)), path.name)
    return ("", 0, path.name)


def latest_completed_semantic_artifacts() -> dict[str, dict[str, Any]]:
    """Recover durable decision-grade D2 when rolling Current was overwritten by pending state."""
    latest: dict[str, tuple[tuple[str, int, str], Path, dict[str, Any]]] = {}
    for path in D2_EVIDENCE_DIR.glob("D2_RESEARCH_*.json"):
        try:
            artifact = load_json(path)
        except Exception:
            continue
        security_id = str(artifact.get("security_id") or "")
        if not security_id or artifact.get("status") != SEMANTIC_COMPLETE_STATUS:
            continue
        if not underwriting_complete(artifact):
            continue
        key = _artifact_sort_key(path)
        if security_id not in latest or key > latest[security_id][0]:
            latest[security_id] = (key, path, artifact)

    recovered: dict[str, dict[str, Any]] = {}
    for security_id, (_key, path, artifact) in latest.items():
        evidence_gap = artifact.get("evidence_gap") if isinstance(artifact.get("evidence_gap"), dict) else {}
        try:
            artifact_path = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            artifact_path = str(path)
        recovered[security_id] = {
            "security_id": security_id,
            "security_name": artifact.get("security_name"),
            "d1_rank": artifact.get("d1_rank"),
            "archetype": artifact.get("archetype"),
            "status": SEMANTIC_COMPLETE_STATUS,
            "research_disposition": artifact.get("research_disposition"),
            "semantic_artifact": artifact_path,
            "first_rejection_test": artifact.get("first_rejection_test"),
            "next_gate": artifact.get("next_gate"),
            "evidence_gap": evidence_gap,
            "manual_user_input_required": bool(evidence_gap.get("manual_user_input_required")),
            "underwriting": artifact.get("underwriting"),
            "primary_source_count": len(artifact.get("sources") or []),
            "source_discovery_mode": artifact.get("source_discovery_mode"),
            "durable_semantic_recovery": True,
        }
    return recovered


def completed_semantic_reusable(previous: dict[str, Any], obj: dict[str, Any]) -> bool:
    if previous.get("status") != SEMANTIC_COMPLETE_STATUS or not underwriting_complete(previous):
        return False
    if explicit_semantic_refresh_required(obj):
        return False

    current_semantic_watermark = semantic_input_watermark(obj)
    prior_semantic_watermark = previous.get("semantic_input_watermark")
    if prior_semantic_watermark:
        return prior_semantic_watermark == current_semantic_watermark

    # Compatibility for semantic completions written before semantic_input_watermark existed.
    comparable_fields = ("security_id", "archetype", "d1_disposition", "d2_questions", "first_rejection", "variant_wedge")
    comparable = {
        field: previous.get(field)
        for field in comparable_fields
        if field in previous
    }
    if comparable:
        current = semantic_input_projection(obj)
        return all(current.get(field) == value for field, value in comparable.items())

    # A durable completed artifact may not carry the original D1 questions.  Its completed
    # underwriting remains authoritative until an explicit refresh trigger is raised.
    return True


def semantic_state_is_same_input(
    prior: dict[str, Any],
    previous: dict[str, Any],
    d1: dict[str, Any],
    watermark: str,
    obj: dict[str, Any] | None = None,
) -> bool:
    """Preserve completed D2 across routine D1 rolls; reopen only on a material refresh signal."""
    if obj is not None and previous.get("status") == SEMANTIC_COMPLETE_STATUS:
        if explicit_semantic_refresh_required(obj):
            return False
        if underwriting_complete(previous):
            return completed_semantic_reusable(previous, obj)
        # Legacy rows marked complete before the underwriting contract was enforced still
        # need one bounded upgrade pass, but only while bound to the same D1 transaction.
        prior_d1 = prior.get("source_d1_state_id")
        current_d1 = d1.get("state_id")
        return bool(prior_d1 and current_d1 and prior_d1 == current_d1)
    if previous.get("input_watermark") == watermark:
        return True
    if previous.get("status") in SEMANTIC_TERMINAL_STATUSES:
        prior_d1 = prior.get("source_d1_state_id")
        current_d1 = d1.get("state_id")
        return bool(prior_d1 and current_d1 and prior_d1 == current_d1)
    return False


def build_state(
    *,
    discover_primary_sources: bool,
    d1_path: Path | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    now_iso = now.replace(microsecond=0).isoformat()
    today = now.date().isoformat()
    start_date = f"{now.year - 1}-01-01"

    d1 = load_json(d1_path or D1_CURRENT)
    evidence = latest_d1_evidence()
    prior = load_json(D2_CURRENT) if D2_CURRENT.exists() else {}
    prior_by_id = {row["security_id"]: row for row in prior.get("queue", []) if row.get("security_id")}
    durable_completed_by_id = latest_completed_semantic_artifacts()

    queue: list[dict[str, Any]] = []
    run_sources: list[dict[str, Any]] = []
    discovery_errors: list[dict[str, str]] = []
    routed = routed_objects(d1)

    for obj in routed:
        security_id = str(obj["security_id"])
        watermark = canonical_hash(obj)
        previous = prior_by_id.get(security_id, {})
        recovered_from_artifact = False
        if (
            previous.get("status") != SEMANTIC_COMPLETE_STATUS
            and not explicit_semantic_refresh_required(obj)
            and security_id in durable_completed_by_id
        ):
            previous = durable_completed_by_id[security_id]
            recovered_from_artifact = True

        same_input = semantic_state_is_same_input(prior, previous, d1, watermark, obj=obj)
        previous_status = previous.get("status") if same_input else None
        attempts = int(previous.get("attempt_count", 0)) if same_input else 0

        baseline = baseline_sources(evidence, security_id)
        cninfo: list[dict[str, Any]] = []
        discovery_error: str | None = None
        if discover_primary_sources:
            cninfo, discovery_error = discover_cninfo(security_id, start_date=start_date, end_date=today)
            run_sources.extend(cninfo)
            if discovery_error:
                discovery_errors.append({
                    "provider": "CNINFO_VIA_AKSHARE",
                    "security_id": security_id,
                    "error": discovery_error,
                })

        if previous_status == "D2_RESEARCH_COMPLETE" and not underwriting_complete(previous):
            status = "D2_UNDERWRITING_PENDING"
        elif previous_status in SEMANTIC_TERMINAL_STATUSES:
            status = str(previous_status)
        elif cninfo:
            status = "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING"
            attempts += 1
        elif discover_primary_sources:
            status = "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY"
            attempts += 1
        else:
            status = str(previous_status or "PENDING_AUTO_RESEARCH")

        semantic_required = status != "D2_RESEARCH_COMPLETE"
        row: dict[str, Any] = {
            "security_id": security_id,
            "security_name": obj.get("security_name"),
            "d1_rank": obj.get("d1_rank"),
            "d1_disposition": obj.get("d1_disposition"),
            "archetype": obj.get("archetype"),
            "input_watermark": watermark,
            "semantic_input_watermark": semantic_input_watermark(obj),
            "d2_questions": obj.get("d2_questions", []),
            "first_rejection": obj.get("first_rejection"),
            "baseline_source_count": len(baseline),
            "primary_source_count": max(int(previous.get("primary_source_count", 0)), len(cninfo)) if discover_primary_sources else int(previous.get("primary_source_count", 0)),
            "status": status,
            "attempt_count": attempts,
            "last_attempt_at": now_iso if discover_primary_sources else previous.get("last_attempt_at"),
            "semantic_research_required": semantic_required,
            "ai_book_auto_reunderwrite": bool(obj.get("ai_book_auto_reunderwrite")),
            "ai_book_reunderwrite_reason": obj.get("ai_book_reunderwrite_reason"),
            "semantic_research_owner": (
                "CHATGPT_NATIVE_AUTONOMOUS_AI_BOOK_D2"
                if obj.get("ai_book_auto_reunderwrite")
                else "CHATGPT_NATIVE_D2_RESEARCH_AND_UNDERWRITING_CONSUMER"
            ),
            "candidate_membership_mutation_authorized": False,
            "real_account_mutation_authorized": False,
            "simulation_mutation_authorized": False,
            "decision_mutation_authorized": False,
            "order_generation_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
            "semantic_reuse_source": (
                "DURABLE_SEMANTIC_ARTIFACT"
                if recovered_from_artifact and same_input
                else ("PRIOR_D2_CURRENT" if same_input and previous_status == SEMANTIC_COMPLETE_STATUS else None)
            ),
        }
        if same_input:
            for field in SEMANTIC_PASSTHROUGH_FIELDS:
                if field in previous:
                    row[field] = previous[field]
        queue.append(row)

    active_pending_statuses = {
        "PENDING_AUTO_RESEARCH",
        "PRIMARY_EVIDENCE_DISCOVERED_SEMANTIC_RESEARCH_PENDING",
        "AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY",
        "D2_UNDERWRITING_PENDING",
    }
    active_pending = [row for row in queue if row["status"] in active_pending_statuses]
    completed = [row for row in queue if row["status"] == "D2_RESEARCH_COMPLETE"]
    reused_completed = [row for row in completed if row.get("semantic_reuse_source")]
    holds = [row for row in queue if row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"]
    blocked = [row for row in queue if row["status"].startswith("AUTO_RESEARCH_BLOCKED") or row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"]
    provider_incident = provider_incident_summary(discovery_errors, len(routed))
    ai_book_auto_pending = [
        row for row in active_pending if row.get("ai_book_auto_reunderwrite")
    ]

    semantic_projection = [
        {
            "security_id": row.get("security_id"),
            "input_watermark": row.get("input_watermark"),
            "status": row.get("status"),
            "research_disposition": row.get("research_disposition"),
            "semantic_artifact": row.get("semantic_artifact"),
            "first_rejection_test": row.get("first_rejection_test"),
            "evidence_gap": row.get("evidence_gap"),
            "underwriting": row.get("underwriting"),
        }
        for row in queue
    ]
    semantic_state_hash = canonical_hash({
        "source_d1_state_id": d1.get("state_id"),
        "queue": semantic_projection,
    })

    state = {
        "schema_version": "1.1.0",
        "state_id": f"RESEARCH_QUEUE_D2_CURRENT_{semantic_state_hash[:16]}",
        "as_of": now_iso,
        "status": "D2_AUTO_CONSUMER_ACTIVE_BACKLOG_PENDING" if active_pending else "D2_AUTO_CONSUMER_ACTIVE_NO_PENDING_WORK",
        "source_d1_state_id": d1.get("state_id"),
        "consumer_policy": {
            "bounded_batch_size": BATCH_SIZE,
            "event_trigger": "PUSH_TO_MAIN_WHEN_D1_CURRENT_OR_D1_EVIDENCE_CHANGES",
            "recovery_cadence": "WEEKDAYS_00:35_UTC_08:35_ASIA_SHANGHAI",
            "manual_dispatch": "BREAK_GLASS_ONLY",
            "idempotence": "COMPLETED_DECISION_GRADE_D2_PERSISTS_ACROSS_ROUTINE_D1_ROLLS_UNTIL_EXPLICIT_MATERIAL_REFRESH",
            "fail_closed": True,
            "semantic_research_owner": "CHATGPT_NATIVE_D2_RESEARCH_AND_UNDERWRITING_CONSUMER",
            "ai_book_near_gate_refresh": "AUTO_ROUTED_TO_CHATGPT_NATIVE_SEMANTIC_D2_WITHOUT_MANUAL_D1_D2_DISPATCH",
        },
        "queue": queue,
        "summary": {
            "routed_count": len(queue),
            "pending_count": len(active_pending),
            "completed_count": len(completed),
            "reused_completed_count": len(reused_completed),
            "hold_evidence_gap_count": len(holds),
            "blocked_count": len(blocked),
            "batch_capacity": BATCH_SIZE,
            "manual_trigger_required": False,
            "provider_incident_active": bool(provider_incident.get("active")),
            "ai_book_auto_reunderwrite_pending_count": len(ai_book_auto_pending),
        },
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "decision_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }

    oldest = None
    for row in active_pending:
        when = row.get("last_attempt_at")
        if when and (oldest is None or when < oldest):
            oldest = when

    liveness = {
        "schema_version": "1.0.0",
        "as_of": now_iso,
        "status": "PASS_D2_CONSUMER_LIVE" if queue else "PASS_D2_CONSUMER_LIVE_NO_ROUTED_WORK",
        "d2_pending_count": len(active_pending),
        "d2_completed_count": len(completed),
        "d2_reused_completed_count": len(reused_completed),
        "d2_hold_evidence_gap_count": len(holds),
        "d2_blocked_count": len(blocked),
        "oldest_pending_attempt_at": oldest,
        "last_consumer_attempt_at": now_iso if discover_primary_sources else prior.get("as_of"),
        "next_recovery_cadence": "NEXT_WEEKDAY_08:35_ASIA_SHANGHAI",
        "manual_trigger_required": False,
        "blocked_items": [row["security_id"] for row in blocked],
        "completed_items": [row["security_id"] for row in completed],
        "ai_book_auto_reunderwrite_pending_items": [
            row["security_id"] for row in ai_book_auto_pending
        ],
        "provider_incident": provider_incident,
        "trade_authority": TRADE_AUTHORITY,
    }

    evidence_run = {
        "schema_version": "1.0.0",
        "run_id": f"RESEARCH_QUEUE_D2_EVIDENCE_{now.strftime('%Y%m%dT%H%M%SZ')}",
        "captured_at": now_iso,
        "source_d1_state_id": d1.get("state_id"),
        "discovery_enabled": discover_primary_sources,
        "primary_sources": run_sources,
        "discovery_errors": discovery_errors,
        "provider_incident": provider_incident,
        "policy": {
            "primary_source_preference": "CNINFO_OR_EXCHANGE_DISCLOSURE",
            "semantic_completion_prohibited": True,
            "semantic_fallback": "CHATGPT_NATIVE_D2_MAY_USE_GOVERNED_EXCHANGE_OR_COMPANY_PRIMARY_DISCLOSURES_WITH_PROVENANCE",
            "purpose": "AUTOMATIC_PRIMARY_EVIDENCE_DISCOVERY_FOR_D2_SEMANTIC_RESEARCH",
        },
        "controls": state["controls"],
    }
    return state, liveness, evidence_run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover-primary-sources", action="store_true")
    parser.add_argument("--d1-current", default=str(D1_CURRENT))
    args = parser.parse_args()

    state, liveness, evidence_run = build_state(
        discover_primary_sources=args.discover_primary_sources,
        d1_path=Path(args.d1_current),
    )
    write_json(D2_CURRENT, state)
    write_json(D2_LIVENESS, liveness)
    evidence_path = D2_EVIDENCE_DIR / f"{evidence_run['run_id']}.json"
    write_json(evidence_path, evidence_run)

    print(json.dumps({
        "status": state["status"],
        "pending": state["summary"]["pending_count"],
        "completed": state["summary"]["completed_count"],
        "blocked": state["summary"]["blocked_count"],
        "provider_incident_active": state["summary"].get("provider_incident_active", False),
        "evidence_path": str(evidence_path.relative_to(ROOT)),
        "manual_trigger_required": False,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
