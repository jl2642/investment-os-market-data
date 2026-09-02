from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRADE_AUTHORITY = "NONE"
D1_BATCH_SIZE = 10
D2_CAPACITY = 3
CAPITAL_HURDLE = 0.10
CASH_HURDLE = 0.04
MAX_ACCEPTABLE_BEAR_DOWNSIDE = -0.35
VALID_CONFIDENCE = {"HIGH", "MEDIUM", "MEDIUM_HIGH", "HIGH_MEDIUM"}


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_hash(payload: Any) -> str:
    text = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_longlist(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in (
            "overall_rank",
            "sleeve_count",
            "primary_sleeve_rank",
            "primary_sleeve_rank_percentile",
            "best_sleeve_score",
            "normalized_primary_score",
            "cross_sleeve_bonus",
            "aggregate_score",
            "event_flag_count",
            "avg_turnover_cny_20d",
            "return_20d",
            "return_60d",
            "return_120d",
            "return_250d",
            "distance_52w_high",
            "volatility_60d",
            "max_drawdown_120d",
        ):
            if key in row:
                row[key] = _num(row[key])
    return rows


def _financial_context(
    financial_rows: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in financial_rows or []:
        sid = str(row.get("symbol") or row.get("security_id") or "")
        if not sid:
            continue
        score = None
        for key in (
            "financial_score",
            "investment_os_score",
            "score",
            "composite_score",
            "score_percentile",
            "financial_score_percentile",
        ):
            if key in row and _num(row.get(key)) is not None:
                score = _num(row.get(key))
                break
        confidence = str(
            row.get("confidence_grade")
            or row.get("score_confidence")
            or row.get("confidence")
            or ""
        )
        status = str(row.get("status") or row.get("score_status") or "")
        out[sid] = {
            "financial_score": score,
            "financial_confidence": confidence or None,
            "financial_status": status or None,
        }
    return out


def build_opportunity_queue(
    longlist: list[dict[str, Any]],
    *,
    screen_source: dict[str, Any],
    financial_rows: list[dict[str, Any]] | None = None,
    limit: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    fin = _financial_context(financial_rows)
    rows: list[dict[str, Any]] = []
    priority_order = {
        "A_IMMEDIATE_RESEARCH": 0,
        "B_WATCH_OR_TRIGGER": 1,
        "C_SCREEN_FLAG_ONLY": 2,
    }
    sorted_rows = sorted(
        longlist,
        key=lambda r: (
            priority_order.get(str(r.get("research_priority")), 9),
            int(_num(r.get("overall_rank")) or 999999),
            str(r.get("symbol") or ""),
        ),
    )
    for row in sorted_rows[:limit]:
        sid = str(row.get("symbol") or "")
        rows.append(
            {
                "security_id": sid,
                "security_name": row.get("name"),
                "as_of_date": row.get("as_of_date"),
                "research_priority": row.get("research_priority"),
                "overall_rank": int(_num(row.get("overall_rank")) or 0),
                "primary_sleeve": row.get("primary_sleeve"),
                "sleeves": str(row.get("sleeves") or "").split("|")
                if row.get("sleeves")
                else [],
                "market_signal": {
                    "aggregate_score": _num(row.get("aggregate_score")),
                    "return_20d": _num(row.get("return_20d")),
                    "return_60d": _num(row.get("return_60d")),
                    "return_120d": _num(row.get("return_120d")),
                    "volatility_60d": _num(row.get("volatility_60d")),
                    "max_drawdown_120d": _num(row.get("max_drawdown_120d")),
                    "avg_turnover_cny_20d": _num(row.get("avg_turnover_cny_20d")),
                    "confidence_grade": row.get("confidence_grade"),
                    "factor_record_quality": row.get("factor_record_quality"),
                },
                "fundamental_context": fin.get(
                    sid,
                    {
                        "financial_score": None,
                        "financial_confidence": None,
                        "financial_status": "NOT_BOUND_IN_THIS_CYCLE",
                    },
                ),
                "candidate_membership_required": False,
                "next_stage": "D1_FAST_TRIAGE",
                "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
            }
        )
    source_fingerprint = canonical_hash(
        {
            "screen_source": screen_source,
            "rows": [
                {
                    "security_id": r["security_id"],
                    "overall_rank": r["overall_rank"],
                    "research_priority": r["research_priority"],
                }
                for r in rows
            ],
        }
    )
    return {
        "schema_version": "2.0.0",
        "state_id": f"OPPORTUNITY_CURRENT_{source_fingerprint[:16]}",
        "generated_at_utc": now.replace(microsecond=0).isoformat(),
        "status": "PASS_OPPORTUNITY_DISCOVERY_NO_CANDIDATE_GATE",
        "source_snapshot": screen_source,
        "opportunity_count": len(rows),
        "rows": rows,
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "decision_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }


def _d2_questions(row: dict[str, Any]) -> list[str]:
    sleeve = str(row.get("primary_sleeve") or "")
    common = [
        "Normalize earnings and cash flow using the latest primary financial disclosures.",
        "Build an explicit valuation range and identify what expectations are embedded in the current price.",
        "Define the first-rejection test and the evidence that would invalidate the thesis.",
    ]
    if sleeve == "DEFENSIVE_STABILITY":
        specific = [
            "Test balance-sheet resilience, cash conversion and sustainable shareholder return.",
            "Compare the opportunity with lower-risk defensive and cash alternatives.",
        ]
    elif sleeve == "RECOVERY_WATCH":
        specific = [
            "Separate cyclical/base-effect recovery from durable operating improvement.",
            "Identify the operational catalyst that would make the recovery investable rather than merely observable.",
        ]
    elif sleeve == "LIQUID_BREAKOUT":
        specific = [
            "Determine whether the price breakout is supported by a fundamental earnings or cash-flow inflection.",
            "Measure how much growth or margin improvement the current valuation already discounts.",
        ]
    else:
        specific = [
            "Determine whether trend persistence is supported by durable fundamental change rather than expectations alone.",
            "Test whether the expected return remains attractive after normalizing current momentum.",
        ]
    return specific + common


def _first_rejection(row: dict[str, Any]) -> str:
    sleeve = str(row.get("primary_sleeve") or "")
    if sleeve == "RECOVERY_WATCH":
        return (
            "Reject D2 promotion if the apparent recovery is mainly base effect, "
            "transient cycle support, or weak cash conversion."
        )
    if sleeve == "DEFENSIVE_STABILITY":
        return (
            "Reject D2 promotion if balance-sheet, cash-conversion or normalized-return "
            "evidence does not support the defensive label."
        )
    if sleeve == "LIQUID_BREAKOUT":
        return (
            "Reject D2 promotion if the price move lacks a primary-source fundamental "
            "inflection or valuation already discounts the plausible upside."
        )
    return (
        "Reject D2 promotion if normalized fundamentals do not support the market signal "
        "or valuation eliminates the expected-return advantage."
    )


def build_d1(
    opportunity: dict[str, Any],
    *,
    prior_d1: dict[str, Any] | None = None,
    batch_size: int = D1_BATCH_SIZE,
    d2_capacity: int = D2_CAPACITY,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    prior_d1 = prior_d1 or {}
    served = list(
        dict.fromkeys(str(x) for x in prior_d1.get("served_security_ids", []) if x)
    )
    served_set = set(served)
    candidates = [
        r
        for r in opportunity.get("rows", [])
        if str(r.get("security_id") or "") not in served_set
    ]
    if len(candidates) < batch_size:
        candidates = list(opportunity.get("rows", []))
        served = []
    selected = candidates[:batch_size]
    research_objects: list[dict[str, Any]] = []
    advance_count = 0
    for rank, row in enumerate(selected, start=1):
        priority = str(row.get("research_priority") or "")
        signal = row.get("market_signal", {})
        r60 = _num(signal.get("return_60d"))
        vol = _num(signal.get("volatility_60d"))
        extreme = (r60 is not None and r60 > 1.0) or (
            vol is not None and vol > 0.80
        )
        if (
            priority == "A_IMMEDIATE_RESEARCH"
            and not extreme
            and advance_count < d2_capacity
        ):
            disposition = "ADVANCE_TO_D2_FAST_TRIAGE"
            advance_count += 1
        elif priority == "A_IMMEDIATE_RESEARCH":
            disposition = "WATCH_FOR_FUNDAMENTAL_CONFIRMATION"
        elif priority == "B_WATCH_OR_TRIGGER":
            disposition = "WATCH_D1_TRIGGER_OR_FUNDAMENTAL_CONFIRMATION"
        else:
            disposition = "REJECT_FOR_NOW_LOW_RESEARCH_PRIORITY"
        research_objects.append(
            {
                "security_id": row.get("security_id"),
                "security_name": row.get("security_name"),
                "d1_rank": rank,
                "d1_disposition": disposition,
                "archetype": row.get("primary_sleeve"),
                "source_opportunity_rank": row.get("overall_rank"),
                "research_priority": priority,
                "market_signal": signal,
                "fundamental_context": row.get("fundamental_context"),
                "variant_wedge": (
                    "D1 fast triage only: test whether the observed market signal is "
                    "supported by normalized fundamentals and an attractive valuation."
                ),
                "first_rejection": _first_rejection(row),
                "d2_questions": _d2_questions(row),
                "candidate_membership_required": False,
                "trade_authority": TRADE_AUTHORITY,
            }
        )
    served_after = list(
        dict.fromkeys(
            served
            + [
                str(r.get("security_id"))
                for r in selected
                if r.get("security_id")
            ]
        )
    )
    source_id = str(opportunity.get("state_id") or "")
    state_hash = canonical_hash(
        {
            "source": source_id,
            "selected": [
                {
                    "security_id": r["security_id"],
                    "d1_disposition": r["d1_disposition"],
                }
                for r in research_objects
            ],
            "served": served_after,
        }
    )
    return {
        "schema_version": "2.0.0",
        "state_id": f"RESEARCH_QUEUE_D1_CURRENT_{state_hash[:16]}",
        "as_of": now.replace(microsecond=0).isoformat(),
        "status": "D1_FAST_TRIAGE_COMPLETE",
        "source_opportunity_state_id": source_id,
        "batch_size": len(research_objects),
        "served_security_ids": served_after,
        "priority_order": [r["security_id"] for r in research_objects],
        "research_objects": research_objects,
        "routing_summary": {
            "advance_to_d2_count": sum(
                str(r["d1_disposition"]).startswith("ADVANCE_TO_D2")
                for r in research_objects
            ),
            "watch_count": sum(
                "WATCH" in str(r["d1_disposition"]) for r in research_objects
            ),
            "reject_count": sum(
                "REJECT" in str(r["d1_disposition"]) for r in research_objects
            ),
            "ready_for_user_decision": 0,
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


def rejection_triggered(value: Any) -> bool:
    """Return True only for thesis invalidation, not promotion/price gates."""
    text = str(value or "").upper()
    if not text:
        return False
    if any(
        token in text
        for token in (
            "NOT_TRIGGERED",
            "NOT_FORMALLY_TRIGGERED",
            "FOR_PROMOTION",
            "VALUATION_LEG_TRIGGERED",
            "PRICE_GATE_TRIGGERED",
            "CAPITAL_GATE_TRIGGERED",
        )
    ):
        return False
    return any(
        token in text
        for token in (
            "TRIGGERED_BY_KILL_THESIS",
            "KILL_THESIS_TRIGGERED",
            "THESIS_INVALIDATED",
            "INVALIDATION_TRIGGERED",
            "FUNDAMENTAL_REJECTION_TRIGGERED",
        )
    )


def position_ids(position_payload: dict[str, Any]) -> set[str]:
    return {
        str(r.get("security_id"))
        for r in position_payload.get("holdings", [])
        if r.get("security_id")
    }


def evidence_gap_is_material(row: dict[str, Any]) -> bool:
    gap = row.get("evidence_gap")
    if isinstance(gap, dict):
        return bool(gap.get("material"))
    return bool(gap)


def load_latest_semantic_d2(
    directory: Path | None,
) -> list[dict[str, Any]]:
    if directory is None or not directory.exists():
        return []
    latest: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
    for path in sorted(directory.glob("D2_RESEARCH_*.json")):
        try:
            row = load_json(path)
        except Exception:
            continue
        sid = str(row.get("security_id") or "")
        if not sid:
            continue
        if str(row.get("status") or "") not in {
            "D2_RESEARCH_COMPLETE",
            "D2_RESEARCH_HOLD_EVIDENCE_GAP",
        }:
            continue
        if not isinstance(row.get("underwriting"), dict):
            continue
        underwriting = row.get("underwriting") or {}
        sort_key = (
            str(underwriting.get("price_as_of") or ""),
            path.name,
        )
        candidate = dict(row)
        candidate["source_semantic_d2_artifact"] = path.name
        if sid not in latest or sort_key > latest[sid][0]:
            latest[sid] = (sort_key, candidate)
    return [latest[sid][1] for sid in sorted(latest)]


def load_latest_holding_d2(
    directory: Path | None,
    *,
    real_positions: dict[str, Any] | None = None,
    simulation_positions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if directory is None or not directory.exists():
        return []
    holding_ids = position_ids(real_positions or {}) | position_ids(
        simulation_positions or {}
    )
    latest: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
    for path in sorted(directory.glob("D2_RESEARCH_*.json")):
        try:
            row = load_json(path)
        except Exception:
            continue
        sid = str(row.get("security_id") or "")
        if not sid or sid not in holding_ids:
            continue
        context = str(row.get("account_context") or "").upper()
        update_type = str(row.get("research_update_type") or "").upper()
        if "EXISTING" not in context and "EXISTING" not in update_type:
            continue
        if str(row.get("status") or "") not in {
            "D2_RESEARCH_COMPLETE",
            "D2_RESEARCH_HOLD_EVIDENCE_GAP",
        }:
            continue
        underwriting = row.get("underwriting") or {}
        sort_key = (
            str(underwriting.get("price_as_of") or ""),
            path.name,
        )
        candidate = dict(row)
        candidate["source_holding_d2_artifact"] = path.name
        candidate["source_semantic_d2_artifact"] = path.name
        if sid not in latest or sort_key > latest[sid][0]:
            latest[sid] = (sort_key, candidate)
    return [latest[sid][1] for sid in sorted(latest)]


def merge_d2_with_semantic_research(
    primary_d2: dict[str, Any],
    semantic_rows: list[dict[str, Any]],
    *,
    holding_ids: set[str] | None = None,
) -> dict[str, Any]:
    holding_ids = holding_ids or set()
    semantic_by_id = {
        str(row.get("security_id") or ""): row
        for row in semantic_rows
        if row.get("security_id")
    }
    merged_primary: list[dict[str, Any]] = []
    carried_forward: list[dict[str, Any]] = []
    for primary in list(primary_d2.get("queue", []) or []):
        sid = str(primary.get("security_id") or "")
        status = str(primary.get("status") or "")
        decision_grade_primary = (
            status in {"D2_RESEARCH_COMPLETE", "D2_RESEARCH_HOLD_EVIDENCE_GAP"}
            and isinstance(primary.get("underwriting"), dict)
        )
        semantic = semantic_by_id.get(sid)
        if not decision_grade_primary and semantic is not None:
            replacement = dict(semantic)
            replacement["source_reuse_reason"] = (
                "LATEST_DECISION_GRADE_D2_CARRY_FORWARD_FOR_REPEATED_D1_SUBJECT"
            )
            merged_primary.append(replacement)
            carried_forward.append(replacement)
        else:
            merged_primary.append(primary)

    seen = {
        str(row.get("security_id") or "")
        for row in merged_primary
        if row.get("security_id")
    }
    supplemental = [
        row
        for row in semantic_rows
        if str(row.get("security_id") or "") in holding_ids
        and str(row.get("security_id") or "") not in seen
    ]
    merged = dict(primary_d2)
    merged["queue"] = merged_primary + supplemental
    merged["source_primary_d2_state_id"] = primary_d2.get("state_id")
    merged["carried_forward_semantic_d2_count"] = len(carried_forward)
    merged["supplemental_holding_d2_count"] = len(supplemental)
    if carried_forward or supplemental:
        identity = canonical_hash(
            {
                "primary_d2_state_id": primary_d2.get("state_id"),
                "carried_forward_artifacts": [
                    row.get("source_semantic_d2_artifact")
                    for row in carried_forward
                ],
                "holding_artifacts": [
                    row.get("source_semantic_d2_artifact")
                    for row in supplemental
                ],
            }
        )
        merged["state_id"] = (
            f"{primary_d2.get('state_id') or 'D2_CURRENT'}_SEMANTIC_{identity[:12]}"
        )
    return merged


def merge_d2_with_holding_research(
    primary_d2: dict[str, Any],
    holding_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    primary_rows = list(primary_d2.get("queue", []) or [])
    seen = {
        str(row.get("security_id") or "")
        for row in primary_rows
        if row.get("security_id")
    }
    supplemental = [
        row
        for row in holding_rows
        if str(row.get("security_id") or "") not in seen
    ]
    merged = dict(primary_d2)
    merged["queue"] = primary_rows + supplemental
    merged["source_primary_d2_state_id"] = primary_d2.get("state_id")
    merged["supplemental_holding_d2_count"] = len(supplemental)
    if supplemental:
        identity = canonical_hash(
            {
                "primary_d2_state_id": primary_d2.get("state_id"),
                "holding_artifacts": [
                    row.get("source_holding_d2_artifact") for row in supplemental
                ],
            }
        )
        merged["state_id"] = (
            f"{primary_d2.get('state_id') or 'D2_CURRENT'}_HOLDINGS_{identity[:12]}"
        )
    return merged


def _underwriting_metrics(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    u = row.get("underwriting")
    missing: list[str] = []
    if not isinstance(u, dict):
        return None, ["UNDERWRITING_OBJECT_ABSENT"]
    current = _num(u.get("current_price"))
    entry = _num(
        u.get("entry_price")
        if u.get("entry_price") not in (None, "")
        else (
            u.get("research_reopen_price")
            if u.get("research_reopen_price") not in (None, "")
            else u.get("hurdle_entry_price_15pct")
        )
    )
    confidence = str(u.get("confidence") or "").upper()
    scenarios = u.get("scenarios") if isinstance(u.get("scenarios"), list) else []
    values: dict[str, float] = {}
    probs: dict[str, float] = {}
    for s in scenarios:
        name = str(s.get("name") or "").upper()
        value = _num(
            s.get("value")
            if s.get("value") not in (None, "")
            else s.get("value_per_share")
        )
        prob = _num(s.get("probability"))
        if name and value is not None and prob is not None:
            values[name] = value
            probs[name] = prob
    for name in ("BEAR", "BASE", "BULL"):
        if name not in values or name not in probs:
            missing.append(f"SCENARIO_{name}_ABSENT")
    if current is None or current <= 0:
        missing.append("CURRENT_PRICE_ABSENT")
    if entry is None or entry <= 0:
        missing.append("ENTRY_PRICE_ABSENT")
    if confidence not in VALID_CONFIDENCE:
        missing.append("CONFIDENCE_NOT_DECISION_GRADE")
    if probs and abs(sum(probs.values()) - 1.0) > 0.02:
        missing.append("SCENARIO_PROBABILITIES_NOT_NORMALIZED")
    if missing:
        return None, missing
    fair = sum(values[k] * probs[k] for k in ("BEAR", "BASE", "BULL"))
    expected = fair / current - 1.0
    downside = values["BEAR"] / current - 1.0
    return {
        "current_price": current,
        "entry_price": entry,
        "bear_value": values["BEAR"],
        "base_value": values["BASE"],
        "bull_value": values["BULL"],
        "scenario_probabilities": probs,
        "probability_weighted_value": fair,
        "expected_return": expected,
        "bear_downside": downside,
        "confidence": confidence,
        "price_as_of": u.get("price_as_of"),
        "normalized_earnings_basis": u.get("normalized_earnings_basis"),
        "kill_thesis": u.get("kill_thesis") or row.get("first_rejection"),
        "catalysts": u.get("catalysts") or [],
        "portfolio_role": u.get("portfolio_role"),
    }, []


def build_capital_comparison(
    d2: dict[str, Any],
    *,
    real_positions: dict[str, Any] | None = None,
    simulation_positions: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    real_ids = position_ids(real_positions or {})
    sim_ids = position_ids(simulation_positions or {})
    rows: list[dict[str, Any]] = []
    for d2row in d2.get("queue", []):
        sid = str(d2row.get("security_id") or "")
        status = str(d2row.get("status") or "")
        metrics, missing = _underwriting_metrics(d2row)
        existing = sid in real_ids or sid in sim_ids
        material_gap = (
            status == "D2_RESEARCH_HOLD_EVIDENCE_GAP"
            or evidence_gap_is_material(d2row)
        )
        if rejection_triggered(d2row.get("first_rejection_test")):
            comp = "AVOID_INVALIDATION_TRIGGERED"
        elif material_gap:
            comp = "EVIDENCE_BLOCKED"
        elif status != "D2_RESEARCH_COMPLETE":
            comp = "UNDERWRITING_PENDING"
        elif metrics is None:
            comp = "UNDERWRITING_INCOMPLETE"
        elif metrics["expected_return"] <= 0:
            comp = "AVOID_NEGATIVE_EXPECTED_RETURN"
        elif metrics["current_price"] > metrics["entry_price"]:
            comp = "PRICE_BLOCKED"
        elif (
            metrics["expected_return"] >= CAPITAL_HURDLE
            and metrics["bear_downside"] >= MAX_ACCEPTABLE_BEAR_DOWNSIDE
        ):
            comp = "PASS_NEW_CAPITAL"
        else:
            comp = "CAPITAL_NOT_COMPETITIVE"
        rows.append(
            {
                "security_id": sid,
                "security_name": d2row.get("security_name"),
                "d2_status": status,
                "comparison_status": comp,
                "existing_position": existing,
                "position_accounts": [
                    x
                    for x, flag in (
                        ("REAL", sid in real_ids),
                        ("SIMULATION", sid in sim_ids),
                    )
                    if flag
                ],
                "metrics": metrics,
                "missing_requirements": missing,
                "capital_hurdle": CAPITAL_HURDLE,
                "cash_hurdle": CASH_HURDLE,
                "trade_authority": TRADE_AUTHORITY,
            }
        )
    ranked = [r for r in rows if r.get("metrics")]
    ranked.sort(
        key=lambda r: float(r["metrics"]["expected_return"]), reverse=True
    )
    ranks = {r["security_id"]: i + 1 for i, r in enumerate(ranked)}
    peer_returns = [float(r["metrics"]["expected_return"]) for r in ranked]
    peer_median = (
        sorted(peer_returns)[len(peer_returns) // 2] if peer_returns else None
    )
    for row in rows:
        row["rank_among_current_d2"] = ranks.get(row["security_id"])
        row["peer_expected_return_median"] = peer_median
        row["comparison_vector"] = {
            "expected_return": row["metrics"]["expected_return"]
            if row.get("metrics")
            else None,
            "bear_downside": row["metrics"]["bear_downside"]
            if row.get("metrics")
            else None,
            "confidence": row["metrics"]["confidence"]
            if row.get("metrics")
            else None,
            "existing_position": row["existing_position"],
            "cash_hurdle": CASH_HURDLE,
            "capital_hurdle": CAPITAL_HURDLE,
        }
    fingerprint = canonical_hash(
        {
            "source_d2_state_id": d2.get("state_id"),
            "rows": rows,
        }
    )
    return {
        "schema_version": "2.0.0",
        "state_id": f"CAPITAL_COMPARISON_CURRENT_{fingerprint[:16]}",
        "generated_at_utc": now.replace(microsecond=0).isoformat(),
        "status": "PASS_LIVE_CAPITAL_COMPARISON",
        "source_d2_state_id": d2.get("state_id"),
        "coverage": {
            "d2_subject_count": len(rows),
            "decision_grade_underwriting_count": len(ranked),
            "real_position_state_bound": bool(real_positions),
            "simulation_position_state_bound": bool(simulation_positions),
            "portfolio_comparison_boundary": (
                "Current D2 subjects are ranked explicitly; holdings without D2 "
                "underwriting remain outside expected-return comparison rather than "
                "receiving invented returns."
            ),
        },
        "rows": rows,
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }


def build_recommendations(
    d2: dict[str, Any],
    comparison: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    comp_by_id = {
        str(r.get("security_id")): r for r in comparison.get("rows", [])
    }
    rows: list[dict[str, Any]] = []
    for d2row in d2.get("queue", []):
        sid = str(d2row.get("security_id") or "")
        comp = comp_by_id.get(sid, {})
        cstatus = str(
            comp.get("comparison_status") or "UNDERWRITING_PENDING"
        )
        existing = bool(comp.get("existing_position"))
        metrics = comp.get("metrics") or {}
        explicit_position_action = str(
            (d2row.get("underwriting") or {}).get("action") or ""
        ).upper()
        explicit_position_action = {
            "TRIM_REVIEW": "TRIM",
            "EXIT_REVIEW": "EXIT",
        }.get(explicit_position_action, explicit_position_action)
        if rejection_triggered(d2row.get("first_rejection_test")):
            action = "EXIT" if existing else "AVOID"
        elif existing and explicit_position_action in {"ADD", "HOLD", "TRIM", "EXIT"}:
            action = explicit_position_action
        elif cstatus == "EVIDENCE_BLOCKED":
            action = "WATCH_FOR_EVIDENCE"
        elif cstatus in {"UNDERWRITING_PENDING", "UNDERWRITING_INCOMPLETE"}:
            action = "WATCH"
        elif cstatus == "AVOID_INVALIDATION_TRIGGERED":
            action = "EXIT" if existing else "AVOID"
        elif cstatus == "AVOID_NEGATIVE_EXPECTED_RETURN":
            action = "TRIM" if existing else "AVOID"
        elif cstatus == "PASS_NEW_CAPITAL":
            action = "ADD" if existing else "BUY"
        elif cstatus == "PRICE_BLOCKED":
            action = "HOLD" if existing else "BUY_BELOW"
        else:
            action = "HOLD" if existing else "WATCH"
        ready = action in {"BUY", "ADD", "TRIM", "EXIT"}
        rows.append(
            {
                "security_id": sid,
                "security_name": d2row.get("security_name"),
                "action": action,
                "current_price": metrics.get("current_price"),
                "entry_price": metrics.get("entry_price"),
                "base_value": metrics.get("base_value"),
                "probability_weighted_value": metrics.get(
                    "probability_weighted_value"
                ),
                "expected_return": metrics.get("expected_return"),
                "bear_downside": metrics.get("bear_downside"),
                "confidence": metrics.get("confidence"),
                "top_reasons": [
                    str(
                        d2row.get("research_disposition")
                        or d2row.get("status")
                        or ""
                    ),
                    (
                        f"D2_EXPLICIT_POSITION_ACTION_{explicit_position_action}"
                        if existing
                        and explicit_position_action in {"ADD", "HOLD", "TRIM", "EXIT"}
                        else cstatus
                    ),
                    (
                        f"D2_CAPITAL_RANK_{comp.get('rank_among_current_d2')}"
                        if comp.get("rank_among_current_d2")
                        else "NO_DECISION_GRADE_CAPITAL_RANK"
                    ),
                ],
                "top_blocker": (
                    comp.get("missing_requirements", [None])[0]
                    if comp.get("missing_requirements")
                    else (cstatus if cstatus != "PASS_NEW_CAPITAL" else None)
                ),
                "kill_thesis": metrics.get("kill_thesis")
                or d2row.get("first_rejection"),
                "catalysts": metrics.get("catalysts") or [],
                "portfolio_implication": (
                    "EXISTING_POSITION"
                    if existing
                    else "NEW_CAPITAL_CANDIDATE"
                ),
                "ready_for_user_decision": ready,
                "orders": 0,
                "trade_authority": TRADE_AUTHORITY,
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    fingerprint = canonical_hash(
        {
            "source_d2_state_id": d2.get("state_id"),
            "comparison_state_id": comparison.get("state_id"),
            "rows": rows,
        }
    )
    return {
        "schema_version": "2.0.0",
        "state_id": f"RECOMMENDATION_CURRENT_{fingerprint[:16]}",
        "generated_at_utc": now.replace(microsecond=0).isoformat(),
        "status": "PASS_S2_RECOMMENDATION",
        "source_d2_state_id": d2.get("state_id"),
        "source_capital_comparison_state_id": comparison.get("state_id"),
        "summary": {
            "subject_count": len(rows),
            "action_counts": counts,
            "ready_for_user_decision_count": sum(
                bool(r["ready_for_user_decision"]) for r in rows
            ),
        },
        "records": rows,
        "controls": {
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "user_decisions_generated": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    p1 = sub.add_parser("opportunity-d1")
    p1.add_argument("--screening-longlist", required=True)
    p1.add_argument("--screen-source", required=True)
    p1.add_argument("--prior-d1")
    p1.add_argument("--financial-score")
    p1.add_argument("--output-dir", required=True)

    p2 = sub.add_parser("decision")
    p2.add_argument("--d2-current", required=True)
    p2.add_argument("--real-positions", required=True)
    p2.add_argument("--simulation-positions", required=True)
    p2.add_argument(
        "--semantic-d2-dir",
        "--holding-d2-dir",
        dest="semantic_d2_dir",
    )
    p2.add_argument("--output-dir", required=True)

    args = parser.parse_args()
    out = Path(args.output_dir)
    if args.mode == "opportunity-d1":
        longlist = read_longlist(Path(args.screening_longlist))
        source = load_json(Path(args.screen_source))
        fin_rows = None
        if args.financial_score:
            import pandas as pd

            fin_rows = pd.read_parquet(args.financial_score).to_dict("records")
        opportunity = build_opportunity_queue(
            longlist, screen_source=source, financial_rows=fin_rows
        )
        d1 = build_d1(
            opportunity,
            prior_d1=load_json(Path(args.prior_d1))
            if args.prior_d1
            else {},
        )
        write_json(out / "OPPORTUNITY_CURRENT.json", opportunity)
        write_json(out / "D1_CURRENT.json", d1)
        print(
            json.dumps(
                {
                    "status": "PASS_OPPORTUNITY_D1",
                    "opportunities": opportunity["opportunity_count"],
                    "d1": d1["batch_size"],
                    "advance_to_d2": d1["routing_summary"][
                        "advance_to_d2_count"
                    ],
                    "orders": 0,
                    "trade_authority": "NONE",
                }
            )
        )
        return 0

    d2 = load_json(Path(args.d2_current))
    real = load_json(Path(args.real_positions))
    sim = load_json(Path(args.simulation_positions))
    semantic_rows = load_latest_semantic_d2(
        Path(args.semantic_d2_dir) if args.semantic_d2_dir else None
    )
    d2 = merge_d2_with_semantic_research(
        d2,
        semantic_rows,
        holding_ids=position_ids(real) | position_ids(sim),
    )
    comparison = build_capital_comparison(
        d2, real_positions=real, simulation_positions=sim
    )
    recommendation = build_recommendations(d2, comparison)
    write_json(out / "CAPITAL_COMPARISON_CURRENT.json", comparison)
    write_json(out / "RECOMMENDATION_CURRENT.json", recommendation)
    print(
        json.dumps(
            {
                "status": "PASS_DECISION",
                "subjects": recommendation["summary"]["subject_count"],
                "carried_forward_semantic_d2": d2.get("carried_forward_semantic_d2_count", 0),
                "supplemental_holding_d2": d2.get("supplemental_holding_d2_count", 0),
                "actions": recommendation["summary"]["action_counts"],
                "orders": 0,
                "trade_authority": "NONE",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
