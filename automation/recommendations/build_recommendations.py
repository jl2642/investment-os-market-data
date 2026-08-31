from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

REAL_POSITIONS = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM_POSITIONS = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"

TRADE_AUTHORITY = "NONE"
OPPORTUNITY_STATES = {
    "BUY_NOW",
    "BUY_ON_PRICE",
    "BUY_ON_EVIDENCE",
    "WATCH_HIGH_PRIORITY",
    "WATCH_NORMAL",
    "AVOID",
}
POSITION_STATES = {"ADD", "HOLD", "TRIM_REVIEW", "EXIT_REVIEW"}
ALL_STATES = OPPORTUNITY_STATES | POSITION_STATES
MARKETS = ("A_SHARE", "H_SHARE", "US_SHARE")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_hash(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def market_from_security_id(security_id: str) -> str:
    sid = security_id.upper()
    if sid.startswith("HKEX:") or sid.endswith(".HK"):
        return "H_SHARE"
    if sid.endswith(".SZ") or sid.endswith(".SH") or sid.startswith("SSE:") or sid.startswith("SZSE:"):
        return "A_SHARE"
    return "US_SHARE"


def split_triggers(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def rejection_triggered(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return False
    if text.startswith("NOT_") or text.startswith("NO_"):
        return False
    return text.startswith("TRIGGERED") or text.startswith("FAIL") or "INVALIDATED" in text


def comparison_lookup(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("security_id")): row
        for row in pack.get("blocked", [])
        if row.get("security_id")
    }


def position_lookup(real: dict[str, Any], simulation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for account, payload in (("REAL", real), ("SIMULATION", simulation)):
        for row in payload.get("holdings", []):
            sid = str(row.get("security_id") or "")
            if not sid:
                continue
            item = dict(row)
            item["_account"] = account
            out.setdefault(sid, []).append(item)
    return out


def position_status(
    security_id: str,
    positions: dict[str, list[dict[str, Any]]],
) -> tuple[str, str, bool, list[str]]:
    rows = positions.get(security_id, [])
    if not rows:
        return (
            "OPPORTUNITY",
            "NO_CURRENT_POSITION_AND_INCREMENTAL_PORTFOLIO_FIT_NOT_ESTABLISHED",
            False,
            [],
        )
    accounts = sorted({str(x.get("_account")) for x in rows})
    verified = bool(rows) and all(bool(x.get("broker_verified")) for x in rows)
    if not verified:
        return (
            "EXISTING_POSITION_CONTEXT_UNVERIFIED",
            "POSITION_CONTEXT_PRESENT_BROKER_UNVERIFIED_BLOCKS_POSITION_ACTION",
            False,
            accounts,
        )
    return (
        "EXISTING_POSITION_VERIFIED",
        "CURRENT_POSITION_CONTEXT_VERIFIED_FIT_REVIEW_REQUIRED",
        True,
        accounts,
    )


def evidence_status(d2: dict[str, Any]) -> tuple[str, bool]:
    status = str(d2.get("status") or "")
    gap = d2.get("evidence_gap")
    material_gap = status == "D2_RESEARCH_HOLD_EVIDENCE_GAP" or bool(gap)
    if material_gap:
        return "MATERIAL_EVIDENCE_GAP_ACTIVE", True
    if status == "D2_RESEARCH_COMPLETE":
        return "RESEARCH_COMPLETE_ACTIVE_GATES_REMAIN", False
    return "RESEARCH_INCOMPLETE_OR_UNRESOLVED", False


def valuation_status(comparison: dict[str, Any] | None, material_gap: bool) -> str:
    if material_gap:
        return "VALUATION_NOT_DECISION_READY_MATERIAL_EVIDENCE_GAP"
    if not comparison:
        return "CURRENT_ENTRY_BASIS_NOT_ESTABLISHED"
    reasons = set(comparison.get("reason_codes", []))
    valuation = comparison.get("valuation_context") or {}
    if valuation.get("live_exact_valuation_bound") is True:
        if "FRESH_NORMALIZED_VALUATION_ABSENT" in reasons:
            return "LIVE_EXACT_VALUATION_BOUND_NORMALIZED_VALUATION_STILL_REQUIRED"
        return "LIVE_EXACT_VALUATION_BOUND_OTHER_DECISION_GATES_REMAIN"
    if "FRESH_VALUATION_BINDING_ABSENT" in reasons:
        return "RESEARCH_VALUATION_CONTEXT_PRESENT_FRESH_BINDING_ABSENT"
    if "FRESH_NORMALIZED_VALUATION_ABSENT" in reasons:
        return "RESEARCH_VALUATION_CONTEXT_PRESENT_FRESH_NORMALIZED_BINDING_ABSENT"
    if comparison.get("gate_state") == "BLOCKED_MATERIAL_EVIDENCE":
        return "VALUATION_NOT_DECISION_READY_MATERIAL_EVIDENCE_GAP"
    return "CURRENT_ENTRY_BASIS_NOT_ESTABLISHED"


def capital_comparison_status(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return "UNAVAILABLE_NO_MATCHING_GOVERNED_COMPARISON_CONTEXT"
    gate = str(comparison.get("gate_state") or "UNKNOWN")
    if comparison.get("live_operating_authority") is True:
        return f"{gate}_LIVE_OPERATING_CONTEXT"
    return f"{gate}_GOVERNED_PHASE2C_CONTEXT_NOT_LIVE_AUTHORITY"


def current_explicit_gate(d2: dict[str, Any], name: str) -> bool:
    value = d2.get(name)
    return value is True


def route_state(
    *,
    d2: dict[str, Any],
    material_gap: bool,
    comparison: dict[str, Any] | None,
    verified_existing_position: bool,
    portfolio_fit_status_value: str,
) -> tuple[str, list[str]]:
    status = str(d2.get("status") or "")
    disposition = str(d2.get("research_disposition") or "")
    reasons: list[str] = [status, disposition] if disposition else [status]

    first_rejection = d2.get("first_rejection_test")
    if rejection_triggered(first_rejection):
        reasons.append("FIRST_REJECTION_OR_INVALIDATION_TRIGGERED")
        if verified_existing_position:
            return "EXIT_REVIEW", reasons
        return "AVOID", reasons

    research_complete = status == "D2_RESEARCH_COMPLETE"
    no_material_gap = not material_gap
    explicit_entry_basis = current_explicit_gate(d2, "current_entry_basis_established")
    entry_trigger_satisfied = current_explicit_gate(d2, "entry_trigger_satisfied")
    explicit_portfolio_fit = current_explicit_gate(d2, "portfolio_fit_acceptable")
    explicit_capital_comparison = current_explicit_gate(d2, "capital_comparison_available")
    comparison_not_required = current_explicit_gate(d2, "capital_comparison_explicitly_not_required")
    buy_equivalent = all(
        (
            research_complete,
            no_material_gap,
            explicit_entry_basis,
            entry_trigger_satisfied,
            explicit_portfolio_fit,
            explicit_capital_comparison or comparison_not_required,
        )
    )

    if verified_existing_position:
        if current_explicit_gate(d2, "exit_review_trigger_active"):
            reasons.append("EXPLICIT_EXIT_REVIEW_TRIGGER_ACTIVE")
            return "EXIT_REVIEW", reasons
        if current_explicit_gate(d2, "trim_review_trigger_active"):
            reasons.append("EXPLICIT_TRIM_REVIEW_TRIGGER_ACTIVE")
            return "TRIM_REVIEW", reasons
        if buy_equivalent:
            reasons.append("ALL_INCREMENTAL_CAPITAL_GATES_EXPLICITLY_PASS")
            return "ADD", reasons
        reasons.append(portfolio_fit_status_value)
        return "HOLD", reasons

    if buy_equivalent:
        reasons.append("ALL_BUY_NOW_GATES_EXPLICITLY_PASS")
        return "BUY_NOW", reasons

    sole_blocker = str(d2.get("sole_material_decision_blocker") or "").upper()
    if (
        research_complete
        and no_material_gap
        and sole_blocker == "PRICE"
        and explicit_portfolio_fit
        and (explicit_capital_comparison or comparison_not_required)
    ):
        reasons.append("SOLE_MATERIAL_BLOCKER_PRICE")
        return "BUY_ON_PRICE", reasons

    if (
        not rejection_triggered(first_rejection)
        and sole_blocker == "EVIDENCE"
        and material_gap
        and explicit_entry_basis
        and explicit_portfolio_fit
        and (explicit_capital_comparison or comparison_not_required)
    ):
        reasons.append("SOLE_MATERIAL_BLOCKER_EVIDENCE")
        return "BUY_ON_EVIDENCE", reasons

    if material_gap:
        reasons.append("MATERIAL_EVIDENCE_GAP_REQUIRES_EXPLICIT_RECOVERY_TRIGGER")
        return "WATCH_HIGH_PRIORITY", reasons

    if research_complete:
        reasons.append("RESEARCH_COMPLETE_WITHOUT_DECISION_PROMOTION")
        if comparison:
            reasons.extend(str(x) for x in comparison.get("reason_codes", []))
        return "WATCH_NORMAL", reasons

    reasons.append("RESEARCH_NOT_DECISION_GRADE")
    return "WATCH_HIGH_PRIORITY", reasons


def build_record(
    *,
    d2: dict[str, Any],
    comparison: dict[str, Any] | None,
    positions: dict[str, list[dict[str, Any]]],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    sid = str(d2.get("security_id") or "")
    subject_type, portfolio_fit, verified_position, position_accounts = position_status(sid, positions)
    evidence, material_gap = evidence_status(d2)
    recommendation_state, basis = route_state(
        d2=d2,
        material_gap=material_gap,
        comparison=comparison,
        verified_existing_position=verified_position,
        portfolio_fit_status_value=portfolio_fit,
    )

    triggers = split_triggers(d2.get("next_gate"))
    if not triggers and material_gap:
        triggers = ["NEXT_PRIMARY_DISCLOSURE_OR_RESEARCH_EVIDENCE_UPDATE"]

    invalidation = []
    if d2.get("first_rejection"):
        invalidation.append(str(d2.get("first_rejection")))
    if d2.get("first_rejection_test"):
        invalidation.append(f"FIRST_REJECTION_TEST:{d2.get('first_rejection_test')}")

    comparison_reasons = list(comparison.get("reason_codes", [])) if comparison else []
    comparison_missing = list(comparison.get("missing_requirements", [])) if comparison else []

    ready_for_user_decision = recommendation_state in {
        "BUY_NOW",
        "ADD",
        "TRIM_REVIEW",
        "EXIT_REVIEW",
    }

    return {
        "security_id": sid,
        "security_name": d2.get("security_name"),
        "market": market_from_security_id(sid),
        "subject_type": subject_type,
        "recommendation_state": recommendation_state,
        "judgment_basis": list(dict.fromkeys(x for x in basis if x)),
        "research_status": {
            "d2_status": d2.get("status"),
            "research_disposition": d2.get("research_disposition"),
            "semantic_research_required": d2.get("semantic_research_required"),
        },
        "evidence_status": evidence,
        "valuation_status": valuation_status(comparison, material_gap),
        "portfolio_fit_status": portfolio_fit,
        "capital_comparison_status": capital_comparison_status(comparison),
        "triggers": triggers,
        "invalidation_conditions": invalidation,
        "portfolio_role": {
            "current_role": "UNASSIGNED_NO_CURRENT_PORTFOLIO_FIT"
            if not verified_position
            else "EXISTING_POSITION_REQUIRES_CURRENT_FIT_REVIEW",
            "research_archetype": d2.get("archetype"),
            "position_accounts": position_accounts,
        },
        "comparison_context": {
            "gate_state": comparison.get("gate_state") if comparison else None,
            "reason_codes": comparison_reasons,
            "missing_requirements": comparison_missing,
            "is_live_operating_authority": bool(
                comparison and comparison.get("live_operating_authority") is True
            ),
            "valuation_context": comparison.get("valuation_context") if comparison else None,
        },
        "source_bindings": source_snapshot,
        "source_watermarks": {
            "d2": d2.get("last_attempt_at"),
            "funnel": source_snapshot["opportunity_funnel"].get("watermark"),
            "real_positions": source_snapshot["real_positions"].get("watermark"),
            "simulation_positions": source_snapshot["simulation_positions"].get("watermark"),
            "capital_comparison_context": source_snapshot["capital_comparison_context"].get("watermark"),
        },
        "ready_for_user_decision": ready_for_user_decision,
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }


def semantic_projection(payload: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(payload))
    # Operational publication metadata must not change the investment judgment
    # identity when the governed source fingerprint is unchanged.
    for key in (
        "generated_at_utc",
        "prior_recommendation_fingerprint",
        "cycle_action",
        "overall_status",
    ):
        out.pop(key, None)
    return out


def build(
    *,
    funnel_path: Path,
    d2_path: Path,
    comparison_context_path: Path,
    d2_source_commit: str,
    comparison_context_source_id: str,
    prior_current_path: Path | None = None,
    real_positions_path: Path = REAL_POSITIONS,
    simulation_positions_path: Path = SIM_POSITIONS,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat()

    funnel = load_json(funnel_path)
    d2_current = load_json(d2_path)
    comparison_pack = load_json(comparison_context_path)
    real = load_json(real_positions_path)
    simulation = load_json(simulation_positions_path)

    funnel_d2_identity = str(
        funnel.get("source_snapshot", {}).get("D2", {}).get("source_identity") or ""
    )
    if funnel_d2_identity != d2_source_commit:
        raise RuntimeError(
            f"P43_UPSTREAM_FUNNEL_D2_MISMATCH:{funnel_d2_identity}:{d2_source_commit}"
        )

    cmp_hash = canonical_hash(
        {
            "mode": comparison_pack.get("mode"),
            "eligible": comparison_pack.get("eligible_non_reference_count"),
            "blocked": comparison_pack.get("blocked"),
            "controls": comparison_pack.get("controls"),
        }
    )
    real_projection = {
        "state_id": real.get("state_id"),
        "status": real.get("status"),
        "position_watermark": real.get("position_watermark"),
        "mark_watermark": real.get("mark_watermark"),
        "holdings": [
            {
                "security_id": x.get("security_id"),
                "quantity": x.get("quantity"),
                "broker_verified": x.get("broker_verified"),
                "position_source_as_of": x.get("position_source_as_of"),
                "mark_as_of": x.get("mark_as_of"),
            }
            for x in real.get("holdings", [])
        ],
    }
    sim_projection = {
        "state_id": simulation.get("state_id"),
        "status": simulation.get("status"),
        "position_watermark": simulation.get("position_watermark"),
        "mark_watermark": simulation.get("mark_watermark"),
        "holdings": [
            {
                "security_id": x.get("security_id"),
                "quantity": x.get("quantity"),
                "broker_verified": x.get("broker_verified"),
                "position_source_as_of": x.get("position_source_as_of"),
                "mark_as_of": x.get("mark_as_of"),
            }
            for x in simulation.get("holdings", [])
        ],
    }

    source_snapshot = {
        "opportunity_funnel": {
            "identity": funnel.get("cycle_fingerprint"),
            "watermark": funnel.get("generated_at_utc"),
            "overall_status": funnel.get("overall_status"),
        },
        "d2": {
            "identity": d2_source_commit,
            "watermark": d2_current.get("as_of"),
            "status": d2_current.get("status"),
        },
        "real_positions": {
            "identity": canonical_hash(real_projection),
            "watermark": real.get("position_watermark"),
            "status": real.get("status"),
        },
        "simulation_positions": {
            "identity": canonical_hash(sim_projection),
            "watermark": simulation.get("position_watermark"),
            "status": simulation.get("status"),
        },
        "capital_comparison_context": {
            "identity": cmp_hash,
            "source_id": comparison_context_source_id,
            "watermark": comparison_pack.get("generated_at"),
            "mode": comparison_pack.get("mode"),
            "live_operating_authority": bool(
                comparison_pack.get("live_operating_authority") is True
            ),
            "source_bindings": comparison_pack.get("source_bindings"),
        },
    }

    recommendation_fingerprint = canonical_hash(source_snapshot)
    prior = (
        load_json(prior_current_path)
        if prior_current_path and prior_current_path.exists()
        else {}
    )
    prior_fingerprint = prior.get("recommendation_fingerprint")
    cycle_action = (
        "ADVANCE_NEW_SOURCE_FINGERPRINT"
        if prior_fingerprint != recommendation_fingerprint
        else "NO_OP_SAME_SOURCE_FINGERPRINT"
    )

    positions = position_lookup(real, simulation)
    comparisons = comparison_lookup(comparison_pack)
    records = [
        build_record(
            d2=row,
            comparison=comparisons.get(str(row.get("security_id"))),
            positions=positions,
            source_snapshot=source_snapshot,
        )
        for row in d2_current.get("queue", [])
    ]
    records.sort(key=lambda x: (x["market"], x["security_id"]))

    counts = Counter(row["recommendation_state"] for row in records)
    market_counts = Counter(row["market"] for row in records)
    market_coverage = []
    for market in MARKETS:
        count = int(market_counts.get(market, 0))
        market_coverage.append(
            {
                "market": market,
                "schema_supported": True,
                "current_subject_count": count,
                "status": (
                    "CURRENT_D2_OR_EQUIVALENT_INPUT_PRESENT"
                    if count
                    else "NO_CURRENT_D2_OR_EQUIVALENT_RESEARCH_INPUT"
                ),
            }
        )

    actionable = sum(
        counts.get(state, 0)
        for state in ("BUY_NOW", "ADD", "TRIM_REVIEW", "EXIT_REVIEW")
    )
    if cycle_action == "NO_OP_SAME_SOURCE_FINGERPRINT":
        overall_status = "NO_NEW_SOURCE_FINGERPRINT_CURRENT_PRESERVED"
    elif actionable:
        overall_status = "CURRENT_EXPLICIT_USER_REVIEW_ITEMS_PRESENT"
    else:
        overall_status = "CURRENT_EXPLICIT_NON_ACTIONABLE_JUDGMENTS"

    current = {
        "schema_version": "1.0.0",
        "surface_id": "P4_3_UNIFIED_RECOMMENDATION_CURRENT",
        "generated_at_utc": generated_at,
        "overall_status": overall_status,
        "recommendation_fingerprint": recommendation_fingerprint,
        "prior_recommendation_fingerprint": prior_fingerprint,
        "cycle_action": cycle_action,
        "source_snapshot": source_snapshot,
        "market_coverage": market_coverage,
        "summary": {
            "record_count": len(records),
            "state_counts": {state: int(counts.get(state, 0)) for state in sorted(ALL_STATES)},
            "ready_for_user_decision_count": sum(
                1 for row in records if row["ready_for_user_decision"]
            ),
            "buy_now_count": int(counts.get("BUY_NOW", 0)),
            "buy_on_price_count": int(counts.get("BUY_ON_PRICE", 0)),
            "buy_on_evidence_count": int(counts.get("BUY_ON_EVIDENCE", 0)),
        },
        "records": records,
        "controls": {
            "new_scalar_recommendation_score": 0,
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_mutations": 0,
            "target_portfolio_writebacks": 0,
            "user_decisions_generated": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }
    current["semantic_hash"] = canonical_hash(semantic_projection(current))

    explain = {
        "schema_version": "1.0.0",
        "surface_id": "P4_3_RECOMMENDATION_EXPLAIN_CURRENT",
        "generated_at_utc": generated_at,
        "recommendation_fingerprint": recommendation_fingerprint,
        "routing_policy": {
            "d2_research_complete_alone_may_trigger_buy": False,
            "stale_historical_decision_labels_are_current_authority": False,
            "missing_required_inputs_silently_filled": False,
            "global_scalar_recommendation_score": None,
            "realized_outcomes_used": False,
        },
        "legacy_surface_treatment": [
            {
                "surface": "WP4_DECISION_INTERFACE_CURRENT",
                "treatment": "HISTORICAL_CONTEXT_NOT_CURRENT_RECOMMENDATION_AUTHORITY",
            },
            {
                "surface": "DECISION_PROPOSALS_CURRENT",
                "treatment": "HISTORICAL_LKG_NOT_ACTIONABLE",
            },
            {
                "surface": "R3_POSITION_ACTION_MATRIX_CURRENT",
                "treatment": "DEVELOPMENT_SCENARIO_LIBRARY_ONLY",
            },
            {
                "surface": "WP5_PORTFOLIO_DECISION_CURRENT",
                "treatment": "CONTEXT_ONLY_UNLESS_CURRENT_SOURCES_REVALIDATED",
            },
        ],
        "records": [
            {
                "security_id": row["security_id"],
                "recommendation_state": row["recommendation_state"],
                "judgment_basis": row["judgment_basis"],
                "triggers": row["triggers"],
                "invalidation_conditions": row["invalidation_conditions"],
                "capital_comparison_status": row["capital_comparison_status"],
                "portfolio_fit_status": row["portfolio_fit_status"],
            }
            for row in records
        ],
        "controls": current["controls"],
    }

    receipt = {
        "schema_version": "1.0.0",
        "generated_at_utc": generated_at,
        "recommendation_fingerprint": recommendation_fingerprint,
        "prior_recommendation_fingerprint": prior_fingerprint,
        "cycle_action": cycle_action,
        "semantic_hash": current["semantic_hash"],
        "source_snapshot": source_snapshot,
        "summary": current["summary"],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return current, explain, receipt


def validate_payloads(
    current: dict[str, Any],
    explain: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "security_id",
        "security_name",
        "market",
        "subject_type",
        "recommendation_state",
        "judgment_basis",
        "research_status",
        "evidence_status",
        "valuation_status",
        "portfolio_fit_status",
        "capital_comparison_status",
        "triggers",
        "invalidation_conditions",
        "portfolio_role",
        "source_bindings",
        "source_watermarks",
        "ready_for_user_decision",
        "orders",
        "trade_authority",
    }

    records = current.get("records", [])
    for row in records:
        missing = required_fields - set(row)
        if missing:
            errors.append(
                f"P43_REQUIRED_FIELDS:{row.get('security_id')}:{','.join(sorted(missing))}"
            )
        state = row.get("recommendation_state")
        if state not in ALL_STATES:
            errors.append(f"P43_STATE:{row.get('security_id')}:{state}")
        if row.get("orders") != 0 or row.get("trade_authority") != TRADE_AUTHORITY:
            errors.append(f"P43_AUTHORITY:{row.get('security_id')}")
        if (
            row.get("research_status", {}).get("d2_status")
            == "D2_RESEARCH_HOLD_EVIDENCE_GAP"
            and state in {"BUY_NOW", "BUY_ON_PRICE", "ADD"}
        ):
            errors.append(f"P43_EVIDENCE_GAP_BUY:{row.get('security_id')}")
        if state in {"BUY_NOW", "ADD"}:
            d2_status = row.get("research_status", {}).get("d2_status")
            if d2_status != "D2_RESEARCH_COMPLETE":
                errors.append(f"P43_BUY_RESEARCH_NOT_COMPLETE:{row.get('security_id')}")
            if row.get("evidence_status") == "MATERIAL_EVIDENCE_GAP_ACTIVE":
                errors.append(f"P43_BUY_EVIDENCE_GAP:{row.get('security_id')}")
            if "NOT_ESTABLISHED" in str(row.get("portfolio_fit_status")):
                errors.append(f"P43_BUY_PORTFOLIO_FIT:{row.get('security_id')}")
            if "BLOCKED" in str(row.get("capital_comparison_status")):
                errors.append(f"P43_BUY_COMPARISON:{row.get('security_id')}")

    coverage = {row.get("market") for row in current.get("market_coverage", [])}
    if coverage != set(MARKETS):
        errors.append("P43_MARKET_COVERAGE")

    controls = current.get("controls", {})
    for key in (
        "new_scalar_recommendation_score",
        "candidate_membership_mutations",
        "real_account_mutations",
        "simulation_mutations",
        "target_portfolio_writebacks",
        "user_decisions_generated",
        "orders",
    ):
        if int(controls.get(key, 0)) != 0:
            errors.append(f"P43_CONTROL:{key}")
    if controls.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("P43_TRADE_AUTHORITY")

    if receipt.get("recommendation_fingerprint") != current.get("recommendation_fingerprint"):
        errors.append("P43_RECEIPT_FINGERPRINT")
    if receipt.get("semantic_hash") != current.get("semantic_hash"):
        errors.append("P43_RECEIPT_SEMANTIC_HASH")
    if explain.get("recommendation_fingerprint") != current.get("recommendation_fingerprint"):
        errors.append("P43_EXPLAIN_FINGERPRINT")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel-current", required=True)
    parser.add_argument("--d2-current", required=True)
    parser.add_argument("--comparison-context", required=True)
    parser.add_argument("--d2-source-commit", required=True)
    parser.add_argument("--comparison-context-source-id", required=True)
    parser.add_argument("--prior-current")
    parser.add_argument("--real-positions", default=str(REAL_POSITIONS))
    parser.add_argument("--simulation-positions", default=str(SIM_POSITIONS))
    parser.add_argument("--output-dir", default=".p4_3_output")
    parser.add_argument("--now")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    current, explain, receipt = build(
        funnel_path=Path(args.funnel_current),
        d2_path=Path(args.d2_current),
        comparison_context_path=Path(args.comparison_context),
        d2_source_commit=args.d2_source_commit,
        comparison_context_source_id=args.comparison_context_source_id,
        prior_current_path=Path(args.prior_current) if args.prior_current else None,
        real_positions_path=Path(args.real_positions),
        simulation_positions_path=Path(args.simulation_positions),
        now=now,
    )
    errors = validate_payloads(current, explain, receipt)
    if errors:
        raise SystemExit("\n".join(errors))

    out = Path(args.output_dir)
    write_json(out / "RECOMMENDATION_CURRENT.json", current)
    write_json(out / "RECOMMENDATION_EXPLAIN_CURRENT.json", explain)
    write_json(out / "cycle_receipt.json", receipt)

    print(
        json.dumps(
            {
                "status": current["overall_status"],
                "fingerprint": current["recommendation_fingerprint"],
                "cycle_action": current["cycle_action"],
                "state_counts": current["summary"]["state_counts"],
                "ready_for_user_decision_count": current["summary"][
                    "ready_for_user_decision_count"
                ],
                "orders": 0,
                "trade_authority": TRADE_AUTHORITY,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
