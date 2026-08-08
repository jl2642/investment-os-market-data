#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-2"
TRADE_AUTHORITY = "NONE"
ACTIONABLE = {"PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW", "PROBE_BUILD_REVIEW"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_pipe(value: Any) -> list[str]:
    return [x for x in str(value or "").split("|") if x]


def f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def validate(root: Path, context_dir: Path, fit_dir: Path, out: Path) -> dict[str, Any]:
    contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    prefix = contract["output_prefix"]
    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    review = pd.read_csv(out / f"{prefix}_ACCOUNT_SECURITY_REVIEW.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    combined = pd.read_csv(out / f"{prefix}_COMBINED_ROUTING.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    substitutions = pd.read_csv(out / f"{prefix}_SUBSTITUTION_REGISTER.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    fit_decision = read_json(fit_dir / "HKCU_P4_1_REASSESSMENT_DECISION.json")
    ctx_decision = read_json(context_dir / "HKCU_P4_1R_DECISION.json")

    errors: list[str] = []
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != contract["acceptance"]["pass_status"]: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS": errors.append("QUALITY_STATUS")
    if fit_decision.get("status") != contract["entry_contract"]["required_p4_1_status"]: errors.append("ENTRY_P4_1_STATUS")
    if ctx_decision.get("status") != contract["entry_contract"]["required_p4_1r_status"]: errors.append("ENTRY_P4_1R_STATUS")
    if len(review) != contract["acceptance"]["account_security_review_count"]: errors.append(f"REVIEW_COUNT:{len(review)}")
    if len(combined) != contract["acceptance"]["combined_security_count"]: errors.append(f"COMBINED_COUNT:{len(combined)}")
    if review.duplicated(["security_id", "account"]).any(): errors.append("DUPLICATE_REVIEW")
    if combined["security_id"].duplicated().any(): errors.append("DUPLICATE_COMBINED")
    if set(review["account"]) != {"REAL", "SIMULATION"}: errors.append("ACCOUNT_SET")
    if set(review["construction_state"]) - set(contract["construction_states"]): errors.append("CONSTRUCTION_STATE_ENUM")
    if set(combined["combined_route"]) - set(contract["combined_routes"]): errors.append("COMBINED_ROUTE_ENUM")

    required_semantic_cols = {
        "p4_1r_existing_same_style_weight_raw",
        "construction_existing_direct_same_style_weight",
        "construction_style_scope",
    }
    if not required_semantic_cols.issubset(review.columns):
        errors.append("DIRECT_STYLE_SEMANTIC_COLUMNS")

    if not (review["trade_authority"].eq(TRADE_AUTHORITY).all() and combined["trade_authority"].eq(TRADE_AUTHORITY).all()): errors.append("TRADE_AUTHORITY")
    if review["orders_created"].astype(int).sum() != 0 or combined["orders_created"].astype(int).sum() != 0: errors.append("ORDERS_CREATED")
    if review["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("PORTFOLIO_MUTATION")
    if combined["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("COMBINED_PORTFOLIO_MUTATION")

    for _, row in review.iterrows():
        key = f"{row['account']}:{row['security_id']}"
        state = str(row["construction_state"])
        wmin, wmax, cap = f(row["suggested_weight_min"]), f(row["suggested_weight_max"]), f(row["analytical_weight_cap"])
        if wmin < -1e-12 or wmax < -1e-12 or cap < -1e-12: errors.append(f"NEGATIVE_WEIGHT:{key}")
        if wmin > wmax + 1e-12: errors.append(f"MIN_GT_MAX:{key}")
        if wmax > cap + 1e-12: errors.append(f"MAX_GT_CAP:{key}")
        if state in ACTIONABLE:
            if wmax <= 0: errors.append(f"ACTIONABLE_WITHOUT_WEIGHT:{key}")
            cap_cols = [
                "tier_cap", "volatility_cap", "historical_drawdown_loss_cap", "marginal_risk_cap",
                "opportunity_cost_cap", "confidence_cap", "sector_room_cap", "style_room_cap", "liquidity_cap",
            ]
            minimum = min(f(row[c]) for c in cap_cols)
            if state == "PROBE_BUILD_REVIEW":
                minimum = min(minimum, float(contract["construction_policy"]["probe_hard_cap"][row["account"]]))
            if cap > minimum + 1e-12: errors.append(f"CAP_EXCEEDS_INDEPENDENT_MIN:{key}")
        else:
            if wmin > 1e-12 or wmax > 1e-12 or cap > 1e-12: errors.append(f"NON_ACTIONABLE_HAS_NEW_SIZE:{key}")
        if str(row["opportunity_cost_state"]) == "HIGH_RELATIVE_OPPORTUNITY_COST" and wmax > 1e-12:
            errors.append(f"HIGH_OPP_COST_HAS_NEW_SIZE:{key}")

        raw_style = f(row.get("p4_1r_existing_same_style_weight_raw"))
        direct_style = f(row.get("construction_existing_direct_same_style_weight"))
        if direct_style > raw_style + 1e-12:
            errors.append(f"DIRECT_STYLE_GT_RAW:{key}")
        if str(row.get("construction_style_scope")) != "DIRECT_EQUITY_ONLY_EXCLUDES_FIXED_INCOME_AND_GENERIC_POOLED":
            errors.append(f"DIRECT_STYLE_SCOPE:{key}")
        if str(row.get("portfolio_style")) == "DEFENSIVE" and row["account"] == "REAL" and raw_style > 0.30 and direct_style >= raw_style - 1e-12:
            errors.append(f"REAL_DEFENSIVE_FIXED_INCOME_NOT_EXCLUDED:{key}")

        ah = split_pipe(row.get("ah_overlap_security_ids"))
        if ah:
            if state != "SUBSTITUTION_REVIEW_ONLY": errors.append(f"AH_OVERLAP_NOT_SUBSTITUTION:{key}")
            if wmax > 1e-12: errors.append(f"AH_OVERLAP_NET_NEW_SIZE:{key}")
            if f(row["replacement_equivalent_weight_cap"]) > f(row["existing_ah_overlap_weight"]) + 1e-12:
                errors.append(f"REPLACEMENT_CAP_GT_EXISTING:{key}")
            tier_cap = f(row["tier_cap"])
            if abs(f(row["sector_room_cap"]) - tier_cap) > 1e-12 or abs(f(row["style_room_cap"]) - tier_cap) > 1e-12:
                errors.append(f"AH_SUBSTITUTION_NET_NEW_ROOM_APPLIED:{key}")
        if str(row["p4_1_fit_state"]) == "NO_INCREMENTAL_ROLE" and state != "NO_INCREMENTAL_ROLE":
            errors.append(f"P4_1_NO_INCREMENTAL_NOT_PRESERVED:{key}")
        if row["account"] == "REAL" and int(float(row["material_confidence_cap_count"])) > 0 and wmax > 1e-12:
            errors.append(f"REAL_MATERIAL_CONFIDENCE_HAS_SIZE:{key}")
        if str(row["individual_envelope_is_non_additive"]).lower() not in {"true", "1"}:
            errors.append(f"NON_ADDITIVITY_FLAG:{key}")

    ah_review = review[review["ah_overlap_security_ids"].astype(str).str.len() > 0]
    if len(substitutions) != len(ah_review): errors.append(f"SUBSTITUTION_COUNT:{len(substitutions)}!={len(ah_review)}")
    if len(substitutions):
        if substitutions["net_new_weight_authorized"].astype(float).abs().max() > 1e-12: errors.append("SUBSTITUTION_NET_NEW_NONZERO")
        if not substitutions["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("SUBSTITUTION_AUTHORITY")

    for _, row in combined.iterrows():
        sid = str(row["security_id"])
        pair = review[review["security_id"].eq(sid)]
        states = set(pair["construction_state"].astype(str))
        has_new = bool(states & ACTIONABLE)
        has_sub = "SUBSTITUTION_REVIEW_ONLY" in states
        if has_new and has_sub and row["combined_route"] != "ADVANCE_MIXED_NEW_AND_SUBSTITUTION_SCENARIO_TEST":
            errors.append(f"MIXED_NEW_SUBSTITUTION_ROUTE_LOST:{sid}")

    if decision.get("aggregate_portfolio_allocation_produced") is not False: errors.append("AGGREGATE_ALLOCATION_PRODUCED")
    if decision.get("individual_envelopes_non_additive") is not True: errors.append("DECISION_NON_ADDITIVITY")
    if int(decision.get("portfolio_allocations", -1)) != 0: errors.append("PORTFOLIO_ALLOCATIONS")
    if int(decision.get("orders_created", -1)) != 0: errors.append("DECISION_ORDERS")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("DECISION_AUTHORITY")
    for flag in (
        "weighted_score", "fixed_top_n", "candidate_rank_used_as_allocation_authority",
        "exact_ah_net_new_size_authorized", "high_opportunity_cost_new_size_authorized",
        "real_cash_treated_as_strategic_target", "individual_caps_called_aggregate_portfolio",
    ):
        if quality.get(flag) is not False: errors.append(f"QUALITY_FLAG:{flag}")
    for flag in (
        "independent_caps_use_minimum_not_offsetting_score",
        "aggregate_scenario_test_required_before_portfolio_proposal",
        "direct_equity_style_room_excludes_fixed_income_and_generic_pooled",
        "substitution_caps_ignore_net_new_sector_style_room",
        "mixed_new_substitution_route_preserved",
    ):
        if quality.get(flag) is not True: errors.append(f"QUALITY_TRUE_FLAG:{flag}")

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "account_security_review_count": len(review),
        "combined_security_count": len(combined),
        "construction_state_counts": decision.get("construction_state_counts", {}),
        "combined_route_counts": decision.get("combined_route_counts", {}),
        "substitution_review_count": len(substitutions),
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
    ap.add_argument("--context-dir", required=True)
    ap.add_argument("--fit-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    validate(Path(args.repo_root).resolve(), Path(args.context_dir).resolve(), Path(args.fit_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
