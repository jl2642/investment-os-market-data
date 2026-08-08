#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import hkcu_p4_2_portfolio_construction_review as raw

PROGRAM_ID = "HKCU-P4-2"
TRADE_AUTHORITY = "NONE"
ACTIONABLE_NEW_SIZE = {"PRIMARY_BUILD_REVIEW", "SECONDARY_BUILD_REVIEW", "PROBE_BUILD_REVIEW"}
_BASE_INDEPENDENT_CAPS = raw.independent_caps


def non_direct_style_weight(state: dict[str, Any], style: str) -> float:
    assets = raw.account_assets(state)
    if assets <= 0:
        return 0.0
    mv = 0.0
    for h in state.get("holdings", []):
        asset = str(h.get("asset_class") or "").upper()
        name = str(h.get("security_name") or "").upper()
        code = str(h.get("code") or "")
        sid = str(h.get("security_id") or "")
        fixed = "BOND_FUND" in asset or sid.endswith(".OF")
        pooled = "ETF" in asset or "ETF" in name or code in {"510500", "159352", "159612", "159655"}
        if fixed and style == "DEFENSIVE":
            mv += raw.finite(h.get("market_value")) or 0.0
        elif pooled and style == "BROAD_MARKET":
            mv += raw.finite(h.get("market_value")) or 0.0
    return mv / assets


def construction_caps(
    row: pd.Series,
    candidate: pd.Series,
    hk: pd.Series,
    account: str,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, float]:
    raw_style_weight = raw.finite(row.get("existing_same_style_weight")) or 0.0
    style = str(row.get("portfolio_style") or "")
    excluded = non_direct_style_weight(state, style)
    row["existing_same_style_weight"] = max(0.0, raw_style_weight - excluded)
    caps = _BASE_INDEPENDENT_CAPS(row, candidate, hk, account, state, policy)

    # Exact A/H review is an exposure substitution, not a net-new sector/style addition.
    # It remains bounded by issuer/risk/confidence/liquidity caps and by existing overlap weight later.
    if raw.split_pipe(row.get("ah_overlap_security_ids")):
        tier = str(candidate.get("candidate_tier") or row.get("candidate_tier"))
        tier_cap = float(policy["tier_weight_cap"][tier])
        caps["sector_room_cap"] = tier_cap
        caps["style_room_cap"] = tier_cap
    return caps


def combined_route(real_state: str, simulation_state: str) -> str:
    states = {real_state, simulation_state}
    real_new = real_state in ACTIONABLE_NEW_SIZE
    sim_new = simulation_state in ACTIONABLE_NEW_SIZE
    if "SUBSTITUTION_REVIEW_ONLY" in states and (real_new or sim_new):
        return "ADVANCE_MIXED_NEW_AND_SUBSTITUTION_SCENARIO_TEST"
    return raw.combined_route(real_state, simulation_state)


def rebuild_report(decision: dict[str, Any]) -> str:
    return "\n".join([
        "# HKCU P4-2 Portfolio Construction Review",
        "",
        f"Status: **{decision['status']}**",
        "",
        f"- Account × Security reviews: {decision['account_security_review_count']}",
        f"- Actionable new-size review rows: {decision['actionable_new_size_count']}",
        f"- Substitution-only rows: {decision['substitution_review_count']}",
        f"- Watch/no-size rows: {decision['watch_no_size_count']}",
        f"- No-incremental-role rows: {decision['no_incremental_role_count']}",
        f"- Construction states: {decision['construction_state_counts']}",
        f"- Combined routes: {decision['combined_route_counts']}",
        f"- Next gate: {decision['next_gate']}",
        "",
        "## Construction semantics",
        "",
        "Direct-equity style-room calculations exclude fixed-income holdings and generic pooled vehicles that share only a broad descriptive style label. Exact A/H substitution review is exposure-neutral for sector/style room and therefore does not consume net-new concentration room. Mixed new-build plus substitution cases preserve both semantics in the combined route.",
        "",
        "All suggested ranges and caps remain single-security, analytical and non-additive. They are not an aggregate portfolio allocation. P4-3 must assemble full scenarios under aggregate sleeve, sector/style, funding and risk budgets.",
        "",
        "No Candidate, Simulation, Real Account, allocation or order state is mutated. trade_authority=NONE.",
        "",
    ])


def refine(root: Path, fit_dir: Path, out: Path) -> dict[str, Any]:
    contract = raw.read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    prefix = contract["output_prefix"]
    review_file = out / f"{prefix}_ACCOUNT_SECURITY_REVIEW.csv"
    combined_file = out / f"{prefix}_COMBINED_ROUTING.csv"
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    report_file = out / f"{prefix}_ASSESSMENT.md"
    manifest_file = out / f"{prefix}_MANIFEST.json"

    review = pd.read_csv(review_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    combined = pd.read_csv(combined_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    fit = pd.read_csv(
        fit_dir / "HKCU_P4_1_REASSESSMENT_ACCOUNT_SECURITY_ASSESSMENT.csv",
        dtype={"stock_code_5d": str},
        keep_default_na=False,
    )
    decision = raw.read_json(decision_file)
    quality = raw.read_json(quality_file)
    manifest = raw.read_json(manifest_file)

    raw_style = fit.set_index(["security_id", "account"])["existing_same_style_weight"].to_dict()
    review["p4_1r_existing_same_style_weight_raw"] = [
        raw.finite(raw_style.get((str(r.security_id), str(r.account)))) or 0.0
        for r in review.itertuples(index=False)
    ]
    review["construction_existing_direct_same_style_weight"] = review["existing_same_style_weight"].astype(float)
    review["construction_style_scope"] = "DIRECT_EQUITY_ONLY_EXCLUDES_FIXED_INCOME_AND_GENERIC_POOLED"

    route_rows = []
    for sid, group in review.groupby("security_id", sort=False):
        states = dict(zip(group["account"], group["construction_state"]))
        route_rows.append((sid, combined_route(states["REAL"], states["SIMULATION"])))
    route_map = dict(route_rows)
    combined["combined_route"] = combined["security_id"].map(route_map)
    decision["combined_route_counts"] = combined["combined_route"].value_counts().astype(int).to_dict()
    decision["semantic_cleanup"] = {
        "direct_equity_style_room_excludes_fixed_income_and_generic_pooled": True,
        "exact_ah_substitution_does_not_consume_net_new_sector_style_room": True,
        "mixed_new_and_substitution_route_preserves_both_account_semantics": True,
    }
    quality["direct_equity_style_room_excludes_fixed_income_and_generic_pooled"] = True
    quality["substitution_caps_ignore_net_new_sector_style_room"] = True
    quality["mixed_new_substitution_route_preserved"] = True

    review.to_csv(review_file, index=False)
    combined.to_csv(combined_file, index=False)
    raw.write_json(decision_file, decision)
    raw.write_json(quality_file, quality)
    report_file.write_text(rebuild_report(decision), encoding="utf-8")

    for path in (review_file, combined_file, decision_file, quality_file, report_file):
        if path.name in manifest.get("files", {}):
            manifest["files"][path.name] = {"sha256": raw.sha256_file(path), "bytes": path.stat().st_size}
    raw.write_json(manifest_file, manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def build(root: Path, context_dir: Path, fit_dir: Path, out: Path) -> dict[str, Any]:
    raw.independent_caps = construction_caps
    raw.build(root, context_dir, fit_dir, out)
    return refine(root, fit_dir, out)


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
