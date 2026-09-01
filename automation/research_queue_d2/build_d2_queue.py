from __future__ import annotations

import argparse
import hashlib
import json
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
SEMANTIC_TERMINAL_STATUSES = {"D2_RESEARCH_COMPLETE", "D2_RESEARCH_HOLD_EVIDENCE_GAP"}
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


def discover_cninfo(security_id: str, *, start_date: str, end_date: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import akshare as ak
    except Exception as exc:  # pragma: no cover - environment dependent
        return [], f"AKSHARE_IMPORT_FAILED:{type(exc).__name__}"

    symbol = security_id.split(".")[0]
    try:
        frame = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            market="沪深京",
            keyword="",
            category="",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
    except Exception as exc:  # pragma: no cover - network dependent
        return [], f"CNINFO_DISCOVERY_FAILED:{type(exc).__name__}"

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


def semantic_state_is_same_input(prior: dict[str, Any], previous: dict[str, Any], d1: dict[str, Any], watermark: str) -> bool:
    """Compatibility gate for semantic states written before input_watermark was retained.

    A semantic terminal state is preserved when either its object watermark matches or the
    D2 state's source D1 state id still matches the current D1 state id. A genuine D1 state
    change reopens research rather than silently carrying a stale semantic conclusion.
    """
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
    d1_path: Path = D1_CURRENT,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    now_iso = now.replace(microsecond=0).isoformat()
    today = now.date().isoformat()
    start_date = f"{now.year - 1}-01-01"

    d1 = load_json(d1_path)
    evidence = latest_d1_evidence()
    prior = load_json(D2_CURRENT) if D2_CURRENT.exists() else {}
    prior_by_id = {row["security_id"]: row for row in prior.get("queue", []) if row.get("security_id")}

    queue: list[dict[str, Any]] = []
    run_sources: list[dict[str, Any]] = []
    discovery_errors: list[dict[str, str]] = []

    for obj in routed_objects(d1):
        security_id = str(obj["security_id"])
        watermark = canonical_hash(obj)
        previous = prior_by_id.get(security_id, {})
        same_input = semantic_state_is_same_input(prior, previous, d1, watermark)
        previous_status = previous.get("status") if same_input else None
        attempts = int(previous.get("attempt_count", 0)) if same_input else 0

        baseline = baseline_sources(evidence, security_id)
        cninfo: list[dict[str, Any]] = []
        discovery_error: str | None = None
        if discover_primary_sources:
            cninfo, discovery_error = discover_cninfo(security_id, start_date=start_date, end_date=today)
            run_sources.extend(cninfo)
            if discovery_error:
                discovery_errors.append({"security_id": security_id, "error": discovery_error})

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
            "d2_questions": obj.get("d2_questions", []),
            "first_rejection": obj.get("first_rejection"),
            "baseline_source_count": len(baseline),
            "primary_source_count": max(int(previous.get("primary_source_count", 0)), len(cninfo)) if discover_primary_sources else int(previous.get("primary_source_count", 0)),
            "status": status,
            "attempt_count": attempts,
            "last_attempt_at": now_iso if discover_primary_sources else previous.get("last_attempt_at"),
            "semantic_research_required": semantic_required,
            "candidate_membership_mutation_authorized": False,
            "real_account_mutation_authorized": False,
            "simulation_mutation_authorized": False,
            "decision_mutation_authorized": False,
            "order_generation_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
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
    holds = [row for row in queue if row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"]
    blocked = [row for row in queue if row["status"].startswith("AUTO_RESEARCH_BLOCKED") or row["status"] == "D2_RESEARCH_HOLD_EVIDENCE_GAP"]

    state = {
        "schema_version": "1.0.0",
        "state_id": f"RESEARCH_QUEUE_D2_CURRENT_{now.strftime('%Y%m%dT%H%M%SZ')}",
        "as_of": now_iso,
        "status": "D2_AUTO_CONSUMER_ACTIVE_BACKLOG_PENDING" if active_pending else "D2_AUTO_CONSUMER_ACTIVE_NO_PENDING_WORK",
        "source_d1_state_id": d1.get("state_id"),
        "consumer_policy": {
            "bounded_batch_size": BATCH_SIZE,
            "event_trigger": "PUSH_TO_MAIN_WHEN_D1_CURRENT_OR_D1_EVIDENCE_CHANGES",
            "recovery_cadence": "WEEKDAYS_00:35_UTC_08:35_ASIA_SHANGHAI",
            "manual_dispatch": "BREAK_GLASS_ONLY",
            "idempotence": "UNCHANGED_D1_STATE_OR_INPUT_WATERMARK_PRESERVES_SEMANTIC_TERMINAL_WORK",
            "fail_closed": True,
            "semantic_research_owner": "CHATGPT_NATIVE_D2_RESEARCH_AND_UNDERWRITING_CONSUMER",
        },
        "queue": queue,
        "summary": {
            "routed_count": len(queue),
            "pending_count": len(active_pending),
            "completed_count": len(completed),
            "hold_evidence_gap_count": len(holds),
            "blocked_count": len(blocked),
            "batch_capacity": BATCH_SIZE,
            "manual_trigger_required": False,
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
        "d2_hold_evidence_gap_count": len(holds),
        "d2_blocked_count": len(blocked),
        "oldest_pending_attempt_at": oldest,
        "last_consumer_attempt_at": now_iso if discover_primary_sources else prior.get("as_of"),
        "next_recovery_cadence": "NEXT_WEEKDAY_08:35_ASIA_SHANGHAI",
        "manual_trigger_required": False,
        "blocked_items": [row["security_id"] for row in blocked],
        "completed_items": [row["security_id"] for row in completed],
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
        "policy": {
            "primary_source_preference": "CNINFO_OR_EXCHANGE_DISCLOSURE",
            "semantic_completion_prohibited": True,
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
        "evidence_path": str(evidence_path.relative_to(ROOT)),
        "manual_trigger_required": False,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
