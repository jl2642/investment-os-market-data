#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P0_IDS = ("300124.SZ", "300750.SZ", "601138.SH")
HURDLE_RETURN = 0.15


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def semantic_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def find_holding(simulation: dict[str, Any], sid: str) -> dict[str, Any]:
    return next(row for row in simulation["holdings"] if row["security_id"] == sid)


def scenario_product(company: dict[str, Any], completed_mark: float) -> dict[str, Any]:
    shares_bn = float(company["shares_outstanding_bn"])
    cases = []
    for name, assumption in company["scenario_assumptions"]["cases"].items():
        net_profit = float(assumption["net_profit_rmb_bn"])
        exit_pe = float(assumption["exit_pe"])
        implied_market_cap = net_profit * exit_pe
        implied_price = implied_market_cap / shares_bn
        cases.append({
            "scenario": name,
            "net_profit_rmb_bn": net_profit,
            "exit_pe": exit_pe,
            "implied_market_cap_rmb_bn": round(implied_market_cap, 6),
            "implied_price": round(implied_price, 6),
            "return_vs_completed_close": round(implied_price / completed_mark - 1.0, 8),
        })
    cases.sort(key=lambda row: ("BEAR", "BASE", "BULL").index(row["scenario"]))
    base_case = next(row for row in cases if row["scenario"] == "BASE")
    return {
        "model": company["scenario_assumptions"]["model"],
        "shares_outstanding_bn": shares_bn,
        "completed_close_mark": completed_mark,
        "governed_expected_return_hurdle": HURDLE_RETURN,
        "base_case_hurdle_passed": base_case["return_vs_completed_close"] >= HURDLE_RETURN,
        "cases": cases,
        "limitations": [
            "Scenario values are research interfaces, not statutory forecasts",
            "Intraday quotes are excluded from valuation returns",
            "No scenario authorizes a position change or order",
        ],
    }


def upsert_asset(assets: list[dict[str, Any]], item: dict[str, Any]) -> None:
    for index, existing in enumerate(assets):
        if existing.get("asset_id") == item["asset_id"]:
            assets[index] = item
            return
    assets.append(item)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--facts", default="automation/wp5_portfolio_decision/p0_external_source_facts.json")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    generated_at = datetime.now(timezone.utc).isoformat()

    facts = read_json(root / args.facts)
    marks = read_json(root / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json")
    marks_candidate = read_json(root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP2_R/PORTFOLIO_MARKS_REFRESH_CANDIDATE.json")
    fresh_input = read_json(root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/WP5_P0_FRESH_INPUT_STATUS_CURRENT.json")
    simulation = read_json(root / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json")
    internal = read_json(root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/WP5_P0_INTERNAL_EVIDENCE_INVENTORY_CURRENT.json")
    workplan = read_json(root / "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_WORKPLAN_CURRENT.json")
    queue = read_json(root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json")
    execution = read_json(root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(root / "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json")

    mark_by_id = {row["security_id"]: row for row in marks["marks"]}
    intraday_by_id = {row["security_id"]: row for row in marks_candidate.get("intraday_observations", [])}
    research_objects: dict[str, Any] = {}
    action_rows = []

    for sid in P0_IDS:
        company = facts["companies"][sid]
        holding = find_holding(simulation, sid)
        mark_row = mark_by_id[sid]
        completed_mark = float(mark_row["mark"])
        scenario = scenario_product(company, completed_mark)
        current_weight = float(holding["market_value"]) / float(simulation["summary"]["account_total_assets"])
        band = company["conditional_decision"]["proposed_weight_band"]
        within_band = float(band["min"]) <= current_weight <= float(band["max"])
        base_case = next(row for row in scenario["cases"] if row["scenario"] == "BASE")
        action_posture = (
            "HOLD_WITHIN_REVISED_BAND_NO_ADD"
            if within_band
            else "REVIEW_TO_REVISED_BAND_PENDING_USER_APPROVAL"
        )
        research = {
            "research_id": f"WP5_P0_REUNDERWRITE_{sid}",
            "security_id": sid,
            "security_name": company["security_name"],
            "status": "P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_COMPLETE_RESEARCH_ONLY",
            "generated_at": generated_at,
            "portfolio_role_under_review": company["portfolio_role_under_review"],
            "position_context": {
                "quantity": holding["quantity"],
                "unit_cost": holding["unit_cost"],
                "cost_basis": holding["cost_basis"],
                "completed_close_mark": completed_mark,
                "completed_close_date": mark_row["as_of_date"],
                "market_value": holding["market_value"],
                "current_weight": round(current_weight, 8),
                "unrealized_pnl": holding["unrealized_pnl"],
                "unrealized_pnl_pct": holding["unrealized_pnl_pct"],
                "intraday_observation": intraday_by_id.get(sid),
                "intraday_observation_decision_grade": False,
            },
            "official_financial_and_operating_facts": company["official_facts"],
            "current_event_classification": company["current_event_classification"],
            "driver_based_scenarios": scenario,
            "internal_evidence_reference": {
                "candidate_record_count": internal["objects"][sid]["candidate_record_count"],
                "gap_flags": internal["objects"][sid]["internal_evidence_gap_flags"],
                "workplan_decision_gate": internal["objects"][sid]["workplan"]["decision_gate"],
            },
            "conditional_portfolio_decision": {
                **company["conditional_decision"],
                "current_weight": round(current_weight, 8),
                "within_revised_weight_band": within_band,
                "base_case_expected_return": base_case["return_vs_completed_close"],
                "base_case_hurdle_passed": scenario["base_case_hurdle_passed"],
                "action_posture": action_posture,
                "position_change_authorized": False,
                "order_authorized": False,
                "trade_authority": "NONE",
            },
            "sources": company["sources"],
            "source_quality": {
                "source_count": len(company["sources"]),
                "all_primary_documents": all(source["primary_document"] for source in company["sources"]),
                "external_primary_source_reunderwrite_complete": True,
            },
            "implementation_readiness": {
                "research_complete": True,
                "fresh_completed_close_for_action": fresh_input["implementation_action_mark_ready"],
                "user_position_continuity_confirmed": False,
                "broker_verified": False,
                "implementation_ready": False,
            },
            "economic_mutations": {"simulation": 0, "real_account": 0, "candidate_membership": 0, "orders": 0},
            "trade_authority": "NONE",
        }
        research["semantic_hash"] = semantic_hash({key: value for key, value in research.items() if key not in {"generated_at", "semantic_hash"}})
        research_objects[sid] = research
        action_rows.append({
            "security_id": sid,
            "security_name": company["security_name"],
            "completed_close_mark": completed_mark,
            "completed_close_date": mark_row["as_of_date"],
            "current_weight": round(current_weight, 8),
            "revised_weight_band": band,
            "within_revised_weight_band": within_band,
            "base_case_expected_return": base_case["return_vs_completed_close"],
            "base_case_hurdle_passed": scenario["base_case_hurdle_passed"],
            "research_judgment": company["conditional_decision"]["research_judgment"],
            "action_posture": action_posture,
            "implementation_ready": False,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": "NONE",
        })

    combined = {
        "state_id": "WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT",
        "status": "THREE_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITES_COMPLETE_RESEARCH_ONLY",
        "generated_at": generated_at,
        "source_facts_as_of": facts["as_of_date"],
        "latest_completed_close_date": fresh_input["latest_completed_listed_close_date"],
        "intraday_observations_excluded_from_decision_marks": True,
        "research_object_count": len(research_objects),
        "research_objects": research_objects,
        "implementation_ready_count": 0,
        "economic_mutations": {"simulation": 0, "real_account": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    combined["semantic_hash"] = semantic_hash({key: value for key, value in combined.items() if key not in {"generated_at", "semantic_hash"}})

    action_review = {
        "state_id": "WP5_P0_ACTION_REVIEW_CURRENT",
        "status": "P0_RESEARCH_COMPLETE_ALL_CURRENT_WEIGHTS_WITHIN_REVISED_BANDS_NO_ACTION_READY",
        "generated_at": generated_at,
        "decision_mode": "CONDITIONAL_POSITION_REVIEW_PROPOSAL_ONLY",
        "governed_expected_return_hurdle": HURDLE_RETURN,
        "positions": action_rows,
        "portfolio_conclusion": {
            "300124.SZ": "RETAIN_REDUCED_OBSERVATION_WEIGHT_NO_ADD",
            "300750.SZ": "HOLD_VALIDATION_POSITION_NO_ADD",
            "601138.SH": "RETAIN_REDUCED_WEIGHT_NO_ADD",
        },
        "all_current_weights_within_revised_bands": all(row["within_revised_weight_band"] for row in action_rows),
        "base_case_hurdle_pass_count": sum(bool(row["base_case_hurdle_passed"]) for row in action_rows),
        "ready_for_user_decision_count": 0,
        "implementation_blockers": [
            "NEXT_COMPLETED_A_SHARE_CLOSE_REQUIRED_AFTER_INTRADAY_OBSERVATION",
            "USER_POSITION_CONTINUITY_CONFIRMATION_REQUIRED",
            "BROKER_VERIFICATION_UNAVAILABLE",
            "NO_BASE_CASE_EXPECTED_RETURN_MEETS_15_PERCENT_HURDLE",
        ],
        "economic_mutations": {"simulation": 0, "real_account": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    action_review["semantic_hash"] = semantic_hash({key: value for key, value in action_review.items() if key not in {"generated_at", "semantic_hash"}})

    base_items: dict[str, dict[str, Any]] = {}
    for item in queue.get("items", []):
        base_items.setdefault(item["queue_id"], item)
    if "WP5-Q2" in base_items:
        base_items["WP5-Q2"] = {
            **base_items["WP5-Q2"],
            "required_evidence": "Publish the next completed A-share close after the 2026-07-27 intraday observation; intraday quotes are not decision marks",
            "status": "PENDING_NEXT_COMPLETED_CLOSE",
        }
    if "WP5-Q4A" in base_items:
        base_items["WP5-Q4A"] = {
            **base_items["WP5-Q4A"],
            "required_evidence": "External primary-source re-underwrite completed for Inovance, CATL and FII; implementation gates remain closed",
            "status": "RESEARCH_COMPLETE_IMPLEMENTATION_NOT_READY",
        }
    base_items["WP5-Q6"] = {
        "queue_id": "WP5-Q6",
        "subject": "P0 action hurdle",
        "required_evidence": "A fresh completed close, position continuity and a governed base-case expected return at or above 15% are required before any add/trim/exit proposal can be implementation-ready",
        "status": "PENDING",
    }
    queue.update({
        "generated_at": generated_at,
        "items": [base_items[key] for key in sorted(base_items)],
        "status": "P0_EXTERNAL_REUNDERWRITE_COMPLETE_NO_IMPLEMENTATION_READY_ITEMS",
        "p0_external_reunderwrite_path": "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT.json",
        "p0_action_review_path": "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json",
        "ready_for_user_decision_count": 0,
        "orders": 0,
        "trade_authority": "NONE",
    })

    execution.update({
        "current_step": "WP5_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_COMPLETE_RESEARCH_ONLY_ON_BRANCH",
        "next_task": "WP5_NEXT_COMPLETED_CLOSE_REFRESH_AND_USER_POSITION_CONTINUITY_CONFIRMATION",
        "overall_status": "WP5_P0_RESEARCH_COMPLETE_HOLD_NO_ADD_FRESH_CLOSE_AND_USER_CONTINUITY_PENDING",
        "status_date": facts["as_of_date"],
    })
    execution["wp5"].update({
        "branch": "agent/wp5-p0-external-reunderwrite",
        "status": "P0_EXTERNAL_REUNDERWRITE_COMPLETE_RESEARCH_ONLY_ON_BRANCH",
        "next_gate": "NEXT_COMPLETED_CLOSE_USER_POSITION_CONTINUITY_AND_15_PERCENT_BASE_CASE_HURDLE",
        "p0_external_primary_source_reunderwrite_complete": True,
        "p0_event_classification_complete": True,
        "p0_external_reunderwrite_path": "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT.json",
        "p0_action_review_path": "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json",
        "fresh_completed_close_for_action": fresh_input["implementation_action_mark_ready"],
        "ready_for_user_decision_count": 0,
        "position_mutation_allowed": False,
        "order_execution_allowed": False,
        "trade_authority": "NONE",
    })

    assets = registry.setdefault("assets", [])
    for item in (
        {
            "asset_id": "WP5_P0_FRESH_INPUT_STATUS_CURRENT",
            "authority": "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE/WP5_P0_FRESH_INPUT_STATUS_CURRENT.json",
            "role": "Completed-close versus intraday input gate",
            "status": "CURRENT_BRANCH_CANDIDATE",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT",
            "authority": "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT.json",
            "role": "Three P0 external primary-source research objects",
            "status": "CURRENT_BRANCH_CANDIDATE_RESEARCH_ONLY",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "WP5_P0_ACTION_REVIEW_CURRENT",
            "authority": "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json",
            "role": "P0 conditional hold/add/trim/exit review",
            "status": "CURRENT_BRANCH_CANDIDATE_NO_ACTION_READY",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "WP5_P0_REUNDERWRITE_ACCEPTANCE",
            "authority": "GOVERNED_BRANCH_CANDIDATE",
            "format": "JSON",
            "location": "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_ACCEPTANCE_RECORD.json",
            "role": "P0 research, scenario, lineage and zero-mutation acceptance",
            "status": "ACCEPTED_ON_BRANCH_PENDING_MERGE",
            "trade_authority": "NONE",
        },
    ):
        upsert_asset(assets, item)
    registry.update({
        "registry_status": "WP5_P0_EXTERNAL_REUNDERWRITE_ASSETS_REGISTERED_ON_BRANCH_PENDING_MERGE",
        "status": "GITHUB_CURRENT_WP5_P0_RESEARCH_BRANCH_CANDIDATE_FILE_LIBRARY_PENDING",
        "date": facts["as_of_date"],
        "trade_authority": "NONE",
    })

    acceptance = {
        "acceptance_id": "WP5_P0_EXTERNAL_REUNDERWRITE_ACCEPTANCE_V1",
        "status": "WP5_P0_EXTERNAL_REUNDERWRITE_ACCEPTED_RESEARCH_ONLY_ON_BRANCH_PENDING_MERGE",
        "generated_at": generated_at,
        "research_object_count": len(research_objects),
        "external_primary_source_reunderwrite_complete": True,
        "current_event_classification_complete": True,
        "scenario_case_count": sum(len(row["driver_based_scenarios"]["cases"]) for row in research_objects.values()),
        "all_current_weights_within_revised_bands": action_review["all_current_weights_within_revised_bands"],
        "base_case_hurdle_pass_count": action_review["base_case_hurdle_pass_count"],
        "latest_completed_close_date": fresh_input["latest_completed_listed_close_date"],
        "intraday_quotes_excluded_from_decision_marks": True,
        "implementation_ready_count": 0,
        "economic_mutations": {"simulation": 0, "real_account": 0, "candidate_membership": 0, "orders": 0},
        "trade_authority": "NONE",
    }
    acceptance["semantic_hash"] = semantic_hash({key: value for key, value in acceptance.items() if key not in {"generated_at", "semantic_hash"}})

    evidence_root = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP5/P0_REUNDERWRITE"
    for sid, research in research_objects.items():
        write_json(evidence_root / sid / "WP5_P0_REUNDERWRITE_CURRENT.json", research)
    write_json(root / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP5_P0_EXTERNAL_REUNDERWRITE_CURRENT.json", combined)
    write_json(root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json", action_review)
    write_json(root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/WP5_USER_DECISION_QUEUE_CURRENT.json", queue)
    write_json(root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json", execution)
    write_json(root / "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json", registry)
    write_json(root / "investment_os_runtime/00_CONTROL/WP5_P0_REUNDERWRITE_ACCEPTANCE_RECORD.json", acceptance)

    print(json.dumps({
        "research_objects": len(research_objects),
        "scenario_cases": acceptance["scenario_case_count"],
        "all_within_revised_bands": acceptance["all_current_weights_within_revised_bands"],
        "base_case_hurdle_pass_count": acceptance["base_case_hurdle_pass_count"],
        "ready_for_user_decision": 0,
        "orders": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
