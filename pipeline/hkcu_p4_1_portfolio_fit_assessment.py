#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-1"
TRADE_AUTHORITY = "NONE"
ACCOUNTS = ("REAL", "SIMULATION")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if pd.notna(x) else None


def code5(value: Any) -> str:
    s = str(value or "").strip().upper().replace(".HK", "")
    return s.zfill(5) if s.isdigit() and len(s) <= 5 else s


def role_from_sleeve(sleeve: str) -> str:
    return {
        "DEFENSIVE_STABILITY": "DEFENSIVE_INCOME_OR_STABILITY",
        "TREND_LIQUIDITY": "LIQUID_TREND_EXPOSURE",
        "QUALITY_VALUE": "QUALITY_VALUE_COMPOUNDER",
        "RECOVERY_WATCH": "RECOVERY_OR_CATALYST",
        "GROWTH_QUALITY": "QUALITY_GROWTH",
    }.get(sleeve, f"SLEEVE_{sleeve or 'UNSPECIFIED'}")


def account_current_ok(state: dict[str, Any], p4: dict[str, Any]) -> bool:
    ctx = p4["portfolio_context"]
    mark = state.get("mark_watermark", {})
    return (
        state.get("status") == ctx["required_position_status"]
        and state.get("permissions", {}).get("portfolio_fit") is True
        and state.get("trade_authority") == TRADE_AUTHORITY
        and state.get("position_watermark", {}).get("position_state_current") is True
        and mark.get("all_positions_marked") is True
        and mark.get("all_marks_fresh_or_acceptable") is True
        and str(mark.get("latest_mark_date", "")) >= str(p4["as_of_date"])
    )


def direct_overlap(code: str, holdings: list[dict[str, Any]]) -> list[str]:
    hits = []
    for h in holdings:
        hc = code5(h.get("code") or h.get("stock_code") or h.get("ticker"))
        if hc == code:
            hits.append(str(h.get("security_id") or hc))
    return hits


def relevant_a_share_holdings(holdings: list[dict[str, Any]]) -> list[str]:
    out = []
    for h in holdings:
        sid = str(h.get("security_id") or "")
        ac = str(h.get("asset_class") or "").upper()
        if sid.endswith((".SH", ".SZ")) and "ETF" not in ac and "FUND" not in ac:
            out.append(sid)
    return out


def has_lookthrough_gap(holdings: list[dict[str, Any]]) -> bool:
    for h in holdings:
        ac = str(h.get("asset_class") or "").upper()
        if "ETF" in ac or "FUND" in ac:
            return True
    return False


def add_rule(rows: list[dict[str, Any]], base: dict[str, Any], rule: dict[str, Any], state: str, rationale: str) -> None:
    rows.append({**base, "rule_id": rule["rule_id"], "rule_name": rule["name"], "rule_type": rule["type"], "rule_state": state, "rationale": rationale, "trade_authority": TRADE_AUTHORITY})


def build(root: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract_path = root / "config/hkcu_p4_1_portfolio_fit_assessment_contract.json"
    contract = read_json(contract_path)
    auth = contract["authoritative_inputs"]
    p4_path = root / auth["p4_0_contract"]
    p4 = read_json(p4_path)
    candidate_path = root / auth["candidate_current"]
    hkcu_path = root / auth["hkcu_current"]
    bridge_path = root / auth["fmdl5b2_security_issuer_bridge"]
    rel_path = root / auth["fmdl5b2_cross_market_relationships"]
    fmdl_contract_path = root / auth["fmdl5b2_contract"]
    real_path = root / auth["real_positions_current"]
    sim_path = root / auth["simulation_positions_current"]

    candidates = pd.read_csv(candidate_path, dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    hkcu = pd.read_csv(hkcu_path, dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    bridge = pd.read_csv(bridge_path, dtype={"stock_code_5d": str}, keep_default_na=False, encoding="utf-8-sig")
    rel = pd.read_csv(rel_path, dtype={"primary_market_code": str, "related_security_code": str}, keep_default_na=False, encoding="utf-8-sig")
    fmdl_contract = read_json(fmdl_contract_path)
    account_states = {"REAL": read_json(real_path), "SIMULATION": read_json(sim_path)}

    failures: list[str] = []
    entry = contract["entry_contract"]
    if p4.get("program_id") != entry["required_p4_0_program_id"]: failures.append("P4_0_PROGRAM_ID")
    if p4.get("acceptance", {}).get("pass_status") != entry["required_p4_0_pass_status"]: failures.append("P4_0_PASS_STATUS")
    if p4.get("acceptance", {}).get("next_gate") != entry["required_p4_0_next_gate"]: failures.append("P4_0_NEXT_GATE")
    if p4.get("as_of_date") != contract["as_of_date"]: failures.append("AS_OF_DATE_LINEAGE")
    if len(candidates) != entry["entry_candidate_count"]: failures.append(f"CANDIDATE_COUNT:{len(candidates)}")
    if candidates["security_id"].duplicated().any(): failures.append("DUPLICATE_CANDIDATE")
    if fmdl_contract.get("program_id") != "FMDL-5B-2": failures.append("FMDL5B2_PROGRAM_ID")
    if fmdl_contract.get("state_firewall", {}).get("trade_authority") != TRADE_AUTHORITY: failures.append("FMDL5B2_AUTHORITY")

    rules = {r["rule_id"]: r for r in p4["portfolio_fit_rules"]}
    if set(rules) != {f"P4R{i:02d}" for i in range(1, 16)}: failures.append("P4_RULE_SET")

    hkcu_idx = hkcu.set_index("security_id", drop=False)
    bridge_idx = bridge.set_index("security_id", drop=False)
    confirmed_rels = rel[rel["evidence_status"].astype(str).eq("CONFIRMED")].copy()

    # Repository audit: P4-0 requires sector/industry impact and explicit marginal risk evidence.
    # The accepted P4-1 input set contains neither a sector/industry classification surface nor
    # a portfolio covariance/downside-risk surface. P2A sleeve labels are explicitly prohibited
    # from masquerading as sector classification. These gaps are therefore materialized, not filled.
    global_context_gaps = [
        {
            "context_id": "CTX_SECTOR_INDUSTRY",
            "status": "MISSING_DECISION_CRITICAL_CONTEXT",
            "affects_rules": "P4R10",
            "rationale": "No Canonical HK sector/industry classification surface is present in the accepted P4-1 inputs; HKCU category/sub_category are listing/security taxonomy, not industry classification.",
            "required_repair": "Add evidence-controlled Candidate and portfolio sector/industry classification with source lineage before positive P4R10 judgments."
        },
        {
            "context_id": "CTX_MARGINAL_RISK",
            "status": "MISSING_DECISION_CRITICAL_CONTEXT",
            "affects_rules": "P4R12",
            "rationale": "No accepted portfolio covariance, downside co-movement or equivalent marginal-risk surface is present in the P4-1 inputs.",
            "required_repair": "Materialize current return-history based marginal diversification/downside co-movement evidence for both accounts."
        },
        {
            "context_id": "CTX_PORTFOLIO_FACTOR_LOOKTHROUGH",
            "status": "MISSING_DECISION_CRITICAL_CONTEXT",
            "affects_rules": "P4R11",
            "rationale": "Candidate primary_sleeve is available, but current portfolio holdings are not mapped to the same accepted factor/style/theme taxonomy, so marginal concentration direction cannot be asserted.",
            "required_repair": "Map current portfolio exposures to the accepted factor/style/theme taxonomy or provide an evidence-equivalent exposure surface."
        },
        {
            "context_id": "CTX_EXPECTED_RETURN_OPPORTUNITY_COST",
            "status": "MISSING_DECISION_CRITICAL_CONTEXT",
            "affects_rules": "P4R13",
            "rationale": "Valuation support exists, but no accepted expected-return/risk comparison surface ties Candidates to relevant existing exposures and alternatives; A/H discount is context only.",
            "required_repair": "Add bounded expected-return/opportunity-cost comparison evidence without weighted alpha scoring."
        }
    ]

    rule_rows: list[dict[str, Any]] = []
    account_rows: list[dict[str, Any]] = []

    for c in candidates.sort_values("p2a_overall_rank").itertuples(index=False):
        sid = str(c.security_id)
        code = code5(c.stock_code_5d)
        name = str(c.security_name)
        tier = str(c.candidate_tier)
        sleeve = str(c.primary_sleeve)
        h = hkcu_idx.loc[sid] if sid in hkcu_idx.index else None
        b = bridge_idx.loc[sid] if sid in bridge_idx.index else None
        if isinstance(h, pd.DataFrame): h = h.iloc[0]
        if isinstance(b, pd.DataFrame): b = b.iloc[0]

        lineage_ok = str(c.candidate_status) == "ACTIVE" and as_bool(c.formal_candidate_graduation) and str(c.trade_authority) == TRADE_AUTHORITY
        investability_ok = h is not None and as_bool(h.get("publication_eligible")) and as_bool(h.get("buy_eligible")) and not as_bool(h.get("sell_only")) and str(h.get("freshness_status")) == "CURRENT"
        valuation_ok = str(c.valuation_support_state) not in {"", "MISSING", "ADVERSE_OR_UNUSABLE"}
        market_fresh = h is not None and str(h.get("market_latest_date", "")) >= "2026-08-06" and str(h.get("fmdl5e_as_of_date", "")) >= "2026-08-06"
        thesis_ok = bool(str(c.investment_thesis).strip() and str(c.principal_falsifier).strip() and str(c.monitor_triggers).strip())
        liquidity = f(h.get("avg_turnover_hkd_20d")) if h is not None else None
        liquidity_ok = liquidity is not None and liquidity > 0 and investability_ok
        issuer_ok = b is not None and str(b.get("mapping_status")) == "CONFIRMED" and bool(str(b.get("issuer_id", "")).strip())
        candidate_issuer = str(b.get("issuer_id")) if issuer_ok else ""
        candidate_rels = confirmed_rels[confirmed_rels["issuer_id"].astype(str).eq(candidate_issuer)] if candidate_issuer else confirmed_rels.iloc[0:0]

        for account in ACCOUNTS:
            state = account_states[account]
            holdings = state.get("holdings", [])
            account_ok = account_current_ok(state, p4)
            direct = direct_overlap(code, holdings)
            a_holdings = relevant_a_share_holdings(holdings)
            etf_gap = has_lookthrough_gap(holdings)
            ah_candidate = str(c.ah_pair_status).startswith("TRUE_AH_PAIR")
            ah_mapping_gap = ah_candidate and bool(a_holdings) and not candidate_rels["relationship_type"].astype(str).str.contains("A_SHARE", case=False, na=False).any()
            identity_ok = issuer_ok and not ah_mapping_gap
            identity_constraint = etf_gap
            role = role_from_sleeve(sleeve)
            constraints: list[str] = []
            context_defers: list[str] = []
            hard_blocks: list[str] = []
            base = {
                "p2a_overall_rank": int(c.p2a_overall_rank), "security_id": sid, "stock_code_5d": code,
                "security_name": name, "candidate_tier": tier, "account": account,
            }

            hard = {
                "P4R01": ("PASS" if lineage_ok else "BLOCK", f"candidate_status={c.candidate_status}; formal_candidate_graduation={c.formal_candidate_graduation}; trade_authority={c.trade_authority}."),
                "P4R02": ("PASS" if investability_ok else "BLOCK", f"publication_eligible={h.get('publication_eligible') if h is not None else None}; buy_eligible={h.get('buy_eligible') if h is not None else None}; sell_only={h.get('sell_only') if h is not None else None}; freshness={h.get('freshness_status') if h is not None else None}."),
                "P4R03": ("PASS" if market_fresh and valuation_ok else "DEFER", f"market_latest_date={h.get('market_latest_date') if h is not None else None}; fmdl5e_as_of_date={h.get('fmdl5e_as_of_date') if h is not None else None}; valuation_support_state={c.valuation_support_state}."),
                "P4R04": ("PASS" if account_ok else "DEFER", f"account_state_current={account_ok}; latest_mark_date={state.get('mark_watermark', {}).get('latest_mark_date')}."),
                "P4R05": ("PASS" if thesis_ok else "DEFER", f"thesis_present={bool(str(c.investment_thesis).strip())}; falsifier_present={bool(str(c.principal_falsifier).strip())}; monitor_present={bool(str(c.monitor_triggers).strip())}."),
                "P4R06": ("PASS" if liquidity_ok else "BLOCK", f"avg_turnover_hkd_20d={liquidity}; accepted investability remains={investability_ok}."),
                "P4R07": ("PASS_WITH_CONSTRAINTS" if identity_ok and identity_constraint else ("PASS" if identity_ok else "DEFER"), f"candidate_issuer_id={candidate_issuer or 'UNRESOLVED'}; issuer_mapping_confirmed={issuer_ok}; true_ah_pair={ah_candidate}; account_a_share_holdings={len(a_holdings)}; confirmed_a_share_relationship_available={not ah_mapping_gap}; pooled_fund_or_etf_lookthrough_gap={etf_gap}.")
            }
            for rid, (rstate, rationale) in hard.items():
                add_rule(rule_rows, base, rules[rid], rstate, rationale)
                if rstate == "BLOCK": hard_blocks.append(rid)
                elif rstate == "DEFER": context_defers.append(rid)
                elif rstate == "PASS_WITH_CONSTRAINTS": constraints.append("IDENTITY_LOOKTHROUGH_BOUNDED")

            add_rule(rule_rows, base, rules["P4R08"], "PASS", f"portfolio_role={role}; source=accepted P2A primary_sleeve={sleeve}; role is descriptive, not approval.")

            if ah_mapping_gap:
                r9_state = "DEFER"
                r9_note = f"direct_overlap={direct}; TRUE_AH_PAIR candidate but accepted FMDL5B2 relationship surface does not resolve the A-share code against {len(a_holdings)} account A-share holdings."
                context_defers.append("P4R09")
            elif direct:
                r9_state = "PASS_WITH_CONSTRAINTS"
                r9_note = f"direct existing holding overlap={direct}; incremental exposure would duplicate current security exposure and requires substitution/increment review, not automatic rejection."
                constraints.append("DIRECT_EXISTING_HOLDING_OVERLAP")
            elif etf_gap:
                r9_state = "DEFER"
                r9_note = "No direct security overlap, but pooled-fund/ETF holdings lack accepted look-through needed to exclude economically duplicate exposure."
                context_defers.append("P4R09")
            else:
                r9_state = "PASS"
                r9_note = "No direct or confirmed same-issuer overlap identified in accepted identity surfaces."
            add_rule(rule_rows, base, rules["P4R09"], r9_state, r9_note)

            add_rule(rule_rows, base, rules["P4R10"], "DEFER", "Canonical sector/industry classification and account exposure surface are absent; HKCU listing taxonomy and P2A sleeves cannot be neutral-filled as industry.")
            context_defers.append("P4R10")
            add_rule(rule_rows, base, rules["P4R11"], "DEFER", f"Candidate style context primary_sleeve={sleeve}, but account holdings are not mapped to the same accepted factor/style/theme taxonomy.")
            context_defers.append("P4R11")
            add_rule(rule_rows, base, rules["P4R12"], "DEFER", "No accepted account-level covariance/downside-co-movement or equivalent marginal-risk surface is available; diversification cannot be asserted from ticker count.")
            context_defers.append("P4R12")
            add_rule(rule_rows, base, rules["P4R13"], "DEFER", f"valuation_support_state={c.valuation_support_state}; accepted valuation context is available but expected-return/risk opportunity-cost comparison to relevant holdings/alternatives is not materialized.")
            context_defers.append("P4R13")

            if context_defers or hard_blocks:
                size_state = "PASS_WITH_CONSTRAINTS"
                size_note = "analytical_sizing_envelope=NO_SIZE_PENDING_PORTFOLIO_CONTEXT; no target weight or admission authority is created."
                constraints.append("NO_SIZE_PENDING_PORTFOLIO_CONTEXT")
            else:
                size_state = "PASS_WITH_CONSTRAINTS"
                size_note = "analytical_sizing_envelope=CONSTRUCTION_REVIEW_ONLY; numeric target sizing remains outside P4-1 authority."
                constraints.append("CONSTRUCTION_REVIEW_ONLY")
            add_rule(rule_rows, base, rules["P4R14"], size_state, size_note)

            if account == "REAL":
                cash = f(state.get("summary", {}).get("cash")) or f(state.get("summary", {}).get("available_cash")) or 0.0
                funding_note = f"real_cash_policy={state.get('cash_policy')}; broker execution cash={cash}; external liquidity is excluded and not assumed. Funding, if later needed, requires a separate capital decision."
                funding_state = "PASS_WITH_CONSTRAINTS" if cash <= 0 else "PASS"
                if cash <= 0: constraints.append("FUNDING_REQUIRED_FROM_SEPARATE_CAPITAL_DECISION")
            else:
                cash = f(state.get("summary", {}).get("cash")) or f(state.get("summary", {}).get("available_cash")) or 0.0
                funding_note = f"simulation available cash context={cash}; cash is funding context only, not alpha or admission authority."
                funding_state = "PASS"
            add_rule(rule_rows, base, rules["P4R15"], funding_state, funding_note)

            if hard_blocks:
                fit_state = "BLOCK_PORTFOLIO_FIT"
                reason = "Substantive hard-rule failure(s): " + ",".join(sorted(set(hard_blocks)))
            elif context_defers:
                fit_state = "DEFER_PORTFOLIO_CONTEXT"
                reason = "Decision-critical portfolio context missing: " + ",".join(sorted(set(context_defers)))
            elif direct and not constraints:
                fit_state = "NO_INCREMENTAL_ROLE"
                reason = "Existing direct exposure leaves no demonstrated incremental role."
            elif constraints:
                fit_state = "FIT_WITH_CONSTRAINTS"
                reason = "All hard rules pass; named constraints remain: " + ",".join(sorted(set(constraints)))
            else:
                fit_state = "FIT"
                reason = "All applicable hard and decision rules pass with no named constraint."

            account_rows.append({**base, "portfolio_role": role, "direct_overlap_count": len(direct),
                                 "direct_overlap_security_ids": "|".join(direct), "candidate_issuer_id": candidate_issuer,
                                 "context_defer_rules": "|".join(sorted(set(context_defers))),
                                 "constraints": "|".join(sorted(set(constraints))), "fit_state": fit_state,
                                 "fit_reason": reason, "analytical_sizing_envelope": "NO_SIZE_PENDING_PORTFOLIO_CONTEXT" if context_defers or hard_blocks else "CONSTRUCTION_REVIEW_ONLY",
                                 "portfolio_mutation": False, "orders_created": 0, "trade_authority": TRADE_AUTHORITY})

    account_df = pd.DataFrame(account_rows).sort_values(["p2a_overall_rank", "account"]).reset_index(drop=True)
    rule_df = pd.DataFrame(rule_rows).sort_values(["p2a_overall_rank", "account", "rule_id"]).reset_index(drop=True)

    combined_rows = []
    positive = {"FIT", "FIT_WITH_CONSTRAINTS"}
    for sid, g in account_df.groupby("security_id", sort=False):
        states = dict(zip(g["account"], g["fit_state"]))
        real_s, sim_s = states["REAL"], states["SIMULATION"]
        if real_s == "BLOCK_PORTFOLIO_FIT" and sim_s == "BLOCK_PORTFOLIO_FIT": route = "BLOCK_PORTFOLIO_FIT"
        elif "DEFER_PORTFOLIO_CONTEXT" in {real_s, sim_s}: route = "DEFER_PORTFOLIO_CONTEXT"
        elif real_s in positive and sim_s in positive: route = "ADVANCE_DUAL_CONSTRUCTION_REVIEW"
        elif real_s in positive: route = "ADVANCE_REAL_ACCOUNT_REVIEW"
        elif sim_s in positive: route = "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW"
        else: route = "HOLD_PORTFOLIO_WATCH"
        r = g.iloc[0]
        combined_rows.append({"p2a_overall_rank": int(r["p2a_overall_rank"]), "security_id": sid, "stock_code_5d": r["stock_code_5d"],
                              "security_name": r["security_name"], "candidate_tier": r["candidate_tier"], "real_fit_state": real_s,
                              "simulation_fit_state": sim_s, "combined_route": route, "portfolio_mutation": False,
                              "orders_created": 0, "trade_authority": TRADE_AUTHORITY})
    combined_df = pd.DataFrame(combined_rows).sort_values("p2a_overall_rank").reset_index(drop=True)

    if len(account_df) != entry["account_security_assessment_count"]: failures.append(f"ACCOUNT_ASSESSMENT_COUNT:{len(account_df)}")
    if len(rule_df) != entry["rule_assessment_row_count"]: failures.append(f"RULE_ROW_COUNT:{len(rule_df)}")
    if len(combined_df) != entry["entry_candidate_count"]: failures.append(f"COMBINED_COUNT:{len(combined_df)}")
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
    pd.DataFrame(global_context_gaps).to_csv(gap_file, index=False)

    context_blocked = bool(global_context_gaps) or account_df["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").any()
    accept = contract["acceptance"]
    status = accept["context_blocked_status"] if context_blocked and not failures else (accept["pass_status"] if not failures else "FAIL_P4_1_ASSESSMENT_INTEGRITY")
    next_gate = accept["context_repair_next_gate"] if context_blocked and not failures else (accept["normal_next_gate"] if not failures else None)
    decision = {
        "program_id": PROGRAM_ID, "phase": contract["phase"], "as_of_date": contract["as_of_date"], "status": status,
        "entry_candidate_count": len(combined_df), "account_security_assessment_count": len(account_df), "rule_assessment_row_count": len(rule_df),
        "account_fit_state_counts": {a: account_df[account_df["account"].eq(a)]["fit_state"].value_counts().astype(int).to_dict() for a in ACCOUNTS},
        "combined_route_counts": combined_df["combined_route"].value_counts().astype(int).to_dict(),
        "context_gap_count": len(global_context_gaps), "context_gap_ids": [x["context_id"] for x in global_context_gaps],
        "candidate_pool_mutations": 0, "simulation_mutations": 0, "real_account_mutations": 0, "portfolio_allocations": 0,
        "orders_created": 0, "next_gate": next_gate, "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID, "status": "PASS_STRUCTURE_WITH_CONTEXT_BLOCK" if context_blocked and not failures else ("PASS" if not failures else "FAIL"),
        "hard_failures": sorted(set(failures)), "p4_0_contract_bound": True, "candidate_count_exact": len(candidates) == 70,
        "separate_real_and_simulation_assessment": len(account_df) == 140, "all_15_rules_materialized_per_account_security": len(rule_df) == 2100,
        "fmdl5b2_identity_bound": True, "sector_industry_neutral_fill": False, "portfolio_factor_neutral_fill": False,
        "diversification_without_evidence": False, "weighted_score": False, "fixed_top_n": False,
        "portfolio_mutations": 0, "orders_created": 0, "trade_authority": TRADE_AUTHORITY,
    }
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    write_json(decision_file, decision)
    write_json(quality_file, quality)

    report = ["# HKCU P4-1 Portfolio Fit Assessment", "", f"Status: **{status}**", "",
              f"- Candidates: {len(combined_df)}", f"- Account × Security assessments: {len(account_df)}", f"- Rule assessments: {len(rule_df)}",
              f"- Context gaps: {len(global_context_gaps)}", f"- Next gate: {next_gate}", "",
              "## Result", "", "The assessment engine executed the frozen P4-0 contract. Decision-critical portfolio context is not neutral-filled; affected securities route to DEFER_PORTFOLIO_CONTEXT rather than receiving fabricated diversification or concentration claims.", "",
              "## Context gaps", ""]
    for x in global_context_gaps:
        report.append(f"- **{x['context_id']}** ({x['affects_rules']}): {x['rationale']} Repair: {x['required_repair']}")
    report += ["", "## Combined routing", "", "| Rank | Code | Security | Real | Simulation | Route |", "|---:|---|---|---|---|---|"]
    for r in combined_df.itertuples(index=False):
        report.append(f"| {r.p2a_overall_rank} | {r.stock_code_5d} | {r.security_name} | {r.real_fit_state} | {r.simulation_fit_state} | {r.combined_route} |")
    report += ["", "## Boundary", "", "P4-1 is assessment-only. No Candidate membership, Simulation position, Real Account position, portfolio allocation or order is changed. trade_authority=NONE.", ""]
    report_file = out / f"{prefix}_ASSESSMENT.md"
    report_file.write_text("\n".join(report), encoding="utf-8")

    manifest = {"program_id": PROGRAM_ID, "as_of_date": contract["as_of_date"], "contract_sha256": sha256_file(contract_path),
                "p4_0_contract_sha256": sha256_file(p4_path), "candidate_current_sha256": sha256_file(candidate_path),
                "fmdl5b2_contract_sha256": sha256_file(fmdl_contract_path), "real_positions_sha256": sha256_file(real_path),
                "simulation_positions_sha256": sha256_file(sim_path), "files": {}, "trade_authority": TRADE_AUTHORITY}
    for p in (account_file, rule_file, combined_file, gap_file, decision_file, quality_file, report_file):
        manifest["files"][p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    write_json(out / f"{prefix}_MANIFEST.json", manifest)

    if failures:
        raise SystemExit("P4_1_BUILD_INTEGRITY_FAILED:" + "|".join(sorted(set(failures))))
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
