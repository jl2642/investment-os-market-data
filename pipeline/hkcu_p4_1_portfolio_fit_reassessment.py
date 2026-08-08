#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import hkcu_p4_1_portfolio_fit_assessment as base

PROGRAM_ID = "HKCU-P4-1-REASSESSMENT"
TRADE_AUTHORITY = "NONE"
ACCOUNTS = ("REAL", "SIMULATION")
POSITIVE = {"FIT", "FIT_WITH_CONSTRAINTS"}


def boolish(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def split_ids(value: Any) -> list[str]:
    return [x for x in str(value or "").split("|") if x]


def combined_route(real_state: str, simulation_state: str) -> str:
    states = {real_state, simulation_state}
    if real_state == "BLOCK_PORTFOLIO_FIT" and simulation_state == "BLOCK_PORTFOLIO_FIT":
        return "BLOCK_PORTFOLIO_FIT"
    if "DEFER_PORTFOLIO_CONTEXT" in states:
        return "DEFER_PORTFOLIO_CONTEXT"
    if real_state in POSITIVE and simulation_state in POSITIVE:
        return "ADVANCE_DUAL_CONSTRUCTION_REVIEW"
    if real_state in POSITIVE:
        return "ADVANCE_REAL_ACCOUNT_REVIEW"
    if simulation_state in POSITIVE:
        return "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW"
    return "HOLD_PORTFOLIO_WATCH"


def compound_no_incremental(ctx: pd.Series) -> bool:
    return (
        str(ctx.get("marginal_risk_state")) == "ADDS_CORRELATED_RISK"
        and str(ctx.get("opportunity_cost_state")) == "HIGH_RELATIVE_OPPORTUNITY_COST"
        and str(ctx.get("sector_impact_state")) == "INCREASES_EXISTING_DIRECT_SECTOR"
        and str(ctx.get("style_impact_state")) == "INCREASES_EXISTING_STYLE"
    )


def runtime_context_gaps(decision: dict[str, Any], gaps: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, str]]:
    req = contract["runtime_context_contract"]
    problems: list[str] = []
    checks = {
        "program_id": decision.get("program_id") == req["required_program_id"],
        "status": decision.get("status") == req["required_status"],
        "candidate_context_count": int(decision.get("candidate_context_count", -1)) == req["required_candidate_context_count"],
        "account_holding_context_count": int(decision.get("account_holding_context_count", -1)) == req["required_account_holding_context_count"],
        "account_security_context_count": int(decision.get("account_security_context_count", -1)) == req["required_account_security_context_count"],
        "context_ready_account_security_count": int(decision.get("context_ready_account_security_count", -1)) == req["required_context_ready_account_security_count"],
        "exact_ah_mapped_count": int(decision.get("exact_ah_mapped_count", -1)) == req["required_exact_ah_mapped_count"],
        "candidate_industry_coverage": float(decision.get("candidate_industry_coverage", -1)) == float(req["required_candidate_industry_coverage"]),
        "residual_decision_critical_gap_count": int(decision.get("residual_decision_critical_gap_count", -1)) == req["required_residual_gap_count"],
        "trade_authority": decision.get("trade_authority") == req["required_trade_authority"],
        "residual_file_empty": gaps.empty,
    }
    problems.extend(k for k, ok in checks.items() if not ok)
    if not problems:
        return []
    return [{
        "context_id": "P4_1R_RUNTIME_CONTEXT",
        "status": "MISSING_OR_INVALID_DECISION_CRITICAL_CONTEXT",
        "affects_rules": "P4R07|P4R09|P4R10|P4R11|P4R12|P4R13",
        "rationale": "Accepted P4-1R runtime context gate is not fully satisfied: " + ",".join(problems),
        "required_repair": "Re-run and pass P4-1R Portfolio Context Completion before reassessment."
    }]


def role_from_context(ctx: pd.Series, sleeve: str) -> str:
    style = str(ctx.get("portfolio_style") or "").strip()
    if style:
        return style
    return base.role_from_sleeve(sleeve)


def build(root: Path, context_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p4_1_portfolio_fit_reassessment_contract.json"
    contract = base.read_json(contract_path)
    auth = contract["authoritative_inputs"]
    p4_path = root / auth["p4_0_contract"]
    p4_1_path = root / auth["p4_1_contract"]
    p4_1r_path = root / auth["p4_1r_contract"]
    candidate_path = root / auth["candidate_current"]
    hkcu_path = root / auth["hkcu_current"]
    real_path = root / auth["real_positions_current"]
    sim_path = root / auth["simulation_positions_current"]

    p4 = base.read_json(p4_path)
    p4_1 = base.read_json(p4_1_path)
    p4_1r_contract = base.read_json(p4_1r_path)
    candidates = pd.read_csv(candidate_path, dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    hkcu = pd.read_csv(hkcu_path, dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    states = {"REAL": base.read_json(real_path), "SIMULATION": base.read_json(sim_path)}

    p4r_decision_file = context_dir / "HKCU_P4_1R_DECISION.json"
    p4r_manifest_file = context_dir / "HKCU_P4_1R_MANIFEST.json"
    p4r_candidate_file = context_dir / "HKCU_P4_1R_CANDIDATE_CONTEXT.csv"
    p4r_account_file = context_dir / "HKCU_P4_1R_ACCOUNT_SECURITY_CONTEXT.csv"
    p4r_gap_file = context_dir / "HKCU_P4_1R_RESIDUAL_GAPS.csv"
    p4r_decision = base.read_json(p4r_decision_file)
    p4r_manifest = base.read_json(p4r_manifest_file)
    p4r_candidate = pd.read_csv(p4r_candidate_file, dtype={"stock_code_5d": str, "a_share_code_6d": str}, keep_default_na=False)
    p4r_account = pd.read_csv(p4r_account_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    p4r_gaps = pd.read_csv(p4r_gap_file, keep_default_na=False)

    failures: list[str] = []
    entry = contract["entry_contract"]
    if p4.get("program_id") != "HKCU-P4-0": failures.append("P4_0_PROGRAM_ID")
    if p4_1.get("program_id") != "HKCU-P4-1": failures.append("P4_1_PROGRAM_ID")
    if p4_1r_contract.get("program_id") != "HKCU-P4-1R": failures.append("P4_1R_CONTRACT_PROGRAM_ID")
    if p4.get("as_of_date") != contract["as_of_date"] or p4_1.get("as_of_date") != contract["as_of_date"] or p4_1r_contract.get("as_of_date") != contract["as_of_date"]:
        failures.append("AS_OF_DATE_LINEAGE")
    if len(candidates) != entry["entry_candidate_count"]: failures.append(f"CANDIDATE_COUNT:{len(candidates)}")
    if candidates["security_id"].duplicated().any(): failures.append("DUPLICATE_CANDIDATE")
    if len(p4r_candidate) != 70 or p4r_candidate["security_id"].nunique() != 70: failures.append("P4_1R_CANDIDATE_CONTEXT")
    if len(p4r_account) != 140 or p4r_account.duplicated(["security_id", "account"]).any(): failures.append("P4_1R_ACCOUNT_CONTEXT")

    global_context_gaps = runtime_context_gaps(p4r_decision, p4r_gaps, contract)
    runtime_ok = not global_context_gaps
    rules = {r["rule_id"]: r for r in p4["portfolio_fit_rules"]}
    if set(rules) != {f"P4R{i:02d}" for i in range(1, 16)}: failures.append("P4_RULE_SET")

    hkcu_idx = hkcu.set_index("security_id", drop=False)
    ctx_idx = p4r_account.set_index(["security_id", "account"], drop=False)
    candidate_ctx_idx = p4r_candidate.set_index("security_id", drop=False)

    rule_rows: list[dict[str, Any]] = []
    account_rows: list[dict[str, Any]] = []

    for c in candidates.sort_values("p2a_overall_rank").itertuples(index=False):
        sid = str(c.security_id)
        code = base.code5(c.stock_code_5d)
        name = str(c.security_name)
        tier = str(c.candidate_tier)
        sleeve = str(c.primary_sleeve)
        h = hkcu_idx.loc[sid] if sid in hkcu_idx.index else None
        if isinstance(h, pd.DataFrame): h = h.iloc[0]
        cc = candidate_ctx_idx.loc[sid] if sid in candidate_ctx_idx.index else pd.Series(dtype=object)
        if isinstance(cc, pd.DataFrame): cc = cc.iloc[0]

        lineage_ok = str(c.candidate_status) == "ACTIVE" and base.as_bool(c.formal_candidate_graduation) and str(c.trade_authority) == TRADE_AUTHORITY
        investability_ok = h is not None and base.as_bool(h.get("publication_eligible")) and base.as_bool(h.get("buy_eligible")) and not base.as_bool(h.get("sell_only")) and str(h.get("freshness_status")) == "CURRENT"
        valuation_ok = str(c.valuation_support_state) not in {"", "MISSING", "ADVERSE_OR_UNUSABLE"}
        market_fresh = h is not None and str(h.get("market_latest_date", "")) >= "2026-08-06" and str(h.get("fmdl5e_as_of_date", "")) >= "2026-08-06"
        thesis_ok = bool(str(c.investment_thesis).strip() and str(c.principal_falsifier).strip() and str(c.monitor_triggers).strip())
        liquidity = base.f(h.get("avg_turnover_hkd_20d")) if h is not None else None
        liquidity_ok = liquidity is not None and liquidity > 0 and investability_ok

        for account in ACCOUNTS:
            state = states[account]
            ctx = ctx_idx.loc[(sid, account)] if (sid, account) in ctx_idx.index else pd.Series(dtype=object)
            if isinstance(ctx, pd.DataFrame): ctx = ctx.iloc[0]
            ctx_ready = runtime_ok and not ctx.empty and boolish(ctx.get("context_ready")) and str(ctx.get("trade_authority")) == TRADE_AUTHORITY
            account_ok = base.account_current_ok(state, p4)
            direct = split_ids(ctx.get("direct_overlap_security_ids"))
            ah_overlap = split_ids(ctx.get("ah_overlap_security_ids"))
            pooled = boolish(ctx.get("pooled_exposure_present"))
            role = role_from_context(ctx, sleeve)
            constraints: list[str] = []
            context_defers: list[str] = []
            hard_blocks: list[str] = []
            negative_role_reasons: list[str] = []
            base_row = {
                "p2a_overall_rank": int(c.p2a_overall_rank),
                "security_id": sid,
                "stock_code_5d": code,
                "security_name": name,
                "candidate_tier": tier,
                "account": account,
            }

            hard = {
                "P4R01": ("PASS" if lineage_ok else "BLOCK", f"candidate_status={c.candidate_status}; formal_candidate_graduation={c.formal_candidate_graduation}; trade_authority={c.trade_authority}."),
                "P4R02": ("PASS" if investability_ok else "BLOCK", f"publication_eligible={h.get('publication_eligible') if h is not None else None}; buy_eligible={h.get('buy_eligible') if h is not None else None}; sell_only={h.get('sell_only') if h is not None else None}; freshness={h.get('freshness_status') if h is not None else None}."),
                "P4R03": ("PASS" if market_fresh and valuation_ok else "DEFER", f"market_latest_date={h.get('market_latest_date') if h is not None else None}; fmdl5e_as_of_date={h.get('fmdl5e_as_of_date') if h is not None else None}; valuation_support_state={c.valuation_support_state}."),
                "P4R04": ("PASS" if account_ok else "DEFER", f"account_state_current={account_ok}; latest_mark_date={state.get('mark_watermark', {}).get('latest_mark_date')}."),
                "P4R05": ("PASS" if thesis_ok else "DEFER", f"thesis_present={bool(str(c.investment_thesis).strip())}; falsifier_present={bool(str(c.principal_falsifier).strip())}; monitor_present={bool(str(c.monitor_triggers).strip())}."),
                "P4R06": ("PASS" if liquidity_ok else "BLOCK", f"avg_turnover_hkd_20d={liquidity}; accepted investability remains={investability_ok}."),
                "P4R07": ("PASS" if ctx_ready else "DEFER", f"p4_1r_context_ready={ctx_ready}; ah_overlap_state={ctx.get('ah_overlap_state') if not ctx.empty else 'MISSING'}; exact_ah_code={cc.get('a_share_code_6d') if not cc.empty else ''}."),
            }
            for rid, (rule_state, rationale) in hard.items():
                base.add_rule(rule_rows, base_row, rules[rid], rule_state, rationale)
                if rule_state == "BLOCK": hard_blocks.append(rid)
                elif rule_state == "DEFER": context_defers.append(rid)

            base.add_rule(rule_rows, base_row, rules["P4R08"], "PASS", f"portfolio_role={role}; source=P4-1R common style context; original_primary_sleeve={sleeve}; descriptive only.")

            if not ctx_ready:
                r9_state, r9_note = "DEFER", "P4-1R overlap context is not ready."
                context_defers.append("P4R09")
            elif direct:
                r9_state, r9_note = "PASS_WITH_CONSTRAINTS", f"direct existing security overlap={direct}; no automatic rejection, but incremental role must be separately demonstrated."
                constraints.append("DIRECT_EXISTING_SECURITY_OVERLAP")
            elif ah_overlap:
                r9_state, r9_note = "PASS_WITH_CONSTRAINTS", f"exact A/H same-issuer overlap={ah_overlap}; substitution/duplication review required."
                constraints.append("EXACT_AH_OVERLAP")
            elif pooled:
                r9_state, r9_note = "PASS_WITH_CONSTRAINTS", "No direct or exact A/H overlap, but account contains explicit pooled equity exposure; pooled exposure is a named overlap constraint, not a defer."
                constraints.append("POOLED_EQUITY_EXPOSURE_PRESENT")
            else:
                r9_state, r9_note = "PASS", "No direct, exact A/H or pooled overlap constraint identified in accepted P4-1R context."
            base.add_rule(rule_rows, base_row, rules["P4R09"], r9_state, r9_note)

            sector_state = str(ctx.get("sector_impact_state")) if ctx_ready else "UNRESOLVED"
            sector_weight = base.f(ctx.get("existing_same_sector_weight")) if ctx_ready else None
            if not ctx_ready or not str(ctx.get("economic_sector_industry") or "").strip():
                r10_state = "DEFER"; context_defers.append("P4R10")
            elif sector_state == "INCREASES_EXISTING_DIRECT_SECTOR":
                r10_state = "PASS_WITH_CONSTRAINTS"; constraints.append("INCREASES_EXISTING_DIRECT_SECTOR")
            else:
                r10_state = "PASS"
            base.add_rule(rule_rows, base_row, rules["P4R10"], r10_state, f"sector={ctx.get('economic_sector_industry') if ctx_ready else 'UNRESOLVED'}; sector_impact_state={sector_state}; existing_same_sector_weight={sector_weight}.")

            style_state = str(ctx.get("style_impact_state")) if ctx_ready else "UNRESOLVED"
            style_weight = base.f(ctx.get("existing_same_style_weight")) if ctx_ready else None
            if not ctx_ready or not str(ctx.get("portfolio_style") or "").strip():
                r11_state = "DEFER"; context_defers.append("P4R11")
            elif style_state == "INCREASES_EXISTING_STYLE":
                r11_state = "PASS_WITH_CONSTRAINTS"; constraints.append("INCREASES_EXISTING_STYLE")
            else:
                r11_state = "PASS"
            base.add_rule(rule_rows, base_row, rules["P4R11"], r11_state, f"portfolio_style={ctx.get('portfolio_style') if ctx_ready else 'UNRESOLVED'}; style_impact_state={style_state}; existing_same_style_weight={style_weight}.")

            risk_state = str(ctx.get("marginal_risk_state")) if ctx_ready else "UNRESOLVED"
            risk_rule_state = contract["decision_policy"]["marginal_risk_states"].get(risk_state, "DEFER")
            if risk_rule_state == "DEFER": context_defers.append("P4R12")
            elif risk_rule_state == "PASS_WITH_CONSTRAINTS": constraints.append(risk_state)
            elif risk_rule_state == "NO_INCREMENTAL_ROLE": negative_role_reasons.append("MARGINAL_RISK_ADDS_CORRELATED_RISK")
            base.add_rule(rule_rows, base_row, rules["P4R12"], risk_rule_state, f"marginal_risk_state={risk_state}; correlation={ctx.get('candidate_portfolio_correlation') if ctx_ready else None}; downside_correlation={ctx.get('downside_correlation') if ctx_ready else None}; common_return_observations={ctx.get('common_return_observations') if ctx_ready else None}.")

            opp_state = str(ctx.get("opportunity_cost_state")) if ctx_ready else "UNRESOLVED"
            opp_rule_state = contract["decision_policy"]["opportunity_cost_states"].get(opp_state, "DEFER")
            if opp_rule_state == "DEFER": context_defers.append("P4R13")
            elif opp_rule_state == "PASS_WITH_CONSTRAINTS": constraints.append(opp_state)
            elif opp_rule_state == "NO_INCREMENTAL_ROLE": negative_role_reasons.append("HIGH_RELATIVE_OPPORTUNITY_COST")
            base.add_rule(rule_rows, base_row, rules["P4R13"], opp_rule_state, f"opportunity_cost_state={opp_state}; pareto_dominator_count={ctx.get('pareto_dominator_count') if ctx_ready else None}; valuation_anchor={ctx.get('valuation_anchor') if ctx_ready else None}; trailing_return_is_context_only=true.")

            direct_no_role = bool(direct)
            compound_no_role = ctx_ready and compound_no_incremental(ctx)
            if hard_blocks:
                envelope = contract["decision_policy"]["block_sizing_envelope"]
                r14_state = "PASS"
            elif context_defers:
                envelope = contract["decision_policy"]["defer_sizing_envelope"]
                r14_state = "PASS"
            elif direct_no_role or compound_no_role:
                envelope = contract["decision_policy"]["no_incremental_sizing_envelope"]
                r14_state = "PASS"
            else:
                envelope = contract["decision_policy"]["positive_assessment_sizing_envelope"]
                r14_state = "PASS_WITH_CONSTRAINTS"
                constraints.append("NUMERIC_SIZE_REQUIRES_P4_2")
            base.add_rule(rule_rows, base_row, rules["P4R14"], r14_state, f"analytical_sizing_envelope={envelope}; no numeric target, portfolio admission or position authority is created in reassessment.")

            cash = base.f(state.get("summary", {}).get("cash")) or base.f(state.get("summary", {}).get("available_cash")) or 0.0
            if account == "REAL":
                funding_note = f"broker execution cash={cash}; external liquidity excluded; no strategic cash target invented. Any later funding requires a separate capital decision."
                funding_state = "PASS_WITH_CONSTRAINTS" if cash <= 0 else "PASS"
                if cash <= 0: constraints.append("FUNDING_REQUIRES_SEPARATE_CAPITAL_DECISION")
            else:
                funding_note = f"simulation available cash={cash}; funding context only, not alpha or admission authority."
                funding_state = "PASS"
            base.add_rule(rule_rows, base_row, rules["P4R15"], funding_state, funding_note)

            if hard_blocks:
                fit_state = "BLOCK_PORTFOLIO_FIT"
                reason = "Substantive hard-rule failure(s): " + ",".join(sorted(set(hard_blocks)))
            elif context_defers:
                fit_state = "DEFER_PORTFOLIO_CONTEXT"
                reason = "Decision-critical context unresolved: " + ",".join(sorted(set(context_defers)))
            elif direct_no_role:
                fit_state = "NO_INCREMENTAL_ROLE"
                reason = "The exact security is already held; no incremental role is demonstrated at this assessment gate."
            elif compound_no_role:
                fit_state = "NO_INCREMENTAL_ROLE"
                reason = "Evidence jointly shows correlated risk, high relative opportunity cost, and added existing sector/style concentration; this is a portfolio-role conclusion, not a bearish company rejection."
            elif constraints:
                fit_state = "FIT_WITH_CONSTRAINTS"
                reason = "All hard rules pass; named construction constraints remain: " + ",".join(sorted(set(constraints)))
            else:
                fit_state = "FIT"
                reason = "All applicable hard and decision rules pass with no named constraint."

            account_rows.append({
                **base_row,
                "portfolio_role": role,
                "economic_sector_industry": ctx.get("economic_sector_industry") if ctx_ready else "",
                "portfolio_style": ctx.get("portfolio_style") if ctx_ready else "",
                "direct_overlap_security_ids": "|".join(direct),
                "ah_overlap_security_ids": "|".join(ah_overlap),
                "sector_impact_state": sector_state,
                "style_impact_state": style_state,
                "marginal_risk_state": risk_state,
                "opportunity_cost_state": opp_state,
                "negative_role_reasons": "|".join(sorted(set(negative_role_reasons))),
                "context_defer_rules": "|".join(sorted(set(context_defers))),
                "constraints": "|".join(sorted(set(constraints))),
                "fit_state": fit_state,
                "fit_reason": reason,
                "analytical_sizing_envelope": envelope,
                "portfolio_mutation": False,
                "orders_created": 0,
                "trade_authority": TRADE_AUTHORITY,
            })

    account_df = pd.DataFrame(account_rows).sort_values(["p2a_overall_rank", "account"]).reset_index(drop=True)
    rule_df = pd.DataFrame(rule_rows).sort_values(["p2a_overall_rank", "account", "rule_id"]).reset_index(drop=True)

    combined_rows: list[dict[str, Any]] = []
    for sid, g in account_df.groupby("security_id", sort=False):
        states_by_account = dict(zip(g["account"], g["fit_state"]))
        real_state = states_by_account["REAL"]
        simulation_state = states_by_account["SIMULATION"]
        row = g.iloc[0]
        combined_rows.append({
            "p2a_overall_rank": int(row["p2a_overall_rank"]),
            "security_id": sid,
            "stock_code_5d": row["stock_code_5d"],
            "security_name": row["security_name"],
            "candidate_tier": row["candidate_tier"],
            "real_fit_state": real_state,
            "simulation_fit_state": simulation_state,
            "combined_route": combined_route(real_state, simulation_state),
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })
    combined_df = pd.DataFrame(combined_rows).sort_values("p2a_overall_rank").reset_index(drop=True)

    if len(account_df) != entry["account_security_assessment_count"]: failures.append(f"ACCOUNT_ASSESSMENT_COUNT:{len(account_df)}")
    if len(rule_df) != entry["rule_assessment_row_count"]: failures.append(f"RULE_ROW_COUNT:{len(rule_df)}")
    if len(combined_df) != entry["combined_routing_count"]: failures.append(f"COMBINED_COUNT:{len(combined_df)}")
    if account_df.duplicated(["security_id", "account"]).any(): failures.append("DUPLICATE_ACCOUNT_ASSESSMENT")
    if rule_df.duplicated(["security_id", "account", "rule_id"]).any(): failures.append("DUPLICATE_RULE_ASSESSMENT")
    if not set(rule_df["rule_state"]).issubset(set(contract["rule_states"])): failures.append("RULE_STATE_VOCABULARY")
    if not set(account_df["fit_state"]).issubset(set(contract["account_fit_states"])): failures.append("FIT_STATE_VOCABULARY")
    if not set(combined_df["combined_route"]).issubset(set(contract["combined_routing_states"])): failures.append("ROUTE_VOCABULARY")

    prefix = contract["output_prefix"]
    account_file = out / f"{prefix}_ACCOUNT_SECURITY_ASSESSMENT.csv"
    rule_file = out / f"{prefix}_RULE_ASSESSMENT.csv"
    combined_file = out / f"{prefix}_COMBINED_ROUTING.csv"
    gap_file = out / f"{prefix}_CONTEXT_GAP_REGISTER.csv"
    account_df.to_csv(account_file, index=False)
    rule_df.to_csv(rule_file, index=False)
    combined_df.to_csv(combined_file, index=False)
    pd.DataFrame(global_context_gaps, columns=["context_id", "status", "affects_rules", "rationale", "required_repair"]).to_csv(gap_file, index=False)

    accept = contract["acceptance"]
    context_blocked = bool(global_context_gaps) or account_df["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").any()
    if failures:
        status = accept["integrity_fail_status"]
        next_gate = None
    elif context_blocked:
        status = accept["context_blocked_status"]
        next_gate = accept["context_repair_next_gate"]
    else:
        status = accept["pass_status"]
        next_gate = accept["next_gate_on_pass"]

    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_candidate_count": len(combined_df),
        "account_security_assessment_count": len(account_df),
        "rule_assessment_row_count": len(rule_df),
        "account_fit_state_counts": {a: account_df[account_df["account"].eq(a)]["fit_state"].value_counts().astype(int).to_dict() for a in ACCOUNTS},
        "combined_route_counts": combined_df["combined_route"].value_counts().astype(int).to_dict(),
        "context_gap_count": len(global_context_gaps),
        "context_gap_ids": [x["context_id"] for x in global_context_gaps],
        "p4_1r_status": p4r_decision.get("status"),
        "p4_1r_context_ready_account_security_count": p4r_decision.get("context_ready_account_security_count"),
        "p4_1r_residual_gap_count": p4r_decision.get("residual_decision_critical_gap_count"),
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "portfolio_allocations": 0,
        "orders_created": 0,
        "next_gate": next_gate,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if status == accept["pass_status"] else ("PASS_STRUCTURE_WITH_CONTEXT_BLOCK" if not failures else "FAIL"),
        "hard_failures": sorted(set(failures)),
        "p4_0_rule_set_preserved": len(rules) == 15,
        "p4_1r_runtime_context_bound": runtime_ok,
        "separate_real_and_simulation_assessment": len(account_df) == 140,
        "all_15_rules_materialized_per_account_security": len(rule_df) == 2100,
        "weighted_score": False,
        "fixed_top_n": False,
        "fuzzy_identity_matching": False,
        "sector_neutral_fill": False,
        "ticker_count_diversification_inference": False,
        "trailing_return_called_expected_return": False,
        "ah_discount_called_alpha": False,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    base.write_json(decision_file, decision)
    base.write_json(quality_file, quality)

    report = [
        "# HKCU P4-1 Portfolio Fit Reassessment",
        "",
        f"Status: **{status}**",
        "",
        f"- Candidates: {len(combined_df)}",
        f"- Account × Security assessments: {len(account_df)}",
        f"- Rule assessments: {len(rule_df)}",
        f"- Runtime context gaps: {len(global_context_gaps)}",
        f"- Next gate: {next_gate}",
        "",
        "## Account fit state counts",
        "",
        f"- REAL: {decision['account_fit_state_counts']['REAL']}",
        f"- SIMULATION: {decision['account_fit_state_counts']['SIMULATION']}",
        f"- Combined routes: {decision['combined_route_counts']}",
        "",
        "## Combined routing",
        "",
        "| Rank | Code | Security | Real | Simulation | Route |",
        "|---:|---|---|---|---|---|",
    ]
    for row in combined_df.itertuples(index=False):
        report.append(f"| {row.p2a_overall_rank} | {row.stock_code_5d} | {row.security_name} | {row.real_fit_state} | {row.simulation_fit_state} | {row.combined_route} |")
    report += [
        "",
        "## Boundary",
        "",
        "This reassessment is analytical only. It does not change Candidate membership, Real Account or Simulation positions, allocations, target weights, cash policy, orders or trade authority. trade_authority=NONE.",
        "",
    ]
    report_file = out / f"{prefix}_ASSESSMENT.md"
    report_file.write_text("\n".join(report), encoding="utf-8")

    manifest = {
        "program_id": PROGRAM_ID,
        "as_of_date": contract["as_of_date"],
        "contract_sha256": base.sha256_file(contract_path),
        "p4_0_contract_sha256": base.sha256_file(p4_path),
        "p4_1_contract_sha256": base.sha256_file(p4_1_path),
        "p4_1r_contract_sha256": base.sha256_file(p4_1r_path),
        "p4_1r_runtime_manifest_sha256": base.sha256_file(p4r_manifest_file),
        "candidate_current_sha256": base.sha256_file(candidate_path),
        "real_positions_sha256": base.sha256_file(real_path),
        "simulation_positions_sha256": base.sha256_file(sim_path),
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for path in (account_file, rule_file, combined_file, gap_file, decision_file, quality_file, report_file):
        manifest["files"][path.name] = {"sha256": base.sha256_file(path), "bytes": path.stat().st_size}
    base.write_json(out / f"{prefix}_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P4_1_REASSESSMENT_INTEGRITY_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--context-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.context_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
