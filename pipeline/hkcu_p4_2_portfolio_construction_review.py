#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import hkcu_p4_1_portfolio_fit_assessment as base

PROGRAM_ID = "HKCU-P4-2"
TRADE_AUTHORITY = "NONE"
ACCOUNTS = ("REAL", "SIMULATION")
POSITIVE_FIT = {"FIT", "FIT_WITH_CONSTRAINTS"}
ACTIONABLE_NEW_SIZE = {"PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW", "PROBE_BUILD_REVIEW"}


def finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def split_pipe(value: Any) -> list[str]:
    return [x for x in str(value or "").split("|") if x]


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def account_assets(state: dict[str, Any]) -> float:
    summary = state.get("summary", {})
    for key in ("account_total_assets", "total_assets", "portfolio_total_assets", "position_market_value"):
        v = finite(summary.get(key))
        if v is not None and v > 0:
            return v
    mv = sum(finite(x.get("market_value")) or 0.0 for x in state.get("holdings", []))
    cash = finite(summary.get("execution_cash_balance")) or finite(summary.get("available_cash")) or 0.0
    return mv + cash


def account_cash(state: dict[str, Any]) -> float:
    summary = state.get("summary", {})
    for key in ("execution_cash_balance", "available_cash", "cash_balance", "cash"):
        v = finite(summary.get(key))
        if v is not None:
            return v
    return 0.0


def holding_weight(state: dict[str, Any], security_ids: list[str]) -> float:
    assets = account_assets(state)
    if assets <= 0 or not security_ids:
        return 0.0
    target = set(security_ids)
    mv = sum((finite(x.get("market_value")) or 0.0) for x in state.get("holdings", []) if str(x.get("security_id")) in target)
    return mv / assets


def classify_state(row: pd.Series, candidate: pd.Series, account: str) -> tuple[str, list[str]]:
    fit = str(row.get("fit_state"))
    opp = str(row.get("opportunity_cost_state"))
    risk = str(row.get("marginal_risk_state"))
    sector_inc = str(row.get("sector_impact_state")) == "INCREASES_EXISTING_DIRECT_SECTOR"
    style_inc = str(row.get("style_impact_state")) == "INCREASES_EXISTING_STYLE"
    ah = split_pipe(row.get("ah_overlap_security_ids"))
    direct = split_pipe(row.get("direct_overlap_security_ids"))
    material = as_int(candidate.get("material_confidence_cap_count"))
    bounded = as_int(candidate.get("bounded_confidence_cap_count"))
    thesis = str(candidate.get("thesis_strength"))
    reasons: list[str] = []

    if fit == "NO_INCREMENTAL_ROLE" or direct:
        reasons.append("P4_1_NO_INCREMENTAL_OR_DIRECT_EXISTING_OVERLAP")
        return "NO_INCREMENTAL_ROLE", reasons
    if fit not in POSITIVE_FIT:
        reasons.append(f"P4_1_FIT_STATE={fit}")
        return "WATCH_NO_SIZE", reasons
    if ah:
        reasons.append("EXACT_AH_OVERLAP_REQUIRES_SUBSTITUTION_REVIEW")
        return "SUBSTITUTION_REVIEW_ONLY", reasons
    if opp == "HIGH_RELATIVE_OPPORTUNITY_COST":
        reasons.append("HIGH_RELATIVE_OPPORTUNITY_COST")
        return "WATCH_NO_SIZE", reasons
    if account == "REAL" and material > 0:
        reasons.append("MATERIAL_CONFIDENCE_CAP_REAL_ACCOUNT")
        return "WATCH_NO_SIZE", reasons
    if material > 0 or bounded >= 2:
        reasons.append("EVIDENCE_CONFIDENCE_REQUIRES_PROBE")
        return "PROBE_BUILD_REVIEW", reasons
    if thesis == "QUANTITATIVE_ONLY_WITH_COMPANY_MONITOR":
        reasons.append("QUANTITATIVE_ONLY_THESIS_REQUIRES_PROBE")
        return "PROBE_BUILD_REVIEW", reasons
    if opp == "LOW_RELATIVE_OPPORTUNITY_COST" and risk == "IMPROVES_DIVERSIFICATION" and not (sector_inc and style_inc):
        reasons.append("LOW_OPPORTUNITY_COST_AND_DIVERSIFICATION")
        return "PRIMARY_BUILD_REVIEW", reasons
    if opp in {"LOW_RELATIVE_OPPORTUNITY_COST", "MODERATE_RELATIVE_OPPORTUNITY_COST"} and risk in {"IMPROVES_DIVERSIFICATION", "DIVERSIFIES_RETURN_STREAM_BUT_RAISES_RISK_BUDGET"} and not (sector_inc and style_inc):
        reasons.append("ACCEPTABLE_OPPORTUNITY_COST_WITH_BOUNDED_RISK")
        return "SECONDARY_BUILD_REVIEW", reasons
    reasons.append("POSITIVE_FIT_BUT_REQUIRES_PROBE")
    return "PROBE_BUILD_REVIEW", reasons


def independent_caps(row: pd.Series, candidate: pd.Series, hk: pd.Series, account: str, state: dict[str, Any], policy: dict[str, Any]) -> dict[str, float]:
    tier = str(candidate.get("candidate_tier") or row.get("candidate_tier"))
    tier_cap = float(policy["tier_weight_cap"][tier])
    ref_weight = float(policy["tier_risk_reference_weight"][tier])
    loss_budget = float(policy["single_name_loss_budget"][tier])
    assets = account_assets(state)

    cand_vol = finite(row.get("candidate_annualized_volatility"))
    port_vol = finite(row.get("portfolio_annualized_volatility"))
    vol_cap = tier_cap
    if cand_vol is not None and cand_vol > 0 and port_vol is not None and port_vol > 0:
        vol_cap = min(tier_cap, max(0.0, ref_weight * port_vol / cand_vol))

    dd = finite(row.get("max_drawdown_120d"))
    drawdown_abs = max(abs(dd) if dd is not None else float(policy["drawdown_floor_abs"]), float(policy["drawdown_floor_abs"]))
    loss_cap = min(tier_cap, loss_budget / drawdown_abs)

    risk_mult = float(policy["marginal_risk_multiplier"].get(str(row.get("marginal_risk_state")), 0.0))
    risk_cap = tier_cap * risk_mult
    opp_mult = float(policy["opportunity_cost_multiplier"].get(str(row.get("opportunity_cost_state")), 0.0))
    opportunity_cap = tier_cap * opp_mult

    material = as_int(candidate.get("material_confidence_cap_count"))
    bounded = as_int(candidate.get("bounded_confidence_cap_count"))
    thesis = str(candidate.get("thesis_strength"))
    confidence_cap = tier_cap
    if material > 0:
        confidence_cap = float(policy["material_confidence_cap"][account])
    elif bounded >= 2:
        confidence_cap = min(confidence_cap, float(policy["bounded_confidence_cap_two_plus"]))
    if thesis == "QUANTITATIVE_ONLY_WITH_COMPANY_MONITOR":
        confidence_cap = min(confidence_cap, float(policy["quantitative_only_thesis_cap"]))

    sector_cap = tier_cap
    if str(row.get("sector_impact_state")) == "INCREASES_EXISTING_DIRECT_SECTOR":
        sector_cap = max(0.0, float(policy["direct_sector_weight_limit"]) - (finite(row.get("existing_same_sector_weight")) or 0.0))
    style_cap = tier_cap
    if str(row.get("style_impact_state")) == "INCREASES_EXISTING_STYLE":
        style_cap = max(0.0, float(policy["direct_style_weight_limit"]) - (finite(row.get("existing_same_style_weight")) or 0.0))

    adv = finite(hk.get("avg_turnover_hkd_20d"))
    liquidity_cap = tier_cap
    if adv is not None and adv > 0 and assets > 0:
        liquidity_cap = min(tier_cap, adv * float(policy["max_position_fraction_of_adv"]) / assets)

    return {
        "tier_cap": max(0.0, tier_cap),
        "volatility_cap": max(0.0, vol_cap),
        "historical_drawdown_loss_cap": max(0.0, loss_cap),
        "marginal_risk_cap": max(0.0, risk_cap),
        "opportunity_cost_cap": max(0.0, opportunity_cap),
        "confidence_cap": max(0.0, confidence_cap),
        "sector_room_cap": max(0.0, sector_cap),
        "style_room_cap": max(0.0, style_cap),
        "liquidity_cap": max(0.0, liquidity_cap),
    }


def apply_envelope(construction_state: str, caps: dict[str, float], policy: dict[str, Any], account: str) -> tuple[float, float, float]:
    if construction_state not in ACTIONABLE_NEW_SIZE:
        return 0.0, 0.0, 0.0
    cap = min(caps.values()) if caps else 0.0
    if construction_state == "PROBE_BUILD_REVIEW":
        cap = min(cap, float(policy["probe_hard_cap"][account]))
    if cap < float(policy["minimum_actionable_weight"]):
        return 0.0, 0.0, cap
    frac = policy["suggested_range_fraction"][construction_state]
    return cap * float(frac["min"]), cap * float(frac["max"]), cap


def combined_route(real_state: str, sim_state: str) -> str:
    real_new = real_state in ACTIONABLE_NEW_SIZE
    sim_new = sim_state in ACTIONABLE_NEW_SIZE
    if real_new and sim_new:
        return "ADVANCE_DUAL_SCENARIO_TEST"
    if real_new:
        return "ADVANCE_REAL_SCENARIO_TEST"
    if sim_new:
        return "ADVANCE_SIMULATION_SCENARIO_TEST"
    if "SUBSTITUTION_REVIEW_ONLY" in {real_state, sim_state}:
        return "ADVANCE_SUBSTITUTION_SCENARIO_TEST"
    return "HOLD_PORTFOLIO_WATCH"


def build(root: Path, context_dir: Path, fit_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    a = contract["authoritative_inputs"]
    policy = contract["construction_policy"]

    candidates = pd.read_csv(root / a["candidate_current"], dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    hkcu = pd.read_csv(root / a["hkcu_current"], dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    states = {"REAL": read_json(root / a["real_positions_current"]), "SIMULATION": read_json(root / a["simulation_positions_current"])}
    fit_decision = read_json(fit_dir / "HKCU_P4_1_REASSESSMENT_DECISION.json")
    fit = pd.read_csv(fit_dir / "HKCU_P4_1_REASSESSMENT_ACCOUNT_SECURITY_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    fit_combined = pd.read_csv(fit_dir / "HKCU_P4_1_REASSESSMENT_COMBINED_ROUTING.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    ctx_decision = read_json(context_dir / "HKCU_P4_1R_DECISION.json")
    ctx = pd.read_csv(context_dir / "HKCU_P4_1R_ACCOUNT_SECURITY_CONTEXT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    failures: list[str] = []
    if fit_decision.get("status") != contract["entry_contract"]["required_p4_1_status"]:
        failures.append("P4_1_STATUS")
    if ctx_decision.get("status") != contract["entry_contract"]["required_p4_1r_status"]:
        failures.append("P4_1R_STATUS")
    if len(candidates) != 70 or candidates["security_id"].nunique() != 70:
        failures.append("CANDIDATE_COUNT")
    if len(fit) != 140 or fit.duplicated(["security_id", "account"]).any():
        failures.append("FIT_SURFACE")
    if len(ctx) != 140 or ctx.duplicated(["security_id", "account"]).any():
        failures.append("CONTEXT_SURFACE")
    if len(fit_combined) != 70:
        failures.append("COMBINED_ROUTE_SURFACE")
    if any(states[x].get("trade_authority") != TRADE_AUTHORITY for x in ACCOUNTS):
        failures.append("ACCOUNT_AUTHORITY")

    cand_idx = candidates.set_index("security_id", drop=False)
    hk_idx = hkcu.set_index("security_id", drop=False)
    ctx_idx = ctx.set_index(["security_id", "account"], drop=False)
    rows: list[dict[str, Any]] = []
    substitution_rows: list[dict[str, Any]] = []

    for r in fit.sort_values(["p2a_overall_rank", "account"]).itertuples(index=False):
        sid, account = str(r.security_id), str(r.account)
        c = cand_idx.loc[sid]
        if isinstance(c, pd.DataFrame): c = c.iloc[0]
        h = hk_idx.loc[sid]
        if isinstance(h, pd.DataFrame): h = h.iloc[0]
        x = ctx_idx.loc[(sid, account)]
        if isinstance(x, pd.DataFrame): x = x.iloc[0]
        fit_row = pd.Series(r._asdict())
        merged = fit_row.copy()
        for col in x.index:
            if col not in merged.index or str(merged.get(col, "")) in {"", "nan"}:
                merged[col] = x[col]

        construction_state, reasons = classify_state(merged, c, account)
        caps = independent_caps(merged, c, h, account, states[account], policy)
        suggested_min, suggested_max, analytical_cap = apply_envelope(construction_state, caps, policy, account)
        if construction_state in ACTIONABLE_NEW_SIZE and suggested_max <= 0:
            construction_state = "WATCH_NO_SIZE"
            reasons.append("ANALYTICAL_CAP_BELOW_MINIMUM_ACTIONABLE_WEIGHT")
        if construction_state == "WATCH_NO_SIZE":
            suggested_min = suggested_max = 0.0

        ah_ids = split_pipe(merged.get("ah_overlap_security_ids"))
        ah_weight = holding_weight(states[account], ah_ids)
        replacement_cap = 0.0
        if construction_state == "SUBSTITUTION_REVIEW_ONLY":
            replacement_cap = min(min(caps.values()), ah_weight) if ah_weight > 0 else 0.0
            substitution_rows.append({
                "p2a_overall_rank": int(r.p2a_overall_rank),
                "security_id": sid,
                "stock_code_5d": str(r.stock_code_5d).zfill(5),
                "security_name": str(r.security_name),
                "account": account,
                "overlap_security_ids": "|".join(ah_ids),
                "existing_overlap_weight": ah_weight,
                "replacement_equivalent_weight_cap": replacement_cap,
                "net_new_weight_authorized": 0.0,
                "review_semantics": "COMPARE_H_VS_EXISTING_A_OR_OTHER_EXACT_SAME_ISSUER_EXPOSURE_BEFORE_ANY_REPLACEMENT_PROPOSAL",
                "portfolio_mutation": False,
                "orders_created": 0,
                "trade_authority": TRADE_AUTHORITY,
            })

        assets = account_assets(states[account])
        cash = account_cash(states[account])
        funding = "NO_FUNDING_NO_SIZE"
        if construction_state in ACTIONABLE_NEW_SIZE:
            if account == "REAL":
                funding = "EXTERNAL_LIQUIDITY_OR_SEPARATE_CAPITAL_DECISION_REQUIRED" if cash <= 0 else "BROKER_EXECUTION_CASH_OR_SEPARATE_CAPITAL_DECISION"
            else:
                funding = "SIMULATION_AVAILABLE_CASH_OR_REBALANCE_REVIEW"

        dd = finite(merged.get("max_drawdown_120d"))
        max_loss = suggested_max * (abs(dd) if dd is not None else float(policy["drawdown_floor_abs"]))
        peer_group = "|".join([str(merged.get("economic_sector_industry")), str(merged.get("portfolio_style")), str(merged.get("portfolio_role"))])
        rows.append({
            "p2a_overall_rank": int(r.p2a_overall_rank),
            "security_id": sid,
            "stock_code_5d": str(r.stock_code_5d).zfill(5),
            "security_name": str(r.security_name),
            "candidate_tier": str(c.get("candidate_tier")),
            "account": account,
            "p4_1_fit_state": str(r.fit_state),
            "p4_1_constraints": str(r.constraints),
            "construction_state": construction_state,
            "construction_reasons": "|".join(reasons),
            "portfolio_role": str(r.portfolio_role),
            "economic_sector_industry": str(r.economic_sector_industry),
            "portfolio_style": str(r.portfolio_style),
            "sector_impact_state": str(r.sector_impact_state),
            "style_impact_state": str(r.style_impact_state),
            "direct_overlap_security_ids": str(r.direct_overlap_security_ids),
            "ah_overlap_security_ids": str(r.ah_overlap_security_ids),
            "peer_group": peer_group,
            "marginal_risk_state": str(r.marginal_risk_state),
            "opportunity_cost_state": str(r.opportunity_cost_state),
            "candidate_portfolio_correlation": finite(merged.get("candidate_portfolio_correlation")),
            "downside_correlation": finite(merged.get("downside_correlation")),
            "candidate_annualized_volatility": finite(merged.get("candidate_annualized_volatility")),
            "portfolio_annualized_volatility": finite(merged.get("portfolio_annualized_volatility")),
            "max_drawdown_120d": dd,
            "existing_same_sector_weight": finite(merged.get("existing_same_sector_weight")),
            "existing_same_style_weight": finite(merged.get("existing_same_style_weight")),
            "avg_turnover_hkd_20d": finite(h.get("avg_turnover_hkd_20d")),
            "material_confidence_cap_count": as_int(c.get("material_confidence_cap_count")),
            "bounded_confidence_cap_count": as_int(c.get("bounded_confidence_cap_count")),
            "thesis_strength": str(c.get("thesis_strength")),
            "tier_cap": caps["tier_cap"],
            "volatility_cap": caps["volatility_cap"],
            "historical_drawdown_loss_cap": caps["historical_drawdown_loss_cap"],
            "marginal_risk_cap": caps["marginal_risk_cap"],
            "opportunity_cost_cap": caps["opportunity_cost_cap"],
            "confidence_cap": caps["confidence_cap"],
            "sector_room_cap": caps["sector_room_cap"],
            "style_room_cap": caps["style_room_cap"],
            "liquidity_cap": caps["liquidity_cap"],
            "analytical_weight_cap": analytical_cap if construction_state in ACTIONABLE_NEW_SIZE else 0.0,
            "suggested_weight_min": suggested_min,
            "suggested_weight_max": suggested_max,
            "historical_drawdown_loss_at_suggested_max": max_loss,
            "existing_ah_overlap_weight": ah_weight,
            "replacement_equivalent_weight_cap": replacement_cap,
            "account_total_assets": assets,
            "account_execution_or_available_cash": cash,
            "funding_source_class": funding,
            "principal_falsifier": str(c.get("principal_falsifier")),
            "review_triggers": str(c.get("monitor_triggers")),
            "individual_envelope_is_non_additive": True,
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })

    review = pd.DataFrame(rows).sort_values(["p2a_overall_rank", "account"]).reset_index(drop=True)
    substitutions = pd.DataFrame(substitution_rows)
    combined_rows: list[dict[str, Any]] = []
    for sid, group in review.groupby("security_id", sort=False):
        states_map = dict(zip(group["account"], group["construction_state"]))
        first = group.sort_values("account").iloc[0]
        combined_rows.append({
            "p2a_overall_rank": int(first["p2a_overall_rank"]),
            "security_id": sid,
            "stock_code_5d": first["stock_code_5d"],
            "security_name": first["security_name"],
            "candidate_tier": first["candidate_tier"],
            "real_construction_state": states_map.get("REAL", "MISSING"),
            "simulation_construction_state": states_map.get("SIMULATION", "MISSING"),
            "combined_route": combined_route(states_map.get("REAL", "MISSING"), states_map.get("SIMULATION", "MISSING")),
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })
    combined = pd.DataFrame(combined_rows).sort_values("p2a_overall_rank").reset_index(drop=True)

    if len(review) != contract["acceptance"]["account_security_review_count"]:
        failures.append(f"REVIEW_COUNT:{len(review)}")
    if len(combined) != contract["acceptance"]["combined_security_count"]:
        failures.append(f"COMBINED_COUNT:{len(combined)}")
    if review.duplicated(["security_id", "account"]).any():
        failures.append("DUPLICATE_REVIEW_ROW")

    status = contract["acceptance"]["pass_status"] if not failures else contract["acceptance"]["integrity_fail_status"]
    state_counts = {
        account: review.loc[review["account"].eq(account), "construction_state"].value_counts().astype(int).to_dict()
        for account in ACCOUNTS
    }
    route_counts = combined["combined_route"].value_counts().astype(int).to_dict()
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_p4_1_status": fit_decision.get("status"),
        "entry_p4_1r_status": ctx_decision.get("status"),
        "account_security_review_count": len(review),
        "combined_security_count": len(combined),
        "construction_state_counts": state_counts,
        "combined_route_counts": route_counts,
        "actionable_new_size_count": int(review["construction_state"].isin(ACTIONABLE_NEW_SIZE).sum()),
        "substitution_review_count": int((review["construction_state"] == "SUBSTITUTION_REVIEW_ONLY").sum()),
        "watch_no_size_count": int((review["construction_state"] == "WATCH_NO_SIZE").sum()),
        "no_incremental_role_count": int((review["construction_state"] == "NO_INCREMENTAL_ROLE").sum()),
        "individual_envelopes_non_additive": True,
        "aggregate_portfolio_allocation_produced": False,
        "portfolio_allocations": 0,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "next_gate": contract["acceptance"]["next_gate_on_pass"] if status == contract["acceptance"]["pass_status"] else contract["acceptance"]["repair_gate"],
        "integrity_failures": failures,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not failures else "FAIL",
        "weighted_score": False,
        "fixed_top_n": False,
        "candidate_rank_used_as_allocation_authority": False,
        "independent_caps_use_minimum_not_offsetting_score": True,
        "exact_ah_net_new_size_authorized": False,
        "high_opportunity_cost_new_size_authorized": False,
        "real_cash_treated_as_strategic_target": False,
        "individual_caps_called_aggregate_portfolio": False,
        "aggregate_scenario_test_required_before_portfolio_proposal": True,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "hard_failures": failures,
    }

    prefix = contract["output_prefix"]
    review_file = out / f"{prefix}_ACCOUNT_SECURITY_REVIEW.csv"
    combined_file = out / f"{prefix}_COMBINED_ROUTING.csv"
    substitution_file = out / f"{prefix}_SUBSTITUTION_REGISTER.csv"
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    report_file = out / f"{prefix}_ASSESSMENT.md"
    manifest_file = out / f"{prefix}_MANIFEST.json"

    review.to_csv(review_file, index=False)
    combined.to_csv(combined_file, index=False)
    substitutions.to_csv(substitution_file, index=False)
    write_json(decision_file, decision)
    write_json(quality_file, quality)

    lines = [
        "# HKCU P4-2 Portfolio Construction Review",
        "",
        f"Status: **{status}**",
        "",
        f"- Account × Security reviews: {len(review)}",
        f"- Actionable new-size review rows: {decision['actionable_new_size_count']}",
        f"- Substitution-only rows: {decision['substitution_review_count']}",
        f"- Watch/no-size rows: {decision['watch_no_size_count']}",
        f"- No-incremental-role rows: {decision['no_incremental_role_count']}",
        f"- Next gate: {decision['next_gate']}",
        "",
        "## Construction state counts",
        "",
        f"- REAL: {state_counts['REAL']}",
        f"- SIMULATION: {state_counts['SIMULATION']}",
        f"- Combined routes: {route_counts}",
        "",
        "## Important boundary",
        "",
        "All suggested ranges and caps are single-security analytical envelopes. They are intentionally non-additive and are not a portfolio allocation. P4-3 must assemble complete scenarios under aggregate sleeve, sector/style, funding and risk budgets before any portfolio proposal can exist.",
        "",
        "No Candidate, Simulation, Real Account, allocation or order state is mutated. trade_authority=NONE.",
        "",
    ]
    report_file.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "program_id": PROGRAM_ID,
        "status": status,
        "as_of_date": contract["as_of_date"],
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for path in (review_file, combined_file, substitution_file, decision_file, quality_file, report_file):
        manifest["files"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(manifest_file, manifest)

    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--context-dir", required=True)
    ap.add_argument("--fit-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.context_dir).resolve(), Path(args.fit_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
