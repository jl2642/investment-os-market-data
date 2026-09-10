from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
CAPITAL_HURDLE = 0.10
MAX_ACCEPTABLE_BEAR_DOWNSIDE = -0.35


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mark_map(marks: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str | None]:
    watermark = (marks.get("data_watermark") or {}).get("latest_mark_date")
    rows: dict[str, dict[str, Any]] = {}
    for row in marks.get("marks", []) or []:
        sid = str(row.get("security_id") or "").strip()
        if not sid:
            continue
        price = _num(row.get("mark"))
        if price is None:
            price = _num(row.get("mark_price"))
        if price is None:
            price = _num(row.get("price"))
        if price is None or price <= 0:
            continue
        rows[sid] = {**row, "resolved_mark": price}
    return rows, str(watermark) if watermark else None


def _pending_ids(raw_d2: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for row in raw_d2.get("queue", []) or []:
        sid = str(row.get("security_id") or "").strip()
        status = str(row.get("status") or "").upper()
        semantic_required = bool(row.get("semantic_research_required"))
        if sid and semantic_required and "PENDING" in status:
            out.add(sid)
    return out


def _recompute_comparison_status(row: dict[str, Any], metrics: dict[str, Any]) -> str:
    prior = str(row.get("comparison_status") or "")
    if prior in {
        "AVOID_INVALIDATION_TRIGGERED",
        "EVIDENCE_BLOCKED",
        "UNDERWRITING_PENDING",
        "UNDERWRITING_INCOMPLETE",
    }:
        return prior
    expected = _num(metrics.get("expected_return"))
    current = _num(metrics.get("current_price"))
    entry = _num(metrics.get("entry_price"))
    bear_downside = _num(metrics.get("bear_downside"))
    if expected is None or current is None or entry is None or bear_downside is None:
        return "UNDERWRITING_INCOMPLETE"
    if expected <= 0:
        return "AVOID_NEGATIVE_EXPECTED_RETURN"
    if current > entry:
        return "PRICE_BLOCKED"
    if expected >= CAPITAL_HURDLE and bear_downside >= MAX_ACCEPTABLE_BEAR_DOWNSIDE:
        return "PASS_NEW_CAPITAL"
    return "CAPITAL_NOT_COMPETITIVE"


def _action_for_status(status: str, existing: bool) -> str:
    if status == "RESEARCH_REFRESH_PENDING":
        return "HOLD" if existing else "WATCH"
    if status == "AVOID_INVALIDATION_TRIGGERED":
        return "EXIT" if existing else "AVOID"
    if status == "EVIDENCE_BLOCKED":
        return "WATCH_FOR_EVIDENCE"
    if status in {"UNDERWRITING_PENDING", "UNDERWRITING_INCOMPLETE"}:
        return "WATCH"
    if status == "AVOID_NEGATIVE_EXPECTED_RETURN":
        return "TRIM" if existing else "AVOID"
    if status == "PASS_NEW_CAPITAL":
        return "ADD" if existing else "BUY"
    if status == "PRICE_BLOCKED":
        return "HOLD" if existing else "BUY_BELOW"
    return "HOLD" if existing else "WATCH"


def rebase_decisions(
    comparison: dict[str, Any],
    recommendation: dict[str, Any],
    marks: dict[str, Any],
    raw_d2: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    marks_by_id, watermark = _mark_map(marks)
    pending = _pending_ids(raw_d2)

    comparison = json.loads(json.dumps(comparison))
    recommendation = json.loads(json.dumps(recommendation))

    comp_by_id: dict[str, dict[str, Any]] = {}
    for row in comparison.get("rows", []) or []:
        sid = str(row.get("security_id") or "")
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else None
        mark = marks_by_id.get(sid)
        if metrics and mark:
            current = _num(metrics.get("current_price"))
            fair = _num(metrics.get("probability_weighted_value"))
            bear = _num(metrics.get("bear_value"))
            latest = _num(mark.get("resolved_mark"))
            if current and fair is not None and bear is not None and latest and latest > 0:
                metrics.setdefault("underwriting_price", current)
                metrics.setdefault("underwriting_price_as_of", metrics.get("price_as_of"))
                metrics.setdefault("original_expected_return", fair / current - 1.0)
                metrics.setdefault("original_bear_downside", bear / current - 1.0)
                metrics["current_market_price"] = latest
                metrics["current_market_price_as_of"] = mark.get("as_of_date") or watermark
                metrics["current_price"] = latest
                metrics["expected_return"] = fair / latest - 1.0
                metrics["bear_downside"] = bear / latest - 1.0
                metrics["price_basis"] = "PORTFOLIO_MARKS_CURRENT"
                row["comparison_status"] = _recompute_comparison_status(row, metrics)
        if sid in pending:
            row["comparison_status"] = "RESEARCH_REFRESH_PENDING"
            row["research_freshness"] = "RESEARCH_REFRESH_PENDING"
        else:
            row["research_freshness"] = "CURRENT_OR_PERSISTED_NO_ACTIVE_REFRESH"
        comp_by_id[sid] = row

    ranked = [
        r for r in comparison.get("rows", []) or []
        if isinstance(r.get("metrics"), dict) and _num(r["metrics"].get("expected_return")) is not None
    ]
    ranked.sort(key=lambda r: float(r["metrics"]["expected_return"]), reverse=True)
    ranks = {r.get("security_id"): i + 1 for i, r in enumerate(ranked)}
    peer_returns = [float(r["metrics"]["expected_return"]) for r in ranked]
    peer_median = sorted(peer_returns)[len(peer_returns) // 2] if peer_returns else None
    for row in comparison.get("rows", []) or []:
        row["rank_among_current_d2"] = ranks.get(row.get("security_id"))
        row["peer_expected_return_median"] = peer_median
        metrics = row.get("metrics") or {}
        row["comparison_vector"] = {
            "expected_return": metrics.get("expected_return"),
            "bear_downside": metrics.get("bear_downside"),
            "confidence": metrics.get("confidence"),
            "existing_position": row.get("existing_position"),
            "cash_hurdle": row.get("cash_hurdle"),
            "capital_hurdle": row.get("capital_hurdle"),
        }

    comparison["price_freshness_policy"] = {
        "underwriting_snapshot_preserved": True,
        "portfolio_decisions_rebased_to_latest_marks": True,
        "latest_mark_date": watermark,
        "active_semantic_refresh_fails_closed": True,
    }
    comparison["state_id"] = "CAPITAL_COMPARISON_CURRENT_MARK_REBASED_" + canonical_hash(comparison.get("rows", []))[:16]

    for rec in recommendation.get("records", []) or []:
        sid = str(rec.get("security_id") or "")
        comp = comp_by_id.get(sid, {})
        metrics = comp.get("metrics") or {}
        if metrics:
            rec["underwriting_price"] = metrics.get("underwriting_price", metrics.get("current_price"))
            rec["underwriting_price_as_of"] = metrics.get("underwriting_price_as_of", metrics.get("price_as_of"))
            rec["original_expected_return"] = metrics.get("original_expected_return", metrics.get("expected_return"))
            rec["current_market_price"] = metrics.get("current_market_price", metrics.get("current_price"))
            rec["current_market_price_as_of"] = metrics.get("current_market_price_as_of", metrics.get("price_as_of"))
            rec["current_price"] = metrics.get("current_price")
            rec["expected_return"] = metrics.get("expected_return")
            rec["bear_downside"] = metrics.get("bear_downside")
            rec["probability_weighted_value"] = metrics.get("probability_weighted_value")
            rec["price_basis"] = metrics.get("price_basis", "D2_UNDERWRITING_SNAPSHOT")
        status = str(comp.get("comparison_status") or "UNDERWRITING_PENDING")
        existing = bool(comp.get("existing_position"))
        rec["action"] = _action_for_status(status, existing)
        rec["ready_for_user_decision"] = rec["action"] in {"BUY", "ADD", "TRIM", "EXIT"}
        rec["research_freshness"] = comp.get("research_freshness")
        if status == "RESEARCH_REFRESH_PENDING":
            rec["top_blocker"] = "RESEARCH_REFRESH_PENDING"
            rec["ready_for_user_decision"] = False
        reasons = list(rec.get("top_reasons") or [])
        reasons = [x for x in reasons if not str(x).startswith("D2_CAPITAL_RANK_")]
        rank = comp.get("rank_among_current_d2")
        if rank:
            reasons.append(f"D2_CAPITAL_RANK_{rank}")
        rec["top_reasons"] = reasons

    counts: dict[str, int] = {}
    for rec in recommendation.get("records", []) or []:
        action = str(rec.get("action") or "UNKNOWN")
        counts[action] = counts.get(action, 0) + 1
    recommendation.setdefault("summary", {})["action_counts"] = counts
    recommendation["summary"]["ready_for_user_decision_count"] = sum(
        bool(r.get("ready_for_user_decision")) for r in recommendation.get("records", []) or []
    )
    recommendation["source_capital_comparison_state_id"] = comparison["state_id"]
    recommendation["price_freshness_policy"] = comparison["price_freshness_policy"]
    recommendation["state_id"] = "RECOMMENDATION_CURRENT_MARK_REBASED_" + canonical_hash(recommendation.get("records", []))[:16]

    for payload in (comparison, recommendation):
        controls = payload.get("controls") or {}
        if controls.get("orders", 0) != 0 or controls.get("trade_authority", TRADE_AUTHORITY) != TRADE_AUTHORITY:
            raise ValueError("PRICE_REBASE_SAFETY_BOUNDARY_VIOLATION")
    return comparison, recommendation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--portfolio-marks", required=True)
    parser.add_argument("--raw-d2", required=True)
    args = parser.parse_args()

    comparison, recommendation = rebase_decisions(
        read_json(args.comparison),
        read_json(args.recommendation),
        read_json(args.portfolio_marks),
        read_json(args.raw_d2),
    )
    write_json(args.comparison, comparison)
    write_json(args.recommendation, recommendation)
    print(json.dumps({
        "status": "PASS_MARK_REBASE_AND_RESEARCH_FRESHNESS_GUARD",
        "latest_mark_date": comparison.get("price_freshness_policy", {}).get("latest_mark_date"),
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
