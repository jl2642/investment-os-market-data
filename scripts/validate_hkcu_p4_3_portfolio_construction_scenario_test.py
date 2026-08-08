#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-3"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def validate(root: Path, p4_2_dir: Path, out: Path) -> dict[str, Any]:
    contract = read_json(root / "config/hkcu_p4_3_portfolio_construction_scenario_test_contract.json")
    p4_2_contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    prefix = contract["output_prefix"]
    p4_2_prefix = p4_2_contract["output_prefix"]
    policy = contract["scenario_policy"]

    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    summary = pd.read_csv(out / f"{prefix}_SCENARIO_SUMMARY.csv", keep_default_na=False)
    allocations = pd.read_csv(out / f"{prefix}_SCENARIO_ALLOCATIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    ah_options = pd.read_csv(out / f"{prefix}_AH_SUBSTITUTION_OPTIONS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    p4_2_decision = read_json(p4_2_dir / f"{p4_2_prefix}_DECISION.json")
    p4_2_review = pd.read_csv(p4_2_dir / f"{p4_2_prefix}_ACCOUNT_SECURITY_REVIEW.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    p4_2_sub = pd.read_csv(p4_2_dir / f"{p4_2_prefix}_SUBSTITUTION_REGISTER.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    acceptance = contract["acceptance"]
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != acceptance["pass_status"]: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS": errors.append("QUALITY_STATUS")
    if p4_2_decision.get("status") != contract["entry_contract"]["required_p4_2_status"]: errors.append("P4_2_ENTRY_STATUS")
    if len(summary) != acceptance["scenario_count"]: errors.append(f"SCENARIO_COUNT:{len(summary)}")
    if summary["scenario_id"].duplicated().any(): errors.append("DUPLICATE_SCENARIO")
    if int(summary["account"].eq("REAL").sum()) != acceptance["real_scenario_count"]: errors.append("REAL_SCENARIO_COUNT")
    if int(summary["account"].eq("SIMULATION").sum()) != acceptance["simulation_scenario_count"]: errors.append("SIM_SCENARIO_COUNT")
    if int(summary["scenario_family"].eq("MAX_AH_SUBSTITUTION_STRESS").sum()) < acceptance["minimum_ah_stress_scenario_count"]: errors.append("AH_STRESS_SCENARIO_COUNT")
    if not summary["scenario_status"].eq("PASS").all(): errors.append("SCENARIO_STATUS")
    if allocations.empty: errors.append("EMPTY_ALLOCATIONS")
    if not allocations["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("ALLOCATION_AUTHORITY")
    if (pd.to_numeric(allocations["orders_created"], errors="coerce").fillna(0) != 0).any(): errors.append("ALLOCATION_ORDERS")
    if allocations["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("ALLOCATION_MUTATION")

    p4_idx = p4_2_review.set_index(["security_id", "account"], drop=False)
    min_pos = float(policy["minimum_scenario_position_weight"])
    tolerance = float(policy["target_residual_tolerance"])
    sector_abs_limit = float(policy["direct_sector_weight_limit"])
    style_abs_limit = float(policy["direct_style_weight_limit"])
    sector_frac_limit = float(policy["hk_sleeve_sector_fraction_limit"])
    style_frac_limit = float(policy["hk_sleeve_style_fraction_limit"])
    stress_fraction = float(policy["gross_historical_drawdown_stress_fraction_of_hk_sleeve"])

    for _, s in summary.iterrows():
        sid = str(s["scenario_id"])
        account = str(s["account"])
        family = str(s["scenario_family"])
        target = f(s["hk_sleeve_target"])
        rows = allocations[allocations["scenario_id"].eq(sid)].copy()
        total = pd.to_numeric(rows["scenario_weight"], errors="coerce").fillna(0.0).sum()
        if total > target + 1e-9: errors.append(f"TARGET_EXCEEDED:{sid}")
        if target - total > tolerance + 1e-9: errors.append(f"TARGET_UNDERFILLED:{sid}")
        if abs(total - f(s["hk_sleeve_allocated"])) > 1e-9: errors.append(f"SUMMARY_TOTAL_MISMATCH:{sid}")
        if (pd.to_numeric(rows["scenario_weight"], errors="coerce").fillna(0.0) <= 0).any(): errors.append(f"NONPOSITIVE_WEIGHT:{sid}")

        sector = rows.groupby("economic_sector_industry")["scenario_weight"].sum().astype(float)
        style = rows.groupby("portfolio_style")["scenario_weight"].sum().astype(float)
        if len(sector) and sector.max() > target * sector_frac_limit + 1e-9: errors.append(f"SLEEVE_SECTOR_LIMIT:{sid}")
        if len(style) and style.max() > target * style_frac_limit + 1e-9: errors.append(f"SLEEVE_STYLE_LIMIT:{sid}")
        stress = pd.to_numeric(rows["gross_drawdown_stress_weight"], errors="coerce").fillna(0.0).sum()
        if stress > target * stress_fraction + 1e-9: errors.append(f"STRESS_LIMIT:{sid}")

        new_rows = rows[rows["allocation_type"].eq("NEW_BUILD")]
        for _, r in new_rows.iterrows():
            key = (str(r["security_id"]), account)
            if key not in p4_idx.index:
                errors.append(f"NEW_BUILD_NOT_IN_P4_2:{sid}:{key[0]}")
                continue
            p = p4_idx.loc[key]
            if isinstance(p, pd.DataFrame): p = p.iloc[0]
            if str(p["construction_state"]) not in {"PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW", "PROBE_BUILD_REVIEW"}:
                errors.append(f"NON_ACTIONABLE_NEW_BUILD:{sid}:{key[0]}")
            if f(r["scenario_weight"]) > f(p["suggested_weight_max"]) + 1e-9:
                errors.append(f"P4_2_MAX_EXCEEDED:{sid}:{key[0]}")
            if f(r["scenario_weight"]) < min_pos - 1e-9:
                errors.append(f"BELOW_SCENARIO_MIN_POSITION:{sid}:{key[0]}")

        for sector_name, grp in new_rows.groupby("economic_sector_industry"):
            candidate_rows = p4_2_review[(p4_2_review["account"].eq(account)) & (p4_2_review["economic_sector_industry"].eq(sector_name))]
            baseline = pd.to_numeric(candidate_rows["existing_same_sector_weight"], errors="coerce").fillna(0.0).max() if len(candidate_rows) else 0.0
            if baseline + pd.to_numeric(grp["scenario_weight"], errors="coerce").fillna(0.0).sum() > sector_abs_limit + 1e-9:
                errors.append(f"ABSOLUTE_SECTOR_LIMIT:{sid}:{sector_name}")
        for style_name, grp in new_rows.groupby("portfolio_style"):
            candidate_rows = p4_2_review[(p4_2_review["account"].eq(account)) & (p4_2_review["portfolio_style"].eq(style_name))]
            baseline = pd.to_numeric(candidate_rows["construction_existing_direct_same_style_weight"], errors="coerce").fillna(0.0).max() if len(candidate_rows) else 0.0
            if baseline + pd.to_numeric(grp["scenario_weight"], errors="coerce").fillna(0.0).sum() > style_abs_limit + 1e-9:
                errors.append(f"ABSOLUTE_STYLE_LIMIT:{sid}:{style_name}")

        sub_rows = rows[rows["allocation_type"].eq("AH_SUBSTITUTION")]
        if family == "BASE_NEW_BUILD" and len(sub_rows): errors.append(f"BASE_FORCED_SUBSTITUTION:{sid}")
        if family == "MAX_AH_SUBSTITUTION_STRESS":
            if account != "SIMULATION": errors.append(f"AH_STRESS_WRONG_ACCOUNT:{sid}")
            if len(sub_rows) != len(p4_2_sub[p4_2_sub["account"].eq(account)]): errors.append(f"AH_STRESS_OPTION_COUNT:{sid}")
        for _, r in sub_rows.iterrows():
            match = p4_2_sub[(p4_2_sub["account"].eq(account)) & (p4_2_sub["security_id"].eq(str(r["security_id"])))]
            if len(match) != 1:
                errors.append(f"SUBSTITUTION_NOT_IN_P4_2:{sid}:{r['security_id']}")
                continue
            p = match.iloc[0]
            if f(r["scenario_weight"]) > f(p["replacement_equivalent_weight_cap"]) + 1e-9: errors.append(f"SUB_CAP_EXCEEDED:{sid}:{r['security_id']}")
            if f(r["scenario_weight"]) > f(p["existing_overlap_weight"]) + 1e-9: errors.append(f"SUB_EXISTING_OVERLAP_EXCEEDED:{sid}:{r['security_id']}")
            if abs(f(r["paired_reduction_weight"]) - f(r["scenario_weight"])) > 1e-9: errors.append(f"SUB_NOT_EQUAL_WEIGHT:{sid}:{r['security_id']}")
            if abs(f(r["net_new_capital_weight"])) > 1e-12: errors.append(f"SUB_NET_NEW_CAPITAL:{sid}:{r['security_id']}")

        if account == "REAL":
            if f(s["new_build_weight"]) > 0 and str(s["funding_status"]) != "FEASIBLE_WITH_EXTERNAL_FUNDING_DEPENDENCY": errors.append(f"REAL_FUNDING_SEMANTICS:{sid}")
        else:
            if f(s["funding_gap_weight"]) > 1e-12: errors.append(f"SIM_FUNDING_GAP:{sid}")
            if str(s["funding_status"]) != "FEASIBLE_WITH_SIMULATION_CASH": errors.append(f"SIM_FUNDING_SEMANTICS:{sid}")

    if len(ah_options) != len(p4_2_sub): errors.append("AH_OPTIONS_COUNT")
    if len(ah_options) and pd.to_numeric(ah_options["net_new_capital_weight"], errors="coerce").fillna(0.0).abs().max() > 1e-12: errors.append("AH_OPTION_NET_NEW")

    if decision.get("portfolio_proposal_produced") is not False: errors.append("PORTFOLIO_PROPOSAL_PRODUCED")
    if decision.get("target_portfolio_writeback") is not False: errors.append("TARGET_WRITEBACK")
    if int(decision.get("orders_created", -1)) != 0: errors.append("DECISION_ORDERS")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("DECISION_AUTHORITY")

    for flag in ("weighted_score", "fixed_top_n", "candidate_rank_used_as_allocation_authority", "real_cash_treated_as_strategic_target", "real_existing_positions_auto_reduced", "portfolio_proposal_produced"):
        if quality.get(flag) is not False: errors.append(f"QUALITY_FALSE_FLAG:{flag}")
    for flag in ("p4_2_envelopes_respected", "aggregate_hk_sleeve_limit_enforced", "aggregate_sector_style_limits_enforced", "gross_drawdown_stress_budget_enforced", "simulation_cash_is_funding_context", "ah_substitution_net_capital_neutral", "ah_substitution_same_issuer_reduction_required"):
        if quality.get(flag) is not True: errors.append(f"QUALITY_TRUE_FLAG:{flag}")

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "scenario_count": len(summary),
        "allocation_row_count": len(allocations),
        "ah_option_count": len(ah_options),
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
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    validate(Path(args.repo_root).resolve(), Path(args.p4_2_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
