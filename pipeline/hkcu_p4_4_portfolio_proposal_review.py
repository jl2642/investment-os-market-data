#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

PROGRAM_ID = "HKCU-P4-4"
TRADE_AUTHORITY = "NONE"


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


def current_weight(state: dict[str, Any], security_id: str) -> float:
    assets = account_assets(state)
    if assets <= 0:
        return 0.0
    mv = sum(
        finite(x.get("market_value")) or 0.0
        for x in state.get("holdings", [])
        if str(x.get("security_id")) == security_id
    )
    return mv / assets


def scenario_review_state(scenario_id: str, family: str, policy: dict[str, Any]) -> tuple[str, str]:
    if family == "MAX_AH_SUBSTITUTION_STRESS":
        return (
            "RESEARCH_ONLY_AH_SUBSTITUTION",
            "A/H stress proves implementation feasibility only; relative-value context is not alpha and no substitution proposal is authorized without a separate evidence gate.",
        )
    if scenario_id == policy["real_preferred_scenario"]:
        return (
            "PREFERRED_PORTFOLIO_PROPOSAL",
            "Initial REAL proposal uses the smallest passing base scenario because every REAL scenario requires external funding and there is no scenario-specific incremental-return evidence justifying larger immediate capital deployment.",
        )
    if scenario_id == policy["real_conditional_expansion_scenario"]:
        return (
            "CONDITIONAL_EXPANSION_ALTERNATIVE",
            "REAL balanced sleeve remains an explicit next-step alternative after Phase 5 evidence, funding and observation review; it is not the initial proposal.",
        )
    if scenario_id == policy["real_hold_expansion_scenario"]:
        return (
            "HOLD_EXPANSION",
            "REAL expanded sleeve is not proposed at current evidence because it increases absolute capital and downside exposure without scenario-specific incremental-return evidence.",
        )
    if scenario_id == policy["simulation_preferred_scenario"]:
        return (
            "PREFERRED_PORTFOLIO_PROPOSAL",
            "SIM balanced is the primary observation proposal: it is fully funded, passes all aggregate risk constraints and provides broader learning coverage without immediately using the maximum tested sleeve.",
        )
    if scenario_id == policy["simulation_conservative_alternative"]:
        return (
            "CONSERVATIVE_ALTERNATIVE",
            "SIM conservative remains the lower-capital fallback observation scenario.",
        )
    if scenario_id == policy["simulation_expanded_alternative"]:
        return (
            "CONDITIONAL_EXPANSION_ALTERNATIVE",
            "SIM expanded remains an optional broader stress/learning scenario, not the default proposal, because larger absolute capital exposure has no demonstrated incremental-alpha advantage.",
        )
    return "HOLD_UNCLASSIFIED", "Scenario is not part of the frozen proposal routing surface."


def build(root: Path, p4_2_dir: Path, p4_3_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p4_4_portfolio_proposal_review_contract.json")
    p4_3_contract = read_json(root / "config/hkcu_p4_3_portfolio_construction_scenario_test_contract.json")
    p4_2_contract = read_json(root / "config/hkcu_p4_2_portfolio_construction_review_contract.json")
    policy = contract["proposal_policy"]
    prefix = contract["output_prefix"]
    p4_3_prefix = p4_3_contract["output_prefix"]
    p4_2_prefix = p4_2_contract["output_prefix"]

    p4_3_decision = read_json(p4_3_dir / f"{p4_3_prefix}_DECISION.json")
    summary = pd.read_csv(p4_3_dir / f"{p4_3_prefix}_SCENARIO_SUMMARY.csv", keep_default_na=False)
    allocations = pd.read_csv(
        p4_3_dir / f"{p4_3_prefix}_SCENARIO_ALLOCATIONS.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )
    p4_2_review = pd.read_csv(
        p4_2_dir / f"{p4_2_prefix}_ACCOUNT_SECURITY_REVIEW.csv",
        dtype={"stock_code_5d": str}, keep_default_na=False,
    )
    inputs = contract["authoritative_inputs"]
    states = {
        "REAL": read_json(root / inputs["real_positions_current"]),
        "SIMULATION": read_json(root / inputs["simulation_positions_current"]),
    }

    errors: list[str] = []
    if p4_3_decision.get("status") != contract["entry_contract"]["required_p4_3_status"]:
        errors.append("P4_3_STATUS")
    if len(summary) != contract["entry_contract"]["required_scenario_count"]:
        errors.append(f"SCENARIO_COUNT:{len(summary)}")
    if not summary["scenario_status"].eq("PASS").all():
        errors.append("NONPASS_SCENARIO")
    if summary["scenario_id"].duplicated().any():
        errors.append("DUPLICATE_SCENARIO")
    if any(states[a].get("trade_authority") != TRADE_AUTHORITY for a in states):
        errors.append("ACCOUNT_AUTHORITY")

    scenario_reviews: list[dict[str, Any]] = []
    for row in summary.sort_values(["account", "hk_sleeve_target", "scenario_id"]).itertuples(index=False):
        review_state, rationale = scenario_review_state(str(row.scenario_id), str(row.scenario_family), policy)
        scenario_reviews.append({
            "scenario_id": str(row.scenario_id),
            "scenario_family": str(row.scenario_family),
            "account": str(row.account),
            "scenario_review_state": review_state,
            "rationale": rationale,
            "hk_sleeve_target": float(row.hk_sleeve_target),
            "hk_sleeve_allocated": float(row.hk_sleeve_allocated),
            "position_count": int(row.position_count),
            "gross_drawdown_stress_weight": float(row.gross_drawdown_stress_weight),
            "funding_status": str(row.funding_status),
            "sector_mix": str(row.sector_mix),
            "style_mix": str(row.style_mix),
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })
    scenario_review = pd.DataFrame(scenario_reviews)

    preferred = {
        "REAL": policy["real_preferred_scenario"],
        "SIMULATION": policy["simulation_preferred_scenario"],
    }
    proposal_summaries: list[dict[str, Any]] = []
    proposal_allocations: list[dict[str, Any]] = []
    p4_idx = p4_2_review.set_index(["security_id", "account"], drop=False)

    for account, scenario_id in preferred.items():
        s = summary[(summary["scenario_id"].eq(scenario_id)) & (summary["account"].eq(account))]
        if len(s) != 1:
            errors.append(f"PREFERRED_SCENARIO_NOT_UNIQUE:{account}:{scenario_id}")
            continue
        srow = s.iloc[0]
        rows = allocations[(allocations["scenario_id"].eq(scenario_id)) & (allocations["account"].eq(account))].copy()
        if rows.empty:
            errors.append(f"PREFERRED_SCENARIO_EMPTY:{account}")
            continue
        if not rows["allocation_type"].eq("NEW_BUILD").all():
            errors.append(f"PREFERRED_SCENARIO_HAS_SUBSTITUTION:{account}")
        corrs: list[float] = []
        downside_corrs: list[float] = []
        for r in rows.itertuples(index=False):
            key = (str(r.security_id), account)
            if key not in p4_idx.index:
                errors.append(f"P4_2_ROW_MISSING:{account}:{r.security_id}")
                continue
            p = p4_idx.loc[key]
            if isinstance(p, pd.DataFrame):
                p = p.iloc[0]
            corr = finite(p.get("candidate_portfolio_correlation"))
            dcorr = finite(p.get("downside_correlation"))
            if corr is not None: corrs.append(corr)
            if dcorr is not None: downside_corrs.append(dcorr)
            proposal_allocations.append({
                "account": account,
                "proposal_scenario_id": scenario_id,
                "security_id": str(r.security_id),
                "stock_code_5d": str(r.stock_code_5d).zfill(5),
                "security_name": str(r.security_name),
                "current_weight": current_weight(states[account], str(r.security_id)),
                "proposed_weight": float(r.scenario_weight),
                "economic_sector_industry": str(r.economic_sector_industry),
                "portfolio_style": str(r.portfolio_style),
                "funding_source_class": str(r.funding_source_class),
                "historical_drawdown_loss_weight": float(r.gross_drawdown_stress_weight),
                "candidate_portfolio_correlation": corr,
                "downside_correlation": dcorr,
                "portfolio_role": str(p.get("portfolio_role", "")),
                "principal_falsifier": str(p.get("principal_falsifier", "")),
                "review_triggers": str(p.get("review_triggers", "")),
                "alternative_route": (
                    policy["real_conditional_expansion_scenario"]
                    if account == "REAL" else
                    f"{policy['simulation_conservative_alternative']}|{policy['simulation_expanded_alternative']}"
                ),
                "initial_review_date": policy["initial_review_date"],
                "permission": policy["real_permission"] if account == "REAL" else policy["simulation_permission"],
                "execution_status": policy["real_execution_status"] if account == "REAL" else policy["simulation_execution_status"],
                "portfolio_mutation": False,
                "orders_created": 0,
                "trade_authority": TRADE_AUTHORITY,
            })
        proposal_summaries.append({
            "account": account,
            "preferred_scenario_id": scenario_id,
            "decision": "BUY_PROPOSAL" if account == "REAL" else "RESEARCH",
            "permission": policy["real_permission"] if account == "REAL" else policy["simulation_permission"],
            "execution_status": policy["real_execution_status"] if account == "REAL" else policy["simulation_execution_status"],
            "hk_sleeve_proposed": float(srow["hk_sleeve_allocated"]),
            "position_count": int(srow["position_count"]),
            "funding_source": str(srow["funding_status"]),
            "max_historical_drawdown_loss_weight": float(srow["gross_drawdown_stress_weight"]),
            "median_candidate_portfolio_correlation": float(pd.Series(corrs).median()) if corrs else None,
            "median_downside_correlation": float(pd.Series(downside_corrs).median()) if downside_corrs else None,
            "lookthrough_sector_mix": str(srow["sector_mix"]),
            "lookthrough_style_mix": str(srow["style_mix"]),
            "alternative_scenarios": (
                f"{policy['real_conditional_expansion_scenario']}|{policy['real_hold_expansion_scenario']}"
                if account == "REAL" else
                f"{policy['simulation_conservative_alternative']}|{policy['simulation_expanded_alternative']}"
            ),
            "exit_or_hold_condition": "ANY_SECURITY_PRINCIPAL_FALSIFIER_OR_PORTFOLIO_CONSTRAINT_BREACH_REQUIRES_REVIEW_BEFORE_ANY_NEXT_ACTION",
            "initial_review_date": policy["initial_review_date"],
            "pretrade_memo_required_before_real_execution": account == "REAL",
            "target_writeback": False,
            "portfolio_mutation": False,
            "orders_created": 0,
            "trade_authority": TRADE_AUTHORITY,
        })

    proposal_summary = pd.DataFrame(proposal_summaries)
    proposal_allocation = pd.DataFrame(proposal_allocations)

    if len(scenario_review) != contract["acceptance"]["scenario_review_count"]:
        errors.append("SCENARIO_REVIEW_COUNT")
    if len(proposal_summary) != contract["acceptance"]["preferred_proposal_count"]:
        errors.append("PREFERRED_PROPOSAL_COUNT")
    if int(proposal_summary["account"].eq("REAL").sum()) if len(proposal_summary) else 0 != contract["acceptance"]["real_preferred_proposal_count"]:
        errors.append("REAL_PREFERRED_COUNT")
    if int(proposal_summary["account"].eq("SIMULATION").sum()) if len(proposal_summary) else 0 != contract["acceptance"]["simulation_preferred_proposal_count"]:
        errors.append("SIM_PREFERRED_COUNT")

    status = contract["acceptance"]["pass_status"] if not errors else contract["acceptance"]["fail_status"]
    decision = {
        "program_id": PROGRAM_ID,
        "phase": contract["phase"],
        "as_of_date": contract["as_of_date"],
        "status": status,
        "entry_p4_3_status": p4_3_decision.get("status"),
        "scenario_review_count": len(scenario_review),
        "preferred_proposal_count": len(proposal_summary),
        "preferred_real_scenario": policy["real_preferred_scenario"],
        "preferred_simulation_scenario": policy["simulation_preferred_scenario"],
        "ah_substitution_in_preferred_proposal": False,
        "target_portfolio_writeback": False,
        "pretrade_memo_produced": False,
        "user_trade_confirmation_recorded": False,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "phase_close_status": contract["acceptance"]["phase_close_status"] if not errors else "PHASE_4_NOT_CLOSED",
        "next_phase": contract["acceptance"]["next_phase_on_pass"] if not errors else contract["acceptance"]["repair_gate"],
        "additional_p4_subphases_allowed": False,
        "integrity_failures": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    quality = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "weighted_score": False,
        "fixed_top_n": False,
        "candidate_rank_used_as_proposal_authority": False,
        "preferred_real_uses_staged_external_funding_principle": True,
        "simulation_balanced_is_observation_proposal_not_expected_return_claim": True,
        "ah_relative_value_called_alpha": False,
        "ah_stress_promoted_to_preferred_proposal": False,
        "proposal_fields_cover_funding_loss_correlation_lookthrough_alternative_exit_review": True,
        "target_writeback": False,
        "pretrade_memo_produced": False,
        "user_trade_confirmation_recorded": False,
        "portfolio_mutations": 0,
        "orders_created": 0,
        "trade_authority": TRADE_AUTHORITY,
        "hard_failures": errors,
    }

    scenario_file = out / f"{prefix}_SCENARIO_REVIEW.csv"
    proposal_file = out / f"{prefix}_PREFERRED_PROPOSALS.csv"
    allocation_file = out / f"{prefix}_PROPOSAL_ALLOCATIONS.csv"
    decision_file = out / f"{prefix}_DECISION.json"
    quality_file = out / f"{prefix}_QUALITY_REPORT.json"
    report_file = out / f"{prefix}_ASSESSMENT.md"
    manifest_file = out / f"{prefix}_MANIFEST.json"

    scenario_review.to_csv(scenario_file, index=False)
    proposal_summary.to_csv(proposal_file, index=False)
    proposal_allocation.to_csv(allocation_file, index=False)
    write_json(decision_file, decision)
    write_json(quality_file, quality)

    real = proposal_summary[proposal_summary["account"].eq("REAL")].iloc[0] if len(proposal_summary[proposal_summary["account"].eq("REAL")]) else None
    sim = proposal_summary[proposal_summary["account"].eq("SIMULATION")].iloc[0] if len(proposal_summary[proposal_summary["account"].eq("SIMULATION")]) else None
    lines = [
        "# HKCU P4-4 Portfolio Proposal Review",
        "",
        f"Status: **{status}**",
        "",
        f"Phase closure: **{decision['phase_close_status']}**",
        f"Next phase: **{decision['next_phase']}**",
        "",
        "## Preferred proposal surface",
        "",
        f"- REAL: {policy['real_preferred_scenario']} / {float(real['hk_sleeve_proposed']) if real is not None else 0:.2%} HK sleeve / RESEARCH_ONLY / NOT AUTHORIZED FOR EXECUTION.",
        f"- SIMULATION: {policy['simulation_preferred_scenario']} / {float(sim['hk_sleeve_proposed']) if sim is not None else 0:.2%} HK sleeve / RESEARCH_ONLY / NO STATE MUTATION.",
        "- A/H stress variants remain research-only and are not promoted into either preferred proposal.",
        "",
        "REAL uses staged capital migration: because every passing REAL scenario requires external funding and no scenario-specific incremental-return evidence establishes that larger immediate deployment is superior, the initial proposal is the smallest passing base sleeve. The 10% balanced sleeve remains a conditional expansion alternative and the 15% expanded sleeve is held at current evidence.",
        "",
        "SIMULATION uses the balanced base sleeve as the primary observation proposal. Conservative and expanded scenarios remain explicit alternatives; this does not claim the balanced scenario has superior expected return.",
        "",
        "P4-4 creates a research portfolio proposal only. It does not create a Pre-trade Memo, user approval, target writeback, state mutation, broker order or trade authority. Phase 4 is closed on PASS; no additional P4 subphase is authorized.",
        "",
        "trade_authority=NONE.",
        "",
    ]
    report_file.write_text("\n".join(lines), encoding="utf-8")

    manifest = {"program_id": PROGRAM_ID, "status": status, "files": {}, "trade_authority": TRADE_AUTHORITY}
    for path in (scenario_file, proposal_file, allocation_file, decision_file, quality_file, report_file):
        manifest["files"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(manifest_file, manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p4-2-dir", required=True)
    ap.add_argument("--p4-3-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    build(Path(args.repo_root).resolve(), Path(args.p4_2_dir).resolve(), Path(args.p4_3_dir).resolve(), Path(args.output).resolve())


if __name__ == "__main__":
    main()
