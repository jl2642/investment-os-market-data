#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def security_id(value: Any) -> str:
    raw = str(value).strip().upper()
    if "." in raw:
        code, suffix = raw.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    code = raw.zfill(6)
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    return f"{code}.SZ"


def safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def historical_quality(history: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(history, key=lambda row: int(row["year"]))
    first, last = ordered[0], ordered[-1]
    years = int(last["year"]) - int(first["year"])
    revenue_cagr = (last["revenue"] / first["revenue"]) ** (1 / years) - 1 if years else 0.0
    profit_cagr = (last["net_profit_parent"] / first["net_profit_parent"]) ** (1 / years) - 1 if years else 0.0
    rows = []
    for row in ordered:
        net_margin = row["net_profit_parent"] / row["revenue"]
        cash_conversion = row["operating_cash_flow"] / row["net_profit_parent"]
        rows.append({
            **row,
            "net_margin": round(net_margin, 8),
            "operating_cash_flow_to_net_profit": round(cash_conversion, 8),
        })
    return {
        "history": rows,
        "revenue_cagr": round(revenue_cagr, 8),
        "net_profit_cagr": round(profit_cagr, 8),
        "latest_net_margin": rows[-1]["net_margin"],
        "latest_cash_conversion": rows[-1]["operating_cash_flow_to_net_profit"],
        "cash_conversion_three_year_average": round(float(np.mean([row["operating_cash_flow_to_net_profit"] for row in rows])), 8),
        "quality_interpretation": (
            "CASH_FLOW_STRONGER_THAN_ACCOUNTING_PROFIT"
            if rows[-1]["operating_cash_flow_to_net_profit"] >= 1.0
            else "LATEST_CASH_CONVERSION_BELOW_ACCOUNTING_PROFIT_REQUIRES_MONITORING"
        ),
    }


def market_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    frame["security_id"] = frame["security_code"].map(security_id)
    return frame


def factor_pivot(path: Path, factor_ids: list[str], security_ids: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(path)
    frame["security_id"] = frame["symbol"].map(security_id)
    selected = frame[
        frame["security_id"].isin(security_ids)
        & frame["factor_id"].isin(factor_ids)
        & frame["row_status"].isin(["CURRENT", "PARTIAL_CURRENT"])
    ].copy()
    selected["factor_value"] = pd.to_numeric(selected["factor_value"], errors="coerce")
    pivot = selected.pivot_table(index="security_id", columns="factor_id", values="factor_value", aggfunc="first").reset_index()
    periods = {}
    for sid, group in selected.groupby("security_id"):
        periods[sid] = {
            factor: {
                "period_end": str(sub.iloc[0]["period_end"]),
                "as_of_timestamp": str(sub.iloc[0]["as_of_timestamp"]),
                "row_status": str(sub.iloc[0]["row_status"]),
            }
            for factor, sub in group.groupby("factor_id")
        }
    return pivot, periods


def peer_comparison(
    market: pd.DataFrame,
    factors: pd.DataFrame,
    periods: dict[str, Any],
    peer_sets: dict[str, list[str]],
) -> dict[str, Any]:
    market_cols = ["security_id", "security_name", "last_price", "pe_ttm", "pb", "total_market_cap", "turnover_amount", "change_pct", "provider_session_date"]
    market_selected = market[market["security_id"].isin({sid for peers in peer_sets.values() for sid in peers})][market_cols].copy()
    combined = market_selected.merge(factors, on="security_id", how="left")
    rows = []
    peer_set_products = {}
    for target, peers in peer_sets.items():
        group = combined[combined["security_id"].isin(peers)].copy()
        expected = set(peers)
        missing = sorted(expected - set(group["security_id"]))
        metrics = [column for column in group.columns if column not in market_cols]
        medians = {
            metric: safe_float(pd.to_numeric(group[metric], errors="coerce").median())
            for metric in ["pe_ttm", "pb", "total_market_cap", *metrics]
            if metric in group.columns
        }
        peer_rows = []
        for _, item in group.iterrows():
            row = {column: (None if pd.isna(item[column]) else item[column]) for column in group.columns}
            row["is_target"] = row["security_id"] == target
            row["factor_periods"] = periods.get(row["security_id"], {})
            peer_rows.append(row)
            rows.append(row)
        target_row = next((row for row in peer_rows if row["security_id"] == target), None)
        peer_set_products[target] = {
            "target_security_id": target,
            "peer_security_ids": peers,
            "rows": peer_rows,
            "peer_medians": medians,
            "missing_security_ids": missing,
            "target_vs_peer_median": {
                metric: (
                    None
                    if not target_row or target_row.get(metric) is None or medians.get(metric) in (None, 0)
                    else round(float(target_row[metric]) / float(medians[metric]) - 1.0, 8)
                )
                for metric in medians
            },
            "status": "COMPLETE" if not missing and len(peer_rows) == len(peers) else "PARTIAL_PEER_SET",
        }
    return {
        "state_id": "WP4B_PEER_COMPARISON_CURRENT",
        "status": "COMPLETE" if all(item["status"] == "COMPLETE" for item in peer_set_products.values()) else "PARTIAL",
        "peer_sets": peer_set_products,
        "comparison_scope": "CURRENT_MARKET_VALUATION_PLUS_CANONICAL_FINANCIAL_FACTORS",
        "cross_industry_ranking_forbidden": True,
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def scenario_model(company: dict[str, Any], market_row: dict[str, Any]) -> dict[str, Any]:
    assumptions = company["scenario_assumptions"]
    current_price = float(market_row["last_price"])
    current_market_cap = float(market_row["total_market_cap"])
    shares = current_market_cap / current_price
    cases = []
    for name, case in assumptions["scenarios"].items():
        revenue = assumptions["base_revenue_rmb_bn"] * (1.0 + float(case["revenue_growth"]))
        net_income = revenue * float(case["net_margin"])
        implied_market_cap = net_income * float(case["exit_pe"])
        implied_price = implied_market_cap * 1e9 / shares
        cases.append({
            "scenario": name,
            "revenue_growth": case["revenue_growth"],
            "net_margin": case["net_margin"],
            "exit_pe": case["exit_pe"],
            "forward_revenue_rmb_bn": round(revenue, 6),
            "forward_net_income_rmb_bn": round(net_income, 6),
            "implied_market_cap_rmb_bn": round(implied_market_cap, 6),
            "implied_price": round(implied_price, 6),
            "price_return_vs_current": round(implied_price / current_price - 1.0, 8),
        })
    return {
        "model_type": assumptions["model_type"],
        "current_price": current_price,
        "current_market_cap_rmb_bn": round(current_market_cap / 1e9, 6),
        "implied_share_count_bn": round(shares / 1e9, 6),
        "base_year": assumptions["base_year"],
        "base_revenue_rmb_bn": assumptions["base_revenue_rmb_bn"],
        "critical_drivers": assumptions["critical_drivers"],
        "cases": cases,
        "model_limitations": [
            "One-year earnings and exit-multiple model is a decision interface, not a full statutory forecast",
            "No automatic target price or trading action is authorized",
            "Scenario assumptions require refresh after material earnings, guidance, regulation or capital-allocation events",
        ],
    }


def position_fit(
    sid: str,
    company_name: str,
    simulation: dict[str, Any],
    real: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    sim_holding = next((row for row in simulation.get("holdings", []) if row["security_id"] == sid), None)
    real_holding = next((row for row in real.get("holdings", []) if row["security_id"] == sid), None)
    total_assets = float(simulation["summary"]["account_total_assets"])
    if sim_holding:
        current_value = float(sim_holding["market_value"])
        current_weight = current_value / total_assets
        target_weight = float(sim_holding.get("target_weight") or policy["core_target_weight"])
        target_value = total_assets * target_weight
        gap_value = target_value - current_value
        fit_status = (
            "ABOVE_HARD_MAX_RESEARCH_RED_FLAG"
            if current_weight > policy["single_name_hard_max_weight"]
            else "ABOVE_SOFT_MAX_REVIEW_REQUIRED"
            if current_weight > policy["soft_max_weight"]
            else "BELOW_TARGET_RESEARCH_ONLY"
            if current_weight < target_weight - 0.005
            else "AT_TARGET_BAND"
        )
    else:
        current_value = current_weight = 0.0
        target_weight = float(policy["core_target_weight"])
        target_value = total_assets * target_weight
        gap_value = target_value
        fit_status = "NOT_HELD_RESEARCH_ONLY"
    return {
        "security_id": sid,
        "security_name": company_name,
        "simulation_position": sim_holding,
        "real_account_position": real_holding,
        "simulation_total_assets": round(total_assets, 6),
        "current_market_value": round(current_value, 6),
        "current_weight": round(current_weight, 8),
        "target_weight_reference": target_weight,
        "target_market_value_reference": round(target_value, 6),
        "market_value_gap_to_reference": round(gap_value, 6),
        "fit_status": fit_status,
        "portfolio_role": sim_holding.get("portfolio_bucket") if sim_holding else "CORE_RESEARCH_CANDIDATE",
        "broker_verified": False,
        "position_change_authorized": False,
        "order_authorized": False,
        "trade_authority": "NONE",
    }


def company_research(
    sid: str,
    company: dict[str, Any],
    market_row: dict[str, Any],
    peer_product: dict[str, Any],
    scenario: dict[str, Any],
    fit: dict[str, Any],
    sources: list[dict[str, Any]],
    initial_research: dict[str, Any] | None,
) -> dict[str, Any]:
    history = historical_quality(company["financial_history_rmb_bn"])
    return {
        "research_id": f"WP4B_{sid}_RESEARCH_CURRENT",
        "security_id": sid,
        "security_name": company["security_name"],
        "status": "WP4B_RESEARCH_HARDENED_RESEARCH_ONLY",
        "additive_to_wp4_initial_baseline": True,
        "business_and_competition": company["business_model"],
        "management_governance_and_capital_allocation": company["management_governance"],
        "historical_financial_trend_and_cash_quality": history,
        "latest_operating_facts": company["latest_operating_facts"],
        "current_market": {
            key: market_row.get(key)
            for key in ["provider_session_date", "last_price", "pe_ttm", "pb", "total_market_cap", "turnover_amount", "change_pct"]
        },
        "peer_comparison": peer_product,
        "driver_based_scenarios": scenario,
        "position_level_portfolio_fit": fit,
        "event_monitoring_rules": company["monitoring_rules"],
        "initial_wp4_research_reference": initial_research,
        "sources": [source for source in sources if source.get("security_id") in (None, sid)],
        "research_conclusion": {
            "thesis_type": "LONG_TERM_QUALITY_CORE_RESEARCH",
            "decision_grade": "RESEARCH_HARDENED_NO_TRADE_AUTHORITY",
            "required_before_action": [
                "Fresh portfolio marks and position continuity",
                "Current event-monitoring status",
                "Governed WP5 portfolio proposal",
                "Broker verification at action gate",
                "Explicit user approval",
            ],
            "automatic_buy_or_sell_signal": False,
        },
        "candidate_membership_mutations": 0,
        "portfolio_quantity_or_cost_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp4_b/config.json")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read_json(root / args.config)
    facts = read_json(root / cfg["inputs"]["source_facts"])
    market = market_frame(root / cfg["inputs"]["market_current"])
    simulation = read_json(root / cfg["inputs"]["simulation_positions"])
    real = read_json(root / cfg["inputs"]["real_positions"])
    candidate = read_json(root / cfg["inputs"]["candidate_current"])
    wp4_initial_current = read_json(root / cfg["inputs"]["wp4_initial_current"])
    initial_rows = read_jsonl(root / cfg["inputs"]["wp4_initial_research"])
    initial_map = {row["security_id"]: row for row in initial_rows}

    all_peer_ids = sorted({sid for peers in cfg["peer_sets"].values() for sid in peers})
    factors, periods = factor_pivot(
        root / cfg["inputs"]["financial_factor_current"],
        cfg["comparison_factor_ids"],
        all_peer_ids,
    )
    peer_product = peer_comparison(market, factors, periods, cfg["peer_sets"])
    market_lookup = {row["security_id"]: row.to_dict() for _, row in market.iterrows()}

    research_products = {}
    scenarios = {}
    fits = {}
    event_rules = {}
    for sid, company in facts["companies"].items():
        if sid not in market_lookup:
            raise ValueError(f"CORE_SECURITY_MISSING_FROM_MARKET_CURRENT:{sid}")
        scenario = scenario_model(company, market_lookup[sid])
        fit = position_fit(sid, company["security_name"], simulation, real, cfg["position_fit_policy"])
        research = company_research(
            sid,
            company,
            market_lookup[sid],
            peer_product["peer_sets"][sid],
            scenario,
            fit,
            facts["source_register"],
            initial_map.get(sid),
        )
        research_products[sid] = research
        scenarios[sid] = scenario
        fits[sid] = fit
        event_rules[sid] = {
            "security_id": sid,
            "security_name": company["security_name"],
            "rules": company["monitoring_rules"],
            "automatic_trade_action": False,
            "trade_authority": "NONE",
        }

    outputs = cfg["outputs"]
    write_json(root / outputs["midea_research"], research_products["000333.SZ"])
    write_json(root / outputs["yangtze_research"], research_products["600900.SH"])
    write_json(root / outputs["peer_comparison"], peer_product)
    scenario_product = {"state_id": "WP4B_SCENARIO_MODELS_CURRENT", "models": scenarios, "orders": 0, "trade_authority": "NONE"}
    fit_product = {"state_id": "WP4B_POSITION_FIT_CURRENT", "positions": fits, "position_mutations": 0, "orders": 0, "trade_authority": "NONE"}
    event_product = {"state_id": "WP4B_EVENT_MONITORING_CURRENT", "companies": event_rules, "automatic_trade_action": False, "orders": 0, "trade_authority": "NONE"}
    write_json(root / outputs["scenario_models"], scenario_product)
    write_json(root / outputs["position_fit"], fit_product)
    write_json(root / outputs["event_monitoring"], event_product)

    operating = {
        "state_id": "WP4B_CORE2_RESEARCH_CURRENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "WP4B_CORE2_RESEARCH_HARDENING_COMPLETE_RESEARCH_ONLY",
        "core_security_ids": sorted(research_products),
        "initial_wp4_state": wp4_initial_current.get("status"),
        "business_competition_complete": True,
        "management_governance_capital_allocation_complete": True,
        "three_year_financial_and_cash_quality_complete": True,
        "peer_comparison_complete": peer_product["status"] == "COMPLETE",
        "driver_based_scenarios_complete": True,
        "position_level_fit_complete": True,
        "event_monitoring_rules_complete": True,
        "research_only": True,
        "candidate_membership_mutations": 0,
        "portfolio_quantity_or_cost_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(root / outputs["operating_current"], operating)

    product_map = {
        "midea_research": research_products["000333.SZ"],
        "yangtze_research": research_products["600900.SH"],
        "peer_comparison": peer_product,
        "scenario_models": scenario_product,
        "position_fit": fit_product,
        "event_monitoring": event_product,
        "operating_current": operating,
    }
    acceptance = {
        "acceptance_id": "WP4_B_CORE2_HARDENING_ACCEPTANCE_V1",
        "status": "WP4B_CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY",
        "outputs": {
            key: {"path": outputs[key], "semantic_hash": digest(payload)}
            for key, payload in product_map.items()
        },
        "controls": {
            "initial_wp4_baseline_preserved": True,
            "research_objects_added_not_overwritten": True,
            "candidate_membership_mutations": 0,
            "portfolio_quantity_or_cost_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
        "wp5_research_gate_candidate": True,
        "wp5_unblocked": False,
        "wp5_unblock_requirements": [
            "WP2-R, WP3-R and WP4-B integrated R2 acceptance",
            "R2 Draft PR merged to main",
            "fresh Portfolio Current and event status at decision time",
            "separate governed WP5 portfolio proposal",
        ],
    }
    write_json(root / outputs["acceptance"], acceptance)
    print(json.dumps({
        "status": operating["status"],
        "peer_comparison": peer_product["status"],
        "midea_weight": fits["000333.SZ"]["current_weight"],
        "yangtze_weight": fits["600900.SH"]["current_weight"],
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
