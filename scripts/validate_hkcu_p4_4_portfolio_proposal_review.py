#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-4"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def validate(root: Path, p4_2_dir: Path, p4_3_dir: Path, out: Path) -> dict[str, Any]:
    contract = read_json(root / "config/hkcu_p4_4_portfolio_proposal_review_contract.json")
    p4_3_contract = read_json(root / "config/hkcu_p4_3_portfolio_construction_scenario_test_contract.json")
    p4_2_contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    prefix = contract["output_prefix"]
    p4_3_prefix = p4_3_contract["output_prefix"]
    p4_2_prefix = p4_2_contract["output_prefix"]
    policy = contract["proposal_policy"]
    acceptance = contract["acceptance"]

    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    scenario_review = pd.read_csv(out / f"{prefix}_SCENARIO_REVIEW.csv", keep_default_na=False)
    proposals = pd.read_csv(out / f"{prefix}_PREFERRED_PROPOSALS.csv", keep_default_na=False)
    proposal_alloc = pd.read_csv(out / f"{prefix}_PROPOSAL_ALLOCATIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    p4_3_decision = read_json(p4_3_dir / f"{p4_3_prefix}_DECISION.json")
    p4_3_summary = pd.read_csv(p4_3_dir / f"{p4_3_prefix}_SCENARIO_SUMMARY.csv", keep_default_na=False)
    p4_3_alloc = pd.read_csv(p4_3_dir / f"{p4_3_prefix}_SCENARIO_ALLOCATIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    p4_2_review = pd.read_csv(p4_2_dir / f"{p4_2_prefix}_ACCOUNT_SECURITY_REVIEW.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != acceptance["pass_status"]: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS": errors.append("QUALITY_STATUS")
    if p4_3_decision.get("status") != contract["entry_contract"]["required_p4_3_status"]: errors.append("ENTRY_P4_3_STATUS")
    if len(p4_3_summary) != contract["entry_contract"]["required_scenario_count"]: errors.append("ENTRY_SCENARIO_COUNT")
    if len(scenario_review) != acceptance["scenario_review_count"]: errors.append("SCENARIO_REVIEW_COUNT")
    if scenario_review["scenario_id"].duplicated().any(): errors.append("DUPLICATE_SCENARIO_REVIEW")
    if len(proposals) != acceptance["preferred_proposal_count"]: errors.append("PREFERRED_PROPOSAL_COUNT")
    if set(proposals["account"].astype(str)) != {"REAL", "SIMULATION"}: errors.append("PROPOSAL_ACCOUNT_SET")

    expected_pref = {
        "REAL": policy["real_preferred_scenario"],
        "SIMULATION": policy["simulation_preferred_scenario"],
    }
    for account, scenario_id in expected_pref.items():
        p = proposals[proposals["account"].eq(account)]
        if len(p) != 1: errors.append(f"PROPOSAL_ACCOUNT_COUNT:{account}"); continue
        p = p.iloc[0]
        if str(p["preferred_scenario_id"]) != scenario_id: errors.append(f"PREFERRED_ID:{account}")
        expected_decision = "BUY_PROPOSAL" if account == "REAL" else "RESEARCH"
        expected_permission = policy["real_permission"] if account == "REAL" else policy["simulation_permission"]
        expected_execution = policy["real_execution_status"] if account == "REAL" else policy["simulation_execution_status"]
        if str(p["decision"]) != expected_decision: errors.append(f"DECISION_FIELD:{account}")
        if str(p["permission"]) != expected_permission: errors.append(f"PERMISSION_FIELD:{account}")
        if str(p["execution_status"]) != expected_execution: errors.append(f"EXECUTION_STATUS:{account}")
        for col in ("funding_source", "lookthrough_sector_mix", "lookthrough_style_mix", "alternative_scenarios", "exit_or_hold_condition", "initial_review_date"):
            if not str(p[col]).strip(): errors.append(f"MISSING_PROPOSAL_FIELD:{account}:{col}")
        if f(p["max_historical_drawdown_loss_weight"]) <= 0: errors.append(f"MISSING_MAX_LOSS:{account}")
        if str(p["target_writeback"]).lower() not in {"false", "0"}: errors.append(f"TARGET_WRITEBACK:{account}")
        if str(p["portfolio_mutation"]).lower() not in {"false", "0"}: errors.append(f"PORTFOLIO_MUTATION:{account}")
        if int(float(p["orders_created"])) != 0: errors.append(f"PROPOSAL_ORDERS:{account}")
        if str(p["trade_authority"]) != TRADE_AUTHORITY: errors.append(f"PROPOSAL_AUTHORITY:{account}")

        actual = proposal_alloc[(proposal_alloc["account"].eq(account)) & (proposal_alloc["proposal_scenario_id"].eq(scenario_id))].copy()
        expected = p4_3_alloc[(p4_3_alloc["account"].eq(account)) & (p4_3_alloc["scenario_id"].eq(scenario_id))].copy()
        if len(actual) != len(expected): errors.append(f"ALLOCATION_COUNT:{account}")
        if set(actual["security_id"].astype(str)) != set(expected["security_id"].astype(str)): errors.append(f"ALLOCATION_SECURITY_SET:{account}")
        amap = actual.set_index("security_id")["proposed_weight"].astype(float).to_dict()
        emap = expected.set_index("security_id")["scenario_weight"].astype(float).to_dict()
        for sid, ew in emap.items():
            if abs(float(amap.get(sid, -1.0)) - float(ew)) > 1e-12: errors.append(f"ALLOCATION_WEIGHT:{account}:{sid}")
        if expected["allocation_type"].ne("NEW_BUILD").any(): errors.append(f"PREFERRED_EXPECTED_HAS_SUB:{account}")
        if len(actual) and actual["security_id"].duplicated().any(): errors.append(f"DUPLICATE_PROPOSAL_ALLOCATION:{account}")
        if len(actual) and (pd.to_numeric(actual["proposed_weight"], errors="coerce").fillna(0.0) <= 0).any(): errors.append(f"NONPOSITIVE_PROPOSAL_WEIGHT:{account}")
        for col in ("funding_source_class", "portfolio_role", "principal_falsifier", "review_triggers", "alternative_route", "initial_review_date", "permission", "execution_status"):
            if len(actual) and actual[col].astype(str).str.strip().eq("").any(): errors.append(f"ALLOCATION_MISSING_FIELD:{account}:{col}")
        for col in ("candidate_portfolio_correlation", "downside_correlation"):
            if len(actual) and pd.to_numeric(actual[col], errors="coerce").isna().any(): errors.append(f"ALLOCATION_MISSING_NUMERIC_FIELD:{account}:{col}")
        if len(actual) and actual["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append(f"ALLOCATION_MUTATION:{account}")
        if len(actual) and pd.to_numeric(actual["orders_created"], errors="coerce").fillna(0).ne(0).any(): errors.append(f"ALLOCATION_ORDERS:{account}")
        if len(actual) and not actual["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append(f"ALLOCATION_AUTHORITY:{account}")

    ah = scenario_review[scenario_review["scenario_family"].eq("MAX_AH_SUBSTITUTION_STRESS")]
    if len(ah) != 3: errors.append("AH_REVIEW_COUNT")
    if len(ah) and not ah["scenario_review_state"].eq("RESEARCH_ONLY_AH_SUBSTITUTION").all(): errors.append("AH_PROMOTED")
    if proposal_alloc["proposal_scenario_id"].astype(str).str.contains("AH_STRESS", regex=False).any(): errors.append("AH_IN_PREFERRED_PROPOSAL")

    required_review_states = {
        policy["real_preferred_scenario"]: "PREFERRED_PORTFOLIO_PROPOSAL",
        policy["real_conditional_expansion_scenario"]: "CONDITIONAL_EXPANSION_ALTERNATIVE",
        policy["real_hold_expansion_scenario"]: "HOLD_EXPANSION",
        policy["simulation_preferred_scenario"]: "PREFERRED_PORTFOLIO_PROPOSAL",
        policy["simulation_conservative_alternative"]: "CONSERVATIVE_ALTERNATIVE",
        policy["simulation_expanded_alternative"]: "CONDITIONAL_EXPANSION_ALTERNATIVE",
    }
    review_map = scenario_review.set_index("scenario_id")["scenario_review_state"].astype(str).to_dict()
    for sid, state in required_review_states.items():
        if review_map.get(sid) != state: errors.append(f"SCENARIO_ROUTE:{sid}")

    p4_idx = p4_2_review.set_index(["security_id", "account"], drop=False)
    for r in proposal_alloc.itertuples(index=False):
        key = (str(r.security_id), str(r.account))
        if key not in p4_idx.index: errors.append(f"P4_2_LINEAGE_MISSING:{key[1]}:{key[0]}")

    for field in ("candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"):
        if int(decision.get(field, -1)) != int(acceptance[field]): errors.append(f"DECISION_ACCEPTANCE:{field}")
    for field in ("target_portfolio_writeback", "pretrade_memo_produced", "user_trade_confirmation_recorded"):
        if decision.get(field) is not acceptance[field]: errors.append(f"DECISION_ACCEPTANCE:{field}")
    if decision.get("phase_close_status") != acceptance["phase_close_status"]: errors.append("PHASE_NOT_CLOSED")
    if decision.get("next_phase") != acceptance["next_phase_on_pass"]: errors.append("NEXT_PHASE")
    if decision.get("additional_p4_subphases_allowed") is not False: errors.append("MORE_P4_SUBPHASES_ALLOWED")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("DECISION_AUTHORITY")

    for flag in ("weighted_score", "fixed_top_n", "candidate_rank_used_as_proposal_authority", "ah_relative_value_called_alpha", "ah_stress_promoted_to_preferred_proposal", "target_writeback", "pretrade_memo_produced", "user_trade_confirmation_recorded"):
        if quality.get(flag) is not False: errors.append(f"QUALITY_FALSE:{flag}")
    for flag in ("preferred_real_uses_staged_external_funding_principle", "simulation_balanced_is_observation_proposal_not_expected_return_claim", "proposal_fields_cover_funding_loss_correlation_lookthrough_alternative_exit_review"):
        if quality.get(flag) is not True: errors.append(f"QUALITY_TRUE:{flag}")
    if int(quality.get("portfolio_mutations", -1)) != 0: errors.append("QUALITY_MUTATION")
    if int(quality.get("orders_created", -1)) != 0: errors.append("QUALITY_ORDERS")
    if quality.get("trade_authority") != TRADE_AUTHORITY: errors.append("QUALITY_AUTHORITY")

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "phase_close_status": decision.get("phase_close_status"),
        "next_phase": decision.get("next_phase"),
        "scenario_review_count": len(scenario_review),
        "preferred_proposal_count": len(proposals),
        "proposal_allocation_count": len(proposal_alloc),
        "errors": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p4-2-dir", required=True)
    ap.add_argument("--p4-3-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    validate(Path(args.repo_root).resolve(), Path(args.p4_2_dir).resolve(), Path(args.p4_3_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
