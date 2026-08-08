#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-3"
TRADE_AUTHORITY = "NONE"
ACTIONABLE = {"PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW", "PROBE_BUILD_REVIEW"}


def finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


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
            return max(0.0, v)
    return 0.0


def rank_map(values: list[str]) -> dict[str, int]:
    return {str(v): i for i, v in enumerate(values)}


def prepare_actionable(review: pd.DataFrame, account: str, policy: dict[str, Any]) -> pd.DataFrame:
    df = review[(review["account"].eq(account)) & (review["construction_state"].isin(ACTIONABLE))].copy()
    state_rank = rank_map(policy["construction_state_priority"])
    risk_rank = rank_map(policy["marginal_risk_priority"])
    opp_rank = rank_map(policy["opportunity_cost_priority"])
    df["_state_rank"] = df["construction_state"].map(state_rank).fillna(999)
    df["_risk_rank"] = df["marginal_risk_state"].map(risk_rank).fillna(999)
    df["_opp_rank"] = df["opportunity_cost_state"].map(opp_rank).fillna(999)
    df["_max"] = pd.to_numeric(df["suggested_weight_max"], errors="coerce").fillna(0.0)
    return df.sort_values(
        ["_state_rank", "_risk_rank", "_opp_rank", "_max", "security_id"],
        ascending=[True, True, True, False, True],
    )


def scenario_limits(target: float, policy: dict[str, Any]) -> dict[str, float]:
    return {
        "sector_fraction_cap": target * float(policy["hk_sleeve_sector_fraction_limit"]),
        "style_fraction_cap": target * float(policy["hk_sleeve_style_fraction_limit"]),
        "stress_loss_cap": target * float(policy["gross_historical_drawdown_stress_fraction_of_hk_sleeve"]),
    }


def allocate_scenario(
    scenario: dict[str, Any],
    account: str,
    review: pd.DataFrame,
    substitutions: pd.DataFrame,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenario_id = str(scenario["scenario_id"])
    family = str(scenario["scenario_family"])
    target = float(scenario["hk_sleeve_target"])
    limits = scenario_limits(target, policy)
    min_position = float(policy["minimum_scenario_position_weight"])
    target_tolerance = float(policy["target_residual_tolerance"])
    direct_sector_limit = float(policy["direct_sector_weight_limit"])
    direct_style_limit = float(policy["direct_style_weight_limit"])

    sleeve_sector: dict[str, float] = {}
    sleeve_style: dict[str, float] = {}
    net_new_sector: dict[str, float] = {}
    net_new_style: dict[str, float] = {}
    allocation_rows: list[dict[str, Any]] = []
    stress_loss = 0.0
    substitution_weight = 0.0

    review_idx = review.set_index(["security_id", "account"], drop=False)

    if family == "MAX_AH_SUBSTITUTION_STRESS":
        sub = substitutions[substitutions["account"].eq(account)].copy()
        for s in sub.sort_values(["security_id"]).itertuples(index=False):
            key = (str(s.security_id), account)
            if key not in review_idx.index:
                continue
            r = review_idx.loc[key]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[0]
            sector = str(r["economic_sector_industry"])
            style = str(r["portfolio_style"])
            dd = max(abs(finite(r["max_drawdown_120d"]) or 0.0), 0.15)
            replacement_cap = max(0.0, finite(s.replacement_equivalent_weight_cap) or 0.0)
            existing_overlap = max(0.0, finite(s.existing_overlap_weight) or 0.0)
            stress_room = max(0.0, (limits["stress_loss_cap"] - stress_loss) / dd)
            allowed = min(
                replacement_cap,
                existing_overlap,
                max(0.0, target - substitution_weight),
                max(0.0, limits["sector_fraction_cap"] - sleeve_sector.get(sector, 0.0)),
                max(0.0, limits["style_fraction_cap"] - sleeve_style.get(style, 0.0)),
                stress_room,
            )
            if allowed <= 1e-12:
                continue
            allocation_rows.append({
                "scenario_id": scenario_id,
                "scenario_family": family,
                "account": account,
                "security_id": str(s.security_id),
                "stock_code_5d": str(s.stock_code_5d).zfill(5),
                "security_name": str(s.security_name),
                "allocation_type": "AH_SUBSTITUTION",
                "construction_state": "SUBSTITUTION_REVIEW_ONLY",
                "economic_sector_industry": sector,
                "portfolio_style": style,
                "scenario_weight": allowed,
                "p4_2_suggested_weight_max": 0.0,
                "p4_2_replacement_equivalent_cap": replacement_cap,
                "paired_reduction_security_ids": str(s.overlap_security_ids),
                "paired_reduction_weight": allowed,
                "net_new_capital_weight": 0.0,
                "gross_drawdown_stress_weight": allowed * dd,
                "funding_source_class": "EQUAL_WEIGHT_REDUCTION_OF_EXISTING_SAME_ISSUER_A_SHARE_IF_LATER_APPROVED",
                "portfolio_mutation": False,
                "orders_created": 0,
                "trade_authority": TRADE_AUTHORITY,
            })
            sleeve_sector[sector] = sleeve_sector.get(sector, 0.0) + allowed
            sleeve_style[style] = sleeve_style.get(style, 0.0) + allowed
            stress_loss += allowed * dd
            substitution_weight += allowed

    remaining = max(0.0, target - substitution_weight)
    actionable = prepare_actionable(review, account, policy)
    for r in actionable.itertuples(index=False):
        if remaining < min_position - 1e-12:
            break
        sector = str(r.economic_sector_industry)
        style = str(r.portfolio_style)
        baseline_sector = max(0.0, finite(r.existing_same_sector_weight) or 0.0)
        baseline_style = max(0.0, finite(r.construction_existing_direct_same_style_weight) or 0.0)
        dd = max(abs(finite(r.max_drawdown_120d) or 0.0), 0.15)
        row_max = max(0.0, finite(r.suggested_weight_max) or 0.0)
        absolute_sector_room = max(0.0, direct_sector_limit - baseline_sector - net_new_sector.get(sector, 0.0))
        absolute_style_room = max(0.0, direct_style_limit - baseline_style - net_new_style.get(style, 0.0))
        sleeve_sector_room = max(0.0, limits["sector_fraction_cap"] - sleeve_sector.get(sector, 0.0))
        sleeve_style_room = max(0.0, limits["style_fraction_cap"] - sleeve_style.get(style, 0.0))
        stress_room = max(0.0, (limits["stress_loss_cap"] - stress_loss) / dd)
        allowed = min(
            row_max,
            remaining,
            absolute_sector_room,
            absolute_style_room,
            sleeve_sector_room,
            sleeve_style_room,
            stress_room,
        )
        if allowed < min_position - 1e-12:
            continue
        allocation_rows.append({
            "scenario_id": scenario_id,
            "scenario_family": family,
            "account": account,
            "security_id": str(r.security_id),
            "stock_code_5d": str(r.stock_code_5d).zfill(5),
            "security_name": str(r.security_name),
            "allocation_type": "NEW_BUILD",
            "construction_state": str(r.construction_state),
            "economic_sector_industry": sector,
            "portfolio_style": style,
            "scenario_weight": allowed,
            "p4_2_suggested_weight_max": row_max,
            "p4_2_replacement_equivalent_cap": 0.0,
            "paired_reduction_security_ids": "",
            "paired_reduction_weight": 0.0,
            "net_new_capital_weight": allowed,
            "gross_drawdown_stress_weight": allowed * dd,
            "funding_source_class": (
                "EXTERNAL_LIQUIDITY_OR_SEPARATE_CAPITAL_DECISION_REQUIRED"
                if account == "REAL"
                else "SIMULATION_AVAILABLE_CASH"
            ),
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })
        sleeve_sector[sector] = sleeve_sector.get(sector, 0.0) + allowed
        sleeve_style[style] = sleeve_style.get(style, 0.0) + allowed
        net_new_sector[sector] = net_new_sector.get(sector, 0.0) + allowed
        net_new_style[style] = net_new_style.get(style, 0.0) + allowed
        stress_loss += allowed * dd
        remaining -= allowed

    total_weight = sum(float(x["scenario_weight"]) for x in allocation_rows)
    new_build_weight = sum(float(x["net_new_capital_weight"]) for x in allocation_rows)
    assets = account_assets(state)
    cash_weight = account_cash(state) / assets if assets > 0 else 0.0
    funding_gap = 0.0
    if account == "REAL":
        funding_gap = new_build_weight
        funding_status = "FEASIBLE_WITH_EXTERNAL_FUNDING_DEPENDENCY" if new_build_weight > 0 else "NO_NEW_FUNDING_REQUIRED"
    else:
        funding_gap = max(0.0, new_build_weight - cash_weight)
        funding_status = "FEASIBLE_WITH_SIMULATION_CASH" if funding_gap <= 1e-12 else "SIMULATION_FUNDING_GAP"

    max_sector_weight = max(sleeve_sector.values()) if sleeve_sector else 0.0
    max_style_weight = max(sleeve_style.values()) if sleeve_style else 0.0
    target_residual = max(0.0, target - total_weight)
    constraint_errors: list[str] = []
    if total_weight > target + 1e-10:
        constraint_errors.append("HK_SLEEVE_TARGET_EXCEEDED")
    if target_residual > target_tolerance + 1e-10:
        constraint_errors.append("HK_SLEEVE_TARGET_UNDERFILLED")
    if max_sector_weight > limits["sector_fraction_cap"] + 1e-10:
        constraint_errors.append("HK_SLEEVE_SECTOR_FRACTION")
    if max_style_weight > limits["style_fraction_cap"] + 1e-10:
        constraint_errors.append("HK_SLEEVE_STYLE_FRACTION")
    if stress_loss > limits["stress_loss_cap"] + 1e-10:
        constraint_errors.append("GROSS_DRAWDOWN_STRESS")
    if account == "SIMULATION" and funding_gap > 1e-12:
        constraint_errors.append("SIMULATION_FUNDING")

    scenario_status = "PASS" if not constraint_errors else "FAIL"
    summary = {
        "scenario_id": scenario_id,
        "scenario_family": family,
        "account": account,
        "scenario_status": scenario_status,
        "hk_sleeve_target": target,
        "hk_sleeve_allocated": total_weight,
        "target_residual": target_residual,
        "position_count": len(allocation_rows),
        "new_build_weight": new_build_weight,
        "ah_substitution_weight": substitution_weight,
        "gross_drawdown_stress_weight": stress_loss,
        "gross_drawdown_stress_cap": limits["stress_loss_cap"],
        "max_hk_sleeve_sector_weight": max_sector_weight,
        "hk_sleeve_sector_weight_cap": limits["sector_fraction_cap"],
        "max_hk_sleeve_style_weight": max_style_weight,
        "hk_sleeve_style_weight_cap": limits["style_fraction_cap"],
        "account_cash_weight": cash_weight,
        "funding_gap_weight": funding_gap,
        "funding_status": funding_status,
        "sector_mix": json.dumps(sleeve_sector, ensure_ascii=False, sort_keys=True),
        "style_mix": json.dumps(sleeve_style, ensure_ascii=False, sort_keys=True),
        "constraint_errors": "|".join(constraint_errors),
        "portfolio_mutation": False,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    return summary, allocation_rows


def build(root: Path, p4_2_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p4_3_portfolio_construction_scenario_test_contract.json")
    policy = contract["scenario_policy"]
    prefix = contract["output_prefix"]
    p4_2_contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    p4_2_prefix = p4_2_contract["output_prefix"]
    p4_2_decision = read_json(p4_2_dir / f"{p4_2_prefix}_DECISION.json")
    review = pd.read_csv(
        p4_2_dir / f"{p4_2_prefix}_ACCOUNT_SECURITY_REVIEW.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    substitutions = pd.read_csv(
        p4_2_dir / f"{p4_2_prefix}_SUBSTITUTION_REGISTER.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    inputs = contract["authoritative_inputs"]
    states = {
        "REAL": read_json(root / inputs["real_positions_current"]),
        "SIMULATION": read_json(root / inputs["simulation_positions_current"]),
    }

    integrity: list[str] = []
    if p4_2_decision.get("status") != contract["entry_contract"]["required_p4_2_status"]:
        integrity.append("P4_2_STATUS")
    if len(review) != contract["entry_contract"]["account_security_review_count"]:
        integrity.append("P4_2_REVIEW_COUNT")
    if review.duplicated(["security_id", "account"]).any():
        integrity.append("P4_2_REVIEW_DUPLICATE")
    if any(states[a].get("trade_authority") != TRADE_AUTHORITY for a in ("REAL", "SIMULATION")):
        integrity.append("ACCOUNT_TRADE_AUTHORITY")
    if (pd.to_numeric(review["orders_created"], errors="coerce").fillna(0) != 0).any():
        integrity.append("P4_2_ORDERS")

    summaries: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    for account, defs in policy["scenario_definitions"].items():
        for scenario in defs:
            summary, rows = allocate_scenario(scenario, account, review, substitutions, states[account], policy)
            summaries.append(summary)
            allocations.extend(rows)

    summary_df = pd.DataFrame(summaries)
    allocation_df = pd.DataFrame(allocations)
    scenario_failures = summary_df[summary_df["scenario_status"].ne("PASS")]["scenario_id"].astype(str).tolist()
    if scenario_failures:
        integrity.append("SCENARIO_FAILURE:" + ",".join(scenario_failures))

    ah_options = substitutions.copy()
    if len(ah_options):
        ah_options["scenario_test_semantics"] = "OPTIONAL_EQUAL_WEIGHT_A_TO_H_REPLACEMENT_NOT_A_PROPOSAL"
        ah_options["net_new_capital_weight"] = 0.0
        ah_options["portfolio_mutation"] = False
        ah_options["orders_created"] = 0
        ah_options["trade_authority"] = TRADE_AUTHORITY

    status = contract["acceptance"]["pass_status"] if not integrity else contract["acceptance"]["fail_status"]
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_p4_2_status": p4_2_decision.get("status"),
        "scenario_count": len(summary_df),
        "real_scenario_count": int(summary_df["account"].eq("REAL").sum()),
        "simulation_scenario_count": int(summary_df["account"].eq("SIMULATION").sum()),
        "ah_stress_scenario_count": int(summary_df["scenario_family"].eq("MAX_AH_SUBSTITUTION_STRESS").sum()),
        "scenario_status_counts": summary_df["scenario_status"].value_counts().astype(int).to_dict(),
        "scenario_ids": summary_df["scenario_id"].astype(str).tolist(),
        "integrity_failures": integrity,
        "portfolio_proposal_produced": False,
        "target_portfolio_writeback": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "next_gate": contract["acceptance"]["next_gate_on_pass"] if not integrity else contract["acceptance"]["repair_gate"],
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not integrity else "FAIL",
        "weighted_score": False,
        "fixed_top_n": False,
        "candidate_rank_used_as_allocation_authority": False,
        "p4_2_envelopes_respected": True,
        "aggregate_hk_sleeve_limit_enforced": True,
        "aggregate_sector_style_limits_enforced": True,
        "gross_drawdown_stress_budget_enforced": True,
        "real_cash_treated_as_strategic_target": False,
        "real_existing_positions_auto_reduced": False,
        "simulation_cash_is_funding_context": True,
        "ah_substitution_net_capital_neutral": True,
        "ah_substitution_same_issuer_reduction_required": True,
        "portfolio_proposal_produced": False,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "hard_failures": integrity,
    }

    summary_file = out / f"{prefix}_SCENARIO_SUMMARY.csv"
    allocation_file = out / f"{prefix}_SCENARIO_ALLOCATIONS.csv"
    ah_file = out / f"{prefix}_AH_SUBSTITUTION_OPTIONS.csv"
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    report_file = out / f"{prefix}_ASSESSMENT.md"
    manifest_file = out / f"{prefix}_MANIFEST.json"

    summary_df.to_csv(summary_file, index=False)
    allocation_df.to_csv(allocation_file, index=False)
    ah_options.to_csv(ah_file, index=False)
    write_json(decision_file, decision)
    write_json(quality_file, quality)

    report_lines = [
        "# HKCU P4-3 Portfolio Construction Scenario Test",
        "",
        f"Status: **{status}**",
        "",
        f"- Scenarios: {len(summary_df)}",
        f"- REAL scenarios: {int(summary_df['account'].eq('REAL').sum())}",
        f"- SIMULATION scenarios: {int(summary_df['account'].eq('SIMULATION').sum())}",
        f"- A/H substitution stress scenarios: {int(summary_df['scenario_family'].eq('MAX_AH_SUBSTITUTION_STRESS').sum())}",
        f"- Scenario PASS count: {int(summary_df['scenario_status'].eq('PASS').sum())}",
        f"- Next gate: {decision['next_gate']}",
        "",
        "P4-3 produces hypothetical aggregate scenario allocations only. It does not select a preferred portfolio, write target positions, reduce existing holdings, create a Pre-trade Memo or create orders.",
        "",
        "REAL scenario funding gaps are explicit external-liquidity / separate-capital-decision dependencies because broker cash is an execution balance, not a strategic cash bucket. SIMULATION scenarios may use the current simulation cash ledger. A/H stress variants require equal-weight reduction of the existing same-issuer A-share and authorize zero net-new capital for the substitution leg.",
        "",
        "trade_authority=NONE.",
        "",
    ]
    report_file.write_text("\n".join(report_lines), encoding="utf-8")

    manifest = {
        "program_id": PROGRAM_ID,
        "status": status,
        "files": {},
        "trade_authority": TRADE_AUTHORITY,
    }
    for path in (summary_file, allocation_file, ah_file, decision_file, quality_file, report_file):
        manifest["files"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(manifest_file, manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p4-2-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.p4_2_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
