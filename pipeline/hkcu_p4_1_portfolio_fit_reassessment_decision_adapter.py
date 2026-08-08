#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import hkcu_p4_1_portfolio_fit_reassessment as raw
from pipeline import hkcu_p4_1_portfolio_fit_assessment as base

PROGRAM_ID = "HKCU-P4-1-REASSESSMENT"
TRADE_AUTHORITY = "NONE"
ACCOUNTS = ("REAL", "SIMULATION")
NON_SECURITY_SPECIFIC_NOTES = {
    "NUMERIC_SIZE_REQUIRES_P4_2",
    "FUNDING_REQUIRES_SEPARATE_CAPITAL_DECISION",
    "POOLED_EQUITY_EXPOSURE_PRESENT",
}


def split_pipe(value: Any) -> list[str]:
    return [x for x in str(value or "").split("|") if x]


def clean_fit_constraints(value: Any) -> list[str]:
    return sorted({x for x in split_pipe(value) if x not in NON_SECURITY_SPECIFIC_NOTES})


def compound_no_incremental_v2(row: pd.Series) -> bool:
    return (
        str(row.get("opportunity_cost_state")) == "HIGH_RELATIVE_OPPORTUNITY_COST"
        and str(row.get("sector_impact_state")) == "INCREASES_EXISTING_DIRECT_SECTOR"
        and str(row.get("style_impact_state")) == "INCREASES_EXISTING_STYLE"
        and str(row.get("marginal_risk_state")) not in {"", "UNRESOLVED", "IMPROVES_DIVERSIFICATION"}
    )


def fit_state_after_semantic_cleanup(row: pd.Series, constraints: list[str]) -> tuple[str, str, str]:
    raw_state = str(row.get("fit_state"))
    direct = bool(split_pipe(row.get("direct_overlap_security_ids")))
    if raw_state == "BLOCK_PORTFOLIO_FIT":
        return "BLOCK_PORTFOLIO_FIT", "NO_SIZE_BLOCKED", str(row.get("fit_reason"))
    if raw_state == "DEFER_PORTFOLIO_CONTEXT":
        return "DEFER_PORTFOLIO_CONTEXT", "NO_SIZE_PENDING_CONTEXT", str(row.get("fit_reason"))
    if direct:
        return (
            "NO_INCREMENTAL_ROLE",
            "NO_SIZE_NO_INCREMENTAL_ROLE",
            "The exact security is already held; no incremental role is demonstrated at this assessment gate.",
        )
    if compound_no_incremental_v2(row):
        return (
            "NO_INCREMENTAL_ROLE",
            "NO_SIZE_NO_INCREMENTAL_ROLE",
            "High relative opportunity cost combines with added existing sector/style concentration and marginal risk that does not explicitly improve diversification; this is a portfolio-role conclusion, not a bearish company rejection.",
        )
    if constraints:
        return (
            "FIT_WITH_CONSTRAINTS",
            "CONSTRUCTION_REVIEW_ONLY_NO_NUMERIC_TARGET",
            "All hard rules pass; security/account-specific construction constraints remain: " + ",".join(constraints),
        )
    return (
        "FIT",
        "CONSTRUCTION_REVIEW_ONLY_NO_NUMERIC_TARGET",
        "All applicable hard and decision rules pass with no security/account-specific fit constraint.",
    )


def update_rule_semantics(rule_df: pd.DataFrame, account_df: pd.DataFrame) -> pd.DataFrame:
    out = rule_df.copy()
    lookup = account_df.set_index(["security_id", "account"])
    for idx, rule in out.iterrows():
        key = (str(rule["security_id"]), str(rule["account"]))
        row = lookup.loc[key]
        rid = str(rule["rule_id"])
        if rid == "P4R09" and not split_pipe(row.get("direct_overlap_security_ids")) and not split_pipe(row.get("ah_overlap_security_ids")):
            out.at[idx, "rule_state"] = "PASS"
            out.at[idx, "rationale"] = (
                "No direct or exact A/H same-issuer overlap is identified. Pooled vehicles, where present, remain explicit portfolio review context but pooled presence alone is not candidate-specific duplicate-exposure evidence."
            )
        elif rid == "P4R14":
            out.at[idx, "rule_state"] = "PASS"
            out.at[idx, "rationale"] = (
                f"analytical_sizing_envelope={row.get('analytical_sizing_envelope')}; the envelope is explicit and analytical only. Deferring numeric target sizing to P4-2 is a phase boundary, not a security-specific fit constraint."
            )
        elif rid == "P4R15":
            out.at[idx, "rule_state"] = "PASS"
            if str(rule["account"]) == "REAL":
                out.at[idx, "rationale"] = (
                    "REAL cash is broker execution balance only; external liquidity is excluded and no fixed strategic cash target is invented. A later funding decision is separate from security-level portfolio fit."
                )
            else:
                out.at[idx, "rationale"] = (
                    "SIMULATION available cash is funding context only, not alpha or automatic admission authority; cash semantics are preserved."
                )
    return out


def rebuild_report(combined: pd.DataFrame, decision: dict[str, Any]) -> str:
    lines = [
        "# HKCU P4-1 Portfolio Fit Reassessment",
        "",
        f"Status: **{decision['status']}**",
        "",
        f"- Candidates: {len(combined)}",
        f"- Account × Security assessments: {decision['account_security_assessment_count']}",
        f"- Rule assessments: {decision['rule_assessment_row_count']}",
        f"- Runtime context gaps: {decision['context_gap_count']}",
        f"- Next gate: {decision['next_gate']}",
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
    for row in combined.itertuples(index=False):
        lines.append(
            f"| {row.p2a_overall_rank} | {row.stock_code_5d} | {row.security_name} | {row.real_fit_state} | {row.simulation_fit_state} | {row.combined_route} |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "This reassessment is analytical only. It does not change Candidate membership, Real Account or Simulation positions, allocations, target weights, cash policy, orders or trade authority. trade_authority=NONE.",
        "",
    ]
    return "\n".join(lines)


def refine(root: Path, context_dir: Path, out: Path) -> dict[str, Any]:
    contract = base.read_json(root / "config/hkcu_p4_1_portfolio_fit_reassessment_contract.json")
    prefix = contract["output_prefix"]
    account_file = out / f"{prefix}_ACCOUNT_SECURITY_ASSESSMENT.csv"
    rule_file = out / f"{prefix}_RULE_ASSESSMENT.csv"
    combined_file = out / f"{prefix}_COMBINED_ROUTING.csv"
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    report_file = out / f"{prefix}_ASSESSMENT.md"
    manifest_file = out / f"{prefix}_MANIFEST.json"

    account = pd.read_csv(account_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    rules = pd.read_csv(rule_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    combined = pd.read_csv(combined_file, dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = base.read_json(decision_file)
    quality = base.read_json(quality_file)
    manifest = base.read_json(manifest_file)

    refined_rows: list[dict[str, Any]] = []
    for _, row in account.iterrows():
        constraints = clean_fit_constraints(row.get("constraints"))
        fit_state, envelope, reason = fit_state_after_semantic_cleanup(row, constraints)
        record = row.to_dict()
        record["constraints"] = "|".join(constraints)
        record["fit_state"] = fit_state
        record["fit_reason"] = reason
        record["analytical_sizing_envelope"] = envelope
        refined_rows.append(record)
    account = pd.DataFrame(refined_rows).sort_values(["p2a_overall_rank", "account"]).reset_index(drop=True)
    rules = update_rule_semantics(rules, account).sort_values(["p2a_overall_rank", "account", "rule_id"]).reset_index(drop=True)

    combined_rows: list[dict[str, Any]] = []
    for sid, group in account.groupby("security_id", sort=False):
        states = dict(zip(group["account"], group["fit_state"]))
        old = combined[combined["security_id"].eq(sid)].iloc[0].to_dict()
        old["real_fit_state"] = states["REAL"]
        old["simulation_fit_state"] = states["SIMULATION"]
        old["combined_route"] = raw.combined_route(states["REAL"], states["SIMULATION"])
        combined_rows.append(old)
    combined = pd.DataFrame(combined_rows).sort_values("p2a_overall_rank").reset_index(drop=True)

    decision["account_fit_state_counts"] = {
        account_name: account[account["account"].eq(account_name)]["fit_state"].value_counts().astype(int).to_dict()
        for account_name in ACCOUNTS
    }
    decision["combined_route_counts"] = combined["combined_route"].value_counts().astype(int).to_dict()
    decision["semantic_cleanup"] = {
        "numeric_sizing_phase_boundary_not_fit_constraint": True,
        "real_cash_funding_note_not_fit_constraint": True,
        "pooled_presence_not_candidate_specific_duplicate_constraint": True,
        "non_direct_no_incremental_requires_high_opportunity_cost_plus_sector_style_concentration_plus_non_improving_marginal_risk": True,
    }
    quality["universal_governance_notes_removed_from_fit_constraints"] = True
    quality["pooled_presence_alone_called_duplicate_exposure"] = False
    quality["non_direct_no_incremental_is_multi_dimension"] = True

    account.to_csv(account_file, index=False)
    rules.to_csv(rule_file, index=False)
    combined.to_csv(combined_file, index=False)
    base.write_json(decision_file, decision)
    base.write_json(quality_file, quality)
    report_file.write_text(rebuild_report(combined, decision), encoding="utf-8")

    for path in (account_file, rule_file, combined_file, decision_file, quality_file, report_file):
        if path.name in manifest.get("files", {}):
            manifest["files"][path.name] = {"sha256": base.sha256_file(path), "bytes": path.stat().st_size}
    base.write_json(manifest_file, manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def build(root: Path, context_dir: Path, out: Path) -> dict[str, Any]:
    raw.build(root, context_dir, out)
    return refine(root, context_dir, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--context-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.context_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
