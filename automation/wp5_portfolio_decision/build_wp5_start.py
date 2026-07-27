#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


R2_ACCEPTANCE = "investment_os_runtime/00_CONTROL/R2_PRODUCT_CAPABILITY_ACCEPTANCE_CURRENT.json"
EXECUTION_REGISTER = "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
ASSET_REGISTRY = "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"
REAL_POSITIONS = "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM_POSITIONS = "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
CANDIDATE_CURRENT = "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
LEGACY_DECISIONS = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"
WP4B_SCENARIOS = "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP4_B/CORE2/WP4B_SCENARIO_MODELS_CURRENT.json"
WP4B_POSITION_FIT = "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP4_B/CORE2/WP4B_POSITION_FIT_CURRENT.json"
WP4B_EVENTS = "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP4_B/CORE2/WP4B_EVENT_MONITORING_CURRENT.json"

WP5_CONTRACT = "investment_os_runtime/00_CONTROL/WP5_PORTFOLIO_DECISION_CONTRACT.json"
WP5_START = "investment_os_runtime/00_CONTROL/WP5_START_RECORD_CURRENT.json"
WP5_INPUT = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_DECISION_INPUT_CURRENT.json"
WP5_DECISION = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_PORTFOLIO_DECISION_CURRENT.json"
WP5_QUEUE = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json"

CORE2 = ("000333.SZ", "600900.SH")
R2_CAPABILITY_MERGE_SHA = "33a5484f2ca919e80eef96a6750f801f751f8bdf"
R2_CLOSURE_MERGE_SHA = "17db72e866bff027e1f786a8fd0c051ddfcd6c3a"


def read_json(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def file_sha256(root: Path, relative: str) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def semantic_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scenario_map(model: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        row["scenario"]: {
            "implied_price": float(row["implied_price"]),
            "price_return_vs_current": float(row["price_return_vs_current"]),
            "exit_pe": float(row["exit_pe"]),
        }
        for row in model["cases"]
    }


def validate_scenario_scale(models: dict[str, Any]) -> None:
    expected = {
        "000333.SZ": {
            "market_cap": (600.0, 700.0),
            "shares": (7.0, 8.5),
            "prices": {"BEAR": (60.0, 75.0), "BASE": (85.0, 110.0), "BULL": (115.0, 140.0)},
        },
        "600900.SH": {
            "market_cap": (650.0, 760.0),
            "shares": (23.0, 26.0),
            "prices": {"BEAR": (18.0, 25.0), "BASE": (24.0, 31.0), "BULL": (30.0, 38.0)},
        },
    }
    for sid, limits in expected.items():
        model = models["models"][sid]
        market_cap = float(model["current_market_cap_rmb_bn"])
        shares = float(model["implied_share_count_bn"])
        assert limits["market_cap"][0] <= market_cap <= limits["market_cap"][1], (sid, market_cap)
        assert limits["shares"][0] <= shares <= limits["shares"][1], (sid, shares)
        cases = scenario_map(model)
        for case, band in limits["prices"].items():
            price = cases[case]["implied_price"]
            assert band[0] <= price <= band[1], (sid, case, price)
        assert model["provider_market_cap_unit"] == "CNY_10K"
        assert model["provider_market_cap_to_rmb_multiplier"] == 10_000.0


def group_market_value(holdings: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, float] = {}
    for holding in holdings:
        grouped[holding["asset_class"]] = grouped.get(holding["asset_class"], 0.0) + float(holding["market_value"])
    return {key: round(value, 6) for key, value in sorted(grouped.items())}


def update_registry(registry: dict[str, Any]) -> dict[str, Any]:
    entries = [
        ("WP5_CONTRACT", WP5_CONTRACT, "WP5 governed portfolio-decision contract", "CURRENT"),
        ("WP5_START", WP5_START, "WP5 explicit analysis-only start record", "CURRENT_BRANCH_CANDIDATE"),
        ("WP5_DECISION_INPUT_CURRENT", WP5_INPUT, "WP5 frozen decision input snapshot", "CURRENT_BRANCH_CANDIDATE"),
        ("WP5_PORTFOLIO_DECISION_CURRENT", WP5_DECISION, "WP5 conditional portfolio decision baseline", "CURRENT_BRANCH_CANDIDATE"),
        ("WP5_USER_DECISION_QUEUE_CURRENT", WP5_QUEUE, "WP5 governed user decision queue", "CURRENT_BRANCH_CANDIDATE"),
    ]
    assets = registry.setdefault("assets", [])
    if isinstance(assets, list):
        by_id = {item.get("asset_id"): item for item in assets if isinstance(item, dict)}
        for asset_id, location, role, status in entries:
            item = by_id.get(asset_id)
            payload = {
                "asset_id": asset_id,
                "authority": "GOVERNED_BRANCH_CANDIDATE",
                "format": "JSON",
                "location": location,
                "role": role,
                "status": status,
                "trade_authority": "NONE",
            }
            if item is None:
                assets.append(payload)
            else:
                item.update(payload)
    elif isinstance(assets, dict):
        for asset_id, location, role, status in entries:
            assets[asset_id.lower()] = {
                "location": location,
                "role": role,
                "status": status,
                "trade_authority": "NONE",
            }
    else:
        raise TypeError(f"Unsupported assets registry shape: {type(assets).__name__}")
    registry["status"] = "GITHUB_CURRENT_R2_ACCEPTED_WP5_STARTED_ON_BRANCH_ANALYSIS_ONLY_FILE_LIBRARY_PENDING"
    registry["registry_status"] = "WP5_ANALYSIS_ONLY_ASSETS_REGISTERED_ON_BRANCH_PENDING_MERGE"
    return registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    now = datetime.now(timezone.utc).isoformat()

    r2 = read_json(root, R2_ACCEPTANCE)
    execution = read_json(root, EXECUTION_REGISTER)
    registry = read_json(root, ASSET_REGISTRY)
    real = read_json(root, REAL_POSITIONS)
    simulation = read_json(root, SIM_POSITIONS)
    candidate = read_json(root, CANDIDATE_CURRENT)
    legacy_decisions = read_json(root, LEGACY_DECISIONS)
    models = read_json(root, WP4B_SCENARIOS)
    position_fit = read_json(root, WP4B_POSITION_FIT)
    events = read_json(root, WP4B_EVENTS)

    assert r2["status"] == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
    assert r2["wp5_status"] == "READY_PENDING_EXPLICIT_WP5_START"
    assert r2["merge_sha"] == R2_CAPABILITY_MERGE_SHA
    assert r2["economic_mutations"] == {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0}
    assert candidate["counts"]["candidate_core"] == 2
    assert tuple(row["security_id"] for row in candidate["candidate_core_members"]) == CORE2
    assert legacy_decisions["open_proposals"] == []
    validate_scenario_scale(models)

    contract = {
        "contract_id": "WP5_PORTFOLIO_DECISION_CONTRACT_V1",
        "phase": "WP5_PORTFOLIO_DECISION_PHASE",
        "scope": [
            "freeze current Real, Simulation, Candidate and Core2 research inputs",
            "produce account-level and position-level conditional recommendations",
            "separate research judgment, user decision and execution authority",
            "maintain an explicit user decision queue",
        ],
        "required_inputs": [REAL_POSITIONS, SIM_POSITIONS, CANDIDATE_CURRENT, WP4B_SCENARIOS, WP4B_POSITION_FIT, WP4B_EVENTS],
        "hard_gates": {
            "r2_accepted_on_main": True,
            "fresh_market_marks_at_decision_run": True,
            "position_delta_continuity_at_action_gate": True,
            "broker_or_user_verification_before_real_action": True,
            "current_event_classification_before_core2_action": True,
            "scenario_unit_scale_validation": True,
            "separate_user_approval_before_any_state_mutation": True,
        },
        "authority_boundary": {
            "automatic_real_account_mutation": False,
            "automatic_simulation_mutation": False,
            "automatic_candidate_membership_mutation": False,
            "automatic_order_creation": False,
            "trade_authority": "NONE",
        },
        "real_account_cash_policy": "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED_NO_FIXED_STRATEGIC_CASH_TARGET",
        "status": "ACTIVE_ON_GOVERNED_BRANCH_PENDING_USER_MERGE",
    }

    source_paths = [
        R2_ACCEPTANCE,
        REAL_POSITIONS,
        SIM_POSITIONS,
        CANDIDATE_CURRENT,
        LEGACY_DECISIONS,
        WP4B_SCENARIOS,
        WP4B_POSITION_FIT,
        WP4B_EVENTS,
    ]
    decision_input = {
        "state_id": "WP5_DECISION_INPUT_CURRENT",
        "generated_at": now,
        "source_main_merge_sha": R2_CLOSURE_MERGE_SHA,
        "r2_capability_merge_sha": R2_CAPABILITY_MERGE_SHA,
        "source_hashes": {path: file_sha256(root, path) for path in source_paths},
        "watermarks": {
            "real_position_base": real["position_watermark"]["base_state_as_of"],
            "real_user_delta_confirmed_through": real["position_watermark"]["user_delta_continuity_confirmed_through"],
            "simulation_position_base": simulation["position_watermark"]["base_state_as_of"],
            "simulation_user_delta_confirmed_through": simulation["position_watermark"]["user_delta_continuity_confirmed_through"],
            "latest_market_mark_date": min(real["mark_watermark"]["latest_mark_date"], simulation["mark_watermark"]["latest_mark_date"]),
            "candidate_as_of": candidate["as_of"],
        },
        "account_counts": {
            "real_holdings": real["summary"]["holding_count"],
            "simulation_holdings": simulation["summary"]["holding_count"],
            "candidate_core": candidate["counts"]["candidate_core"],
            "candidate_research_queue": candidate["counts"]["research_queue"],
            "candidate_shadow_track": candidate["counts"]["shadow_track"],
        },
        "verification": {
            "real_broker_verified": real["broker_verification"]["broker_verified"],
            "simulation_broker_verified": simulation["broker_verification"]["broker_verified"],
            "core2_scenario_unit_scale_validated": True,
            "legacy_open_proposals": len(legacy_decisions["open_proposals"]),
        },
        "status": "INPUT_FROZEN_FOR_ANALYSIS_NOT_EXECUTION",
        "trade_authority": "NONE",
    }

    real_total = float(real["summary"]["account_total_assets"])
    sim_total = float(simulation["summary"]["account_total_assets"])
    real_grouped = group_market_value(real["holdings"])
    real_weights = {key: round(value / real_total, 8) for key, value in real_grouped.items()}
    sim_cash_weight = float(simulation["summary"]["execution_cash_balance"]) / sim_total

    core2_decisions: dict[str, Any] = {}
    for sid in CORE2:
        model = models["models"][sid]
        fit = position_fit["positions"][sid]
        cases = scenario_map(model)
        if sid == "000333.SZ":
            provisional = "HOLD_ADD_REVIEW_ONLY_AFTER_FRESH_MARK_EVENT_AND_USER_GATES"
            constraints = [
                "2026Q1_ADJUSTED_PARENT_PROFIT_DECLINE_REQUIRES_MONITORING",
                "BROKER_OR_USER_POSITION_VERIFICATION_REQUIRED_AT_ACTION_GATE",
                "FRESH_COMPLETED_CLOSE_REQUIRED",
            ]
        else:
            provisional = "HOLD_NO_ADD_AT_CURRENT_MARK_UNDER_CURRENT_BASE_ASSUMPTIONS"
            constraints = [
                "BASE_CASE_IMPLIED_RETURN_IS_NEGATIVE_AT_CURRENT_MARK",
                "HYDROLOGY_TARIFF_FINANCE_AND_DIVIDEND_EVENT_CLASSIFICATION_REQUIRED",
                "BROKER_OR_USER_POSITION_VERIFICATION_REQUIRED_AT_ACTION_GATE",
                "FRESH_COMPLETED_CLOSE_REQUIRED",
            ]
        core2_decisions[sid] = {
            "security_id": sid,
            "security_name": fit["security_name"],
            "current_mark": model["current_price"],
            "current_weight": fit["current_weight"],
            "reference_target_weight": fit["target_weight_reference"],
            "market_value_gap_to_reference": fit["market_value_gap_to_reference"],
            "scenario_prices": cases,
            "provisional_judgment": provisional,
            "binding_constraints": constraints,
            "implementation_ready": False,
            "order_authorized": False,
            "trade_authority": "NONE",
        }

    decision = {
        "state_id": "WP5_PORTFOLIO_DECISION_CURRENT",
        "generated_at": now,
        "status": "CONDITIONAL_PORTFOLIO_REVIEW_NOT_IMPLEMENTATION_READY",
        "decision_mode": "POSITION_SIZING_AND_PORTFOLIO_ACTION_REVIEW_PROPOSAL_ONLY",
        "real_account": {
            "account_total_assets": real_total,
            "holding_count": real["summary"]["holding_count"],
            "asset_class_market_values": real_grouped,
            "asset_class_weights": real_weights,
            "execution_cash_balance": real["summary"]["execution_cash_balance"],
            "cash_policy": real["cash_policy"],
            "provisional_judgment": "HOLD_EXISTING_STRUCTURE_PENDING_FRESH_DECISION_RUN_AND_USER_VERIFICATION",
            "fixed_cash_target_applied": False,
            "implementation_ready": False,
        },
        "simulation": {
            "account_total_assets": sim_total,
            "holding_count": simulation["summary"]["holding_count"],
            "execution_cash_balance": simulation["summary"]["execution_cash_balance"],
            "execution_cash_weight": round(sim_cash_weight, 8),
            "provisional_judgment": "OBSERVE_AND_REVIEW_POSITION_LEVEL_THESIS_NO_AUTOMATIC_REBALANCE",
            "core2": core2_decisions,
            "implementation_ready": False,
        },
        "candidate": {
            "core_security_ids": list(CORE2),
            "ready_for_user_decision_count": 0,
            "membership_mutations": 0,
            "status": "CORE2_RESEARCH_AVAILABLE_WP5_ACTION_GATES_NOT_YET_PASSED",
        },
        "readiness_blockers": [
            "NEXT_COMPLETED_A_SHARE_CLOSE_MARK_REFRESH_REQUIRED",
            "USER_TRANSACTION_DELTA_CONTINUITY_CONFIRMATION_REQUIRED_AT_ACTION_GATE",
            "REAL_ACCOUNT_BROKER_OR_USER_POSITION_VERIFICATION_REQUIRED",
            "CORE2_CURRENT_EVENT_CLASSIFICATION_REQUIRED",
            "FULL_POSITION_LEVEL_THESIS_AND_RISK_REVIEW_REQUIRED_BEFORE_SIMULATION_CHANGES",
        ],
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }

    queue = {
        "state_id": "WP5_USER_DECISION_QUEUE_CURRENT",
        "generated_at": now,
        "status": "PREPARATION_QUEUE_NO_IMPLEMENTATION_READY_ITEMS",
        "ready_for_user_decision_count": 0,
        "items": [
            {
                "queue_id": "WP5-Q1",
                "subject": "Position continuity confirmation",
                "required_evidence": "User confirms no Real or Simulation quantity/cost changes after 2026-07-24, or supplies deltas",
                "status": "PENDING_AT_ACTION_GATE",
            },
            {
                "queue_id": "WP5-Q2",
                "subject": "Fresh market marks",
                "required_evidence": "Refresh all tracked positions after the next completed A-share close following 2026-07-24",
                "status": "PENDING",
            },
            {
                "queue_id": "WP5-Q3",
                "subject": "Core2 event classification",
                "required_evidence": "Classify Midea and Yangtze monitoring rules as green, amber, red or unavailable using current evidence",
                "status": "PENDING",
            },
            {
                "queue_id": "WP5-Q4",
                "subject": "Position-level simulation review",
                "required_evidence": "Review all 16 Simulation holdings for thesis, valuation, risk budget and portfolio role before any rebalance proposal",
                "status": "PENDING",
            },
        ],
        "orders": 0,
        "trade_authority": "NONE",
    }

    start_record = {
        "start_id": "WP5_PORTFOLIO_DECISION_START_V1",
        "generated_at": now,
        "explicit_start_authority": "USER_CONTINUE_AFTER_R2_AND_PR146_MERGE",
        "source_main_merge_sha": R2_CLOSURE_MERGE_SHA,
        "status": "WP5_STARTED_ANALYSIS_ONLY_ON_GOVERNED_BRANCH",
        "completed_start_steps": [
            "R2_MAIN_ACCEPTANCE_VERIFIED",
            "PORTFOLIO_AND_CANDIDATE_INPUTS_FROZEN",
            "WP4B_SCENARIO_MARKET_CAP_UNIT_REPAIRED_AND_VALIDATED",
            "CONDITIONAL_PORTFOLIO_DECISION_BASELINE_CREATED",
            "USER_DECISION_QUEUE_CREATED",
        ],
        "next_task": "WP5_FRESH_INPUT_REFRESH_AND_FULL_POSITION_LEVEL_ACTION_REVIEW",
        "implementation_ready": False,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }

    execution["current_step"] = "WP5_PORTFOLIO_DECISION_PHASE_STARTED_ANALYSIS_ONLY_ON_BRANCH"
    execution["next_task"] = "WP5_FRESH_INPUT_REFRESH_AND_FULL_POSITION_LEVEL_ACTION_REVIEW"
    execution["overall_status"] = "WP5_STARTED_ANALYSIS_ONLY_NO_ACTION_PENDING_GOVERNED_MERGE"
    execution["status_date"] = "2026-07-27"
    wp5 = execution.setdefault("wp5", {})
    wp5.update({
        "status": "STARTED_ANALYSIS_ONLY_ON_BRANCH",
        "next_gate": "FRESH_MARKS_EVENT_STATUS_USER_DELTA_AND_FULL_POSITION_REVIEW",
        "start_allowed": True,
        "action_review_allowed": True,
        "position_mutation_allowed": False,
        "order_execution_allowed": False,
        "forced_action_prohibited": True,
        "core2_scenario_unit_scale_repaired": True,
        "decision_input_path": WP5_INPUT,
        "decision_current_path": WP5_DECISION,
        "user_decision_queue_path": WP5_QUEUE,
        "ready_for_user_decision_count": 0,
        "trade_authority": "NONE",
    })

    registry = update_registry(registry)

    write_json(root, WP5_CONTRACT, contract)
    write_json(root, WP5_INPUT, decision_input)
    write_json(root, WP5_DECISION, decision)
    write_json(root, WP5_QUEUE, queue)
    start_record["semantic_hashes"] = {
        "contract": semantic_hash(contract),
        "input": semantic_hash(decision_input),
        "decision": semantic_hash(decision),
        "queue": semantic_hash(queue),
    }
    write_json(root, WP5_START, start_record)
    write_json(root, EXECUTION_REGISTER, execution)
    write_json(root, ASSET_REGISTRY, registry)

    print({
        "wp5": start_record["status"],
        "real_holdings": real["summary"]["holding_count"],
        "simulation_holdings": simulation["summary"]["holding_count"],
        "core2": list(CORE2),
        "ready_for_user_decision": 0,
        "orders": 0,
        "trade_authority": "NONE",
    })


if __name__ == "__main__":
    main()
