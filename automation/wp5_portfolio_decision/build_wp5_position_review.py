#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REAL_POSITIONS = "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM_POSITIONS = "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
CANDIDATE_CURRENT = "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
WP5_DECISION = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_PORTFOLIO_DECISION_CURRENT.json"
WP5_QUEUE = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json"
WP5_REVIEW = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_POSITION_REVIEW_CURRENT.json"
EXECUTION_REGISTER = "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
ASSET_REGISTRY = "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"

CORE2 = {"000333.SZ", "600900.SH"}


def read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def security_id(record: dict[str, Any]) -> str | None:
    if record.get("security_id"):
        return str(record["security_id"])
    code = record.get("security_code") or record.get("stock_code") or record.get("code")
    if code is None:
        return None
    text = str(code).zfill(6)
    if text.startswith(("5", "6")):
        return f"{text}.SH"
    if text.startswith(("4", "8", "92")):
        return f"{text}.BJ"
    return f"{text}.SZ"


def candidate_sections(candidate: dict[str, Any]) -> dict[str, set[str]]:
    sections: dict[str, set[str]] = {}
    for key, value in candidate.items():
        if not isinstance(value, list):
            continue
        ids = {sid for item in value if isinstance(item, dict) and (sid := security_id(item))}
        if ids:
            sections[key] = ids
    return sections


def candidate_lane(sid: str, sections: dict[str, set[str]]) -> str:
    if sid in sections.get("candidate_core_members", set()):
        return "CANDIDATE_CORE"
    matched = [key for key, ids in sections.items() if sid in ids]
    text = "|".join(matched).lower()
    if "research" in text or "queue" in text:
        return "RESEARCH_QUEUE_OR_RESEARCH_OBJECT"
    if "shadow" in text:
        return "SHADOW_TRACK"
    if "historical" in text or "archive" in text:
        return "HISTORICAL_CANDIDATE_ARCHIVE"
    if matched:
        return "CANDIDATE_RELATED_OTHER"
    return "NOT_FOUND_IN_CANDIDATE_CURRENT"


def parse_target_weight(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 100.0 if number > 1.0 else number
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        try:
            return float(text[:-1]) / 100.0
        except ValueError:
            return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100.0 if number > 1.0 else number


def real_review(real: dict[str, Any]) -> dict[str, Any]:
    total = float(real["summary"]["account_total_assets"])
    rows = []
    by_asset: dict[str, float] = {}
    for holding in real["holdings"]:
        value = float(holding["market_value"])
        by_asset[holding["asset_class"]] = by_asset.get(holding["asset_class"], 0.0) + value
        rows.append({
            "security_id": holding["security_id"],
            "security_name": holding["security_name"],
            "asset_class": holding["asset_class"],
            "market_value": value,
            "current_weight": round(value / total, 8),
            "unrealized_pnl": holding["unrealized_pnl"],
            "unrealized_pnl_pct": holding["unrealized_pnl_pct"],
            "mark_as_of": holding["mark_as_of"],
            "broker_verified": holding["broker_verified"],
            "provisional_judgment": "HOLD_REVIEW_ONLY_NO_AUTOMATIC_CHANGE",
            "implementation_ready": False,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": "NONE",
        })

    s_and_p = [row for row in rows if row["security_id"] in {"159612.SZ", "159655.SZ"}]
    bond_rows = [row for row in rows if row["asset_class"] == "BOND_FUND"]
    a_share_etfs = [row for row in rows if row["asset_class"] == "A_SHARE_ETF"]
    findings = [
        {
            "finding_id": "REAL-BOND-SLEEVE-CONCENTRATION",
            "exposure_weight": round(sum(row["market_value"] for row in bond_rows) / total, 8),
            "position_count": len(bond_rows),
            "judgment": "HOLD_PENDING_LOOKTHROUGH_OVERLAP_DURATION_AND_CREDIT_REVIEW",
            "automatic_action": False,
        },
        {
            "finding_id": "REAL-SP500-DUPLICATE-EXPOSURE",
            "security_ids": [row["security_id"] for row in s_and_p],
            "combined_weight": round(sum(row["market_value"] for row in s_and_p) / total, 8),
            "judgment": "CONSOLIDATION_REVIEW_ONLY_NO_FORCED_SALE",
            "automatic_action": False,
        },
        {
            "finding_id": "REAL-A-SHARE-ETF-ROLE-OVERLAP",
            "security_ids": [row["security_id"] for row in a_share_etfs],
            "combined_weight": round(sum(row["market_value"] for row in a_share_etfs) / total, 8),
            "judgment": "CLARIFY_A500_VS_CSI500_ROLE_BEFORE_REALLOCATION",
            "automatic_action": False,
        },
    ]
    return {
        "account_total_assets": total,
        "execution_cash_balance": real["summary"]["execution_cash_balance"],
        "cash_policy": real["cash_policy"],
        "fixed_strategic_cash_target": False,
        "asset_class_weights": {key: round(value / total, 8) for key, value in sorted(by_asset.items())},
        "positions": rows,
        "structural_findings": findings,
        "implementation_ready": False,
    }


def simulation_judgment(
    holding: dict[str, Any],
    current_weight: float,
    target_weight: float | None,
    lane: str,
    core2_decision: dict[str, Any] | None,
) -> tuple[str, str, list[str]]:
    sid = holding["security_id"]
    raw_target = str(holding.get("target_weight") or "").strip().lower()
    pnl_pct = float(holding["unrealized_pnl_pct"])
    reasons: list[str] = []

    if sid in CORE2 and core2_decision:
        return (
            "P1_CORE2_CONDITIONAL",
            core2_decision["provisional_judgment"],
            list(core2_decision["binding_constraints"]),
        )
    if raw_target == "reduced":
        reasons.extend(["LEGACY_TARGET_LABEL_REDUCED", "WP4B_DECISION_GRADE_RESEARCH_NOT_AVAILABLE"])
        if pnl_pct <= -0.20:
            reasons.append("DRAWDOWN_BELOW_MINUS_20_PERCENT")
        return "P0_TRIM_OR_EXIT_REUNDERWRITE", "TRIM_OR_EXIT_REVIEW_REQUIRED_NO_AUTOMATIC_SALE", reasons
    if raw_target == "review":
        reasons.extend(["LEGACY_TARGET_LABEL_REVIEW", "WP4B_DECISION_GRADE_RESEARCH_NOT_AVAILABLE"])
        if pnl_pct <= -0.15:
            reasons.append("DRAWDOWN_BELOW_MINUS_15_PERCENT")
        return "P0_FULL_THESIS_REUNDERWRITE", "HOLD_NO_ADD_PENDING_FULL_THESIS_REUNDERWRITE", reasons
    if holding["security_id"] == "510500.SH":
        reasons.extend(["BENCHMARK_ETF_ROLE", "TARGET_GAP_NOT_AN_AUTOMATIC_CASH_DEPLOYMENT_SIGNAL"])
        return "P2_BENCHMARK_ROLE_REVIEW", "HOLD_BENCHMARK_ROLE_REVIEW_NO_AUTOMATIC_TOP_UP", reasons

    reasons.append("WP4B_DECISION_GRADE_RESEARCH_NOT_AVAILABLE")
    reasons.append(f"CANDIDATE_LANE_{lane}")
    if pnl_pct <= -0.15:
        reasons.append("DRAWDOWN_BELOW_MINUS_15_PERCENT")
        return "P1_LOSS_AND_THESIS_REVIEW", "HOLD_NO_ADD_PENDING_THESIS_AND_VALUATION_REFRESH", reasons
    if target_weight is not None:
        gap = current_weight - target_weight
        if gap > 0.01:
            reasons.append("WEIGHT_ABOVE_REFERENCE_BY_MORE_THAN_1_PERCENT")
            return "P1_TRIM_REVIEW", "TRIM_REVIEW_PENDING_RESEARCH_REFRESH", reasons
        if gap < -0.01:
            reasons.append("WEIGHT_BELOW_REFERENCE_BY_MORE_THAN_1_PERCENT")
            return "P2_UNDERWEIGHT_REVIEW", "UNDERWEIGHT_NO_ADD_PENDING_RESEARCH_REFRESH", reasons
    return "P2_HOLD_REVIEW", "HOLD_PENDING_RESEARCH_REFRESH", reasons


def simulation_review(
    simulation: dict[str, Any],
    sections: dict[str, set[str]],
    decision: dict[str, Any],
) -> dict[str, Any]:
    total = float(simulation["summary"]["account_total_assets"])
    core2 = decision["simulation"]["core2"]
    rows = []
    buckets: dict[str, int] = {}
    for holding in simulation["holdings"]:
        sid = holding["security_id"]
        current_weight = float(holding["market_value"]) / total
        target_weight = parse_target_weight(holding.get("target_weight"))
        lane = candidate_lane(sid, sections)
        priority, judgment, reasons = simulation_judgment(
            holding,
            current_weight,
            target_weight,
            lane,
            core2.get(sid),
        )
        buckets[priority] = buckets.get(priority, 0) + 1
        rows.append({
            "security_id": sid,
            "security_name": holding["security_name"],
            "portfolio_bucket": holding.get("portfolio_bucket"),
            "market_value": holding["market_value"],
            "current_weight": round(current_weight, 8),
            "target_weight_raw": holding.get("target_weight"),
            "target_weight_reference": target_weight,
            "weight_gap_to_reference": None if target_weight is None else round(current_weight - target_weight, 8),
            "unrealized_pnl": holding["unrealized_pnl"],
            "unrealized_pnl_pct": holding["unrealized_pnl_pct"],
            "candidate_lane": lane,
            "research_coverage": "WP4B_HARDENED" if sid in CORE2 else "NOT_WP4B_DECISION_GRADE",
            "review_priority": priority,
            "provisional_judgment": judgment,
            "reason_codes": reasons,
            "implementation_ready": False,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": "NONE",
        })

    rows.sort(key=lambda row: (row["review_priority"], -abs(float(row["unrealized_pnl_pct"]))))
    top_positions = sorted(rows, key=lambda row: row["current_weight"], reverse=True)[:5]
    return {
        "account_total_assets": total,
        "execution_cash_balance": simulation["summary"]["execution_cash_balance"],
        "execution_cash_weight": round(float(simulation["summary"]["execution_cash_balance"]) / total, 8),
        "holding_count": len(rows),
        "wp4b_hardened_position_count": sum(row["research_coverage"] == "WP4B_HARDENED" for row in rows),
        "non_wp4b_position_count": sum(row["research_coverage"] != "WP4B_HARDENED" for row in rows),
        "review_priority_counts": dict(sorted(buckets.items())),
        "top_five_positions": [
            {"security_id": row["security_id"], "security_name": row["security_name"], "current_weight": row["current_weight"]}
            for row in top_positions
        ],
        "positions": rows,
        "portfolio_findings": [
            {
                "finding_id": "SIM-RESEARCH-COVERAGE-GAP",
                "judgment": "14_OF_16_POSITIONS_LACK_WP4B_DECISION_GRADE_RESEARCH",
                "action": "RESEARCH_TRIAGE_BEFORE_REBALANCE",
            },
            {
                "finding_id": "SIM-CASH-NOT-AUTOMATIC-DEPLOYMENT-MANDATE",
                "cash_weight": round(float(simulation["summary"]["execution_cash_balance"]) / total, 8),
                "judgment": "CASH_IS_AVAILABLE_BUT_NOT_A_SIGNAL_TO_FORCE_BUYS",
                "action": "DEPLOY_ONLY_AFTER_POSITION_AND_CANDIDATE_GATES",
            },
        ],
        "implementation_ready": False,
    }


def register_asset(registry: dict[str, Any]) -> None:
    payload = {
        "asset_id": "WP5_POSITION_REVIEW_CURRENT",
        "authority": "GOVERNED_BRANCH_CANDIDATE",
        "format": "JSON",
        "location": WP5_REVIEW,
        "role": "WP5 full Real and Simulation position review baseline",
        "status": "CURRENT_BRANCH_CANDIDATE",
        "trade_authority": "NONE",
    }
    assets = registry.setdefault("assets", [])
    if isinstance(assets, list):
        existing = next((item for item in assets if isinstance(item, dict) and item.get("asset_id") == payload["asset_id"]), None)
        if existing is None:
            assets.append(payload)
        else:
            existing.update(payload)
    elif isinstance(assets, dict):
        assets["wp5_position_review_current"] = payload
    else:
        raise TypeError(type(assets).__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    now = datetime.now(timezone.utc).isoformat()

    real = read_json(root, REAL_POSITIONS)
    simulation = read_json(root, SIM_POSITIONS)
    candidate = read_json(root, CANDIDATE_CURRENT)
    decision = read_json(root, WP5_DECISION)
    queue = read_json(root, WP5_QUEUE)
    execution = read_json(root, EXECUTION_REGISTER)
    registry = read_json(root, ASSET_REGISTRY)

    sections = candidate_sections(candidate)
    real_output = real_review(real)
    simulation_output = simulation_review(simulation, sections, decision)
    assert len(real_output["positions"]) == 7
    assert len(simulation_output["positions"]) == 16
    assert simulation_output["wp4b_hardened_position_count"] == 2
    assert simulation_output["non_wp4b_position_count"] == 14

    output = {
        "state_id": "WP5_POSITION_REVIEW_CURRENT",
        "generated_at": now,
        "status": "FULL_POSITION_REVIEW_BASELINE_COMPLETE_NOT_IMPLEMENTATION_READY",
        "review_scope": "7_REAL_HOLDINGS_AND_16_SIMULATION_HOLDINGS",
        "real_account": real_output,
        "simulation": simulation_output,
        "portfolio_level_conclusion": {
            "real_account": "STRUCTURE_CAN_BE_REVIEWED_BUT_NO_REAL_ACTION_WITHOUT_FRESH_MARKS_AND_USER_POSITION_VERIFICATION",
            "simulation": "DO_NOT_REBALANCE_FROM_PNL_OR_LEGACY_TARGET_LABELS_ALONE;TRIAGE_RESEARCH_GAPS_FIRST",
            "candidate": "ONLY_CORE2_HAS_WP4B_HARDENED_RESEARCH_AND_NEITHER_NAME_IS_IMPLEMENTATION_READY",
        },
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }

    existing_items = [item for item in queue.get("items", []) if item.get("queue_id") != "WP5-Q4"]
    existing_items.extend([
        {
            "queue_id": "WP5-Q4A",
            "subject": "Simulation P0 re-underwrite",
            "required_evidence": "Re-underwrite positions carrying legacy target labels reduced or review before any trim, exit or add proposal",
            "status": "PENDING",
        },
        {
            "queue_id": "WP5-Q4B",
            "subject": "Simulation non-Core2 research triage",
            "required_evidence": "Prioritize the remaining non-WP4B holdings by loss, weight gap, candidate lane and portfolio role",
            "status": "PENDING",
        },
        {
            "queue_id": "WP5-Q5",
            "subject": "Real account overlap review",
            "required_evidence": "Review three bond funds, duplicate S&P 500 ETFs and A500/CSI500 role overlap before any simplification proposal",
            "status": "PENDING",
        },
    ])
    queue["items"] = existing_items
    queue["status"] = "FULL_POSITION_REVIEW_COMPLETE_PREPARATION_QUEUE_NO_IMPLEMENTATION_READY_ITEMS"
    queue["ready_for_user_decision_count"] = 0
    queue["orders"] = 0
    queue["trade_authority"] = "NONE"

    decision["full_position_review_path"] = WP5_REVIEW
    decision["full_position_review_complete"] = True
    decision["simulation"]["wp4b_hardened_position_count"] = 2
    decision["simulation"]["non_wp4b_position_count"] = 14
    decision["simulation"]["review_priority_counts"] = simulation_output["review_priority_counts"]
    decision["readiness_blockers"] = [
        blocker for blocker in decision["readiness_blockers"]
        if blocker != "FULL_POSITION_LEVEL_THESIS_AND_RISK_REVIEW_REQUIRED_BEFORE_SIMULATION_CHANGES"
    ] + [
        "P0_AND_NON_CORE2_RESEARCH_REUNDERWRITE_REQUIRED_BEFORE_SIMULATION_CHANGES",
        "REAL_ACCOUNT_OVERLAP_AND_LOOKTHROUGH_REVIEW_REQUIRED_BEFORE_REAL_CHANGES",
    ]

    execution["next_task"] = "WP5_P0_REUNDERWRITE_AND_FRESH_INPUT_REFRESH"
    execution["wp5"]["full_position_review_complete"] = True
    execution["wp5"]["position_review_path"] = WP5_REVIEW
    execution["wp5"]["next_gate"] = "P0_REUNDERWRITE_FRESH_MARKS_EVENT_STATUS_AND_USER_DELTA"
    execution["wp5"]["ready_for_user_decision_count"] = 0
    execution["wp5"]["position_mutation_allowed"] = False
    execution["wp5"]["order_execution_allowed"] = False

    register_asset(registry)
    write_json(root, WP5_REVIEW, output)
    write_json(root, WP5_QUEUE, queue)
    write_json(root, WP5_DECISION, decision)
    write_json(root, EXECUTION_REGISTER, execution)
    write_json(root, ASSET_REGISTRY, registry)

    print({
        "real_positions_reviewed": 7,
        "simulation_positions_reviewed": 16,
        "wp4b_hardened": 2,
        "research_gap": 14,
        "p0": sum(value for key, value in simulation_output["review_priority_counts"].items() if key.startswith("P0_")),
        "ready_for_user_decision": 0,
        "orders": 0,
    })


if __name__ == "__main__":
    main()
