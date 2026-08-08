#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P4-1-REASSESSMENT"
TRADE_AUTHORITY = "NONE"
POSITIVE = {"FIT", "FIT_WITH_CONSTRAINTS"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_route(real_state: str, sim_state: str) -> str:
    states = {real_state, sim_state}
    if real_state == "BLOCK_PORTFOLIO_FIT" and sim_state == "BLOCK_PORTFOLIO_FIT":
        return "BLOCK_PORTFOLIO_FIT"
    if "DEFER_PORTFOLIO_CONTEXT" in states:
        return "DEFER_PORTFOLIO_CONTEXT"
    if real_state in POSITIVE and sim_state in POSITIVE:
        return "ADVANCE_DUAL_CONSTRUCTION_REVIEW"
    if real_state in POSITIVE:
        return "ADVANCE_REAL_ACCOUNT_REVIEW"
    if sim_state in POSITIVE:
        return "ADVANCE_SIMULATION_CONSTRUCTION_REVIEW"
    return "HOLD_PORTFOLIO_WATCH"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--context-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    root = Path(args.repo_root)
    context_dir = Path(args.context_dir)
    out = Path(args.output)

    contract = read_json(root / "config/hkcu_p4_1_portfolio_fit_reassessment_contract.json")
    prefix = contract["output_prefix"]
    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    manifest = read_json(out / f"{prefix}_MANIFEST.json")
    account = pd.read_csv(out / f"{prefix}_ACCOUNT_SECURITY_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    rules = pd.read_csv(out / f"{prefix}_RULE_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    combined = pd.read_csv(out / f"{prefix}_COMBINED_ROUTING.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    gaps = pd.read_csv(out / f"{prefix}_CONTEXT_GAP_REGISTER.csv", keep_default_na=False)
    p4r = read_json(context_dir / "HKCU_P4_1R_DECISION.json")

    errors: list[str] = []
    accept = contract["acceptance"]
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") not in {accept["pass_status"], accept["context_blocked_status"], accept["integrity_fail_status"]}: errors.append("STATUS")
    if len(account) != 140 or account.duplicated(["security_id", "account"]).any(): errors.append("ACCOUNT_CONTEXT")
    if set(account["account"]) != {"REAL", "SIMULATION"}: errors.append("ACCOUNT_SET")
    if len(rules) != 2100 or rules.duplicated(["security_id", "account", "rule_id"]).any(): errors.append("RULE_CONTEXT")
    if rules.groupby(["security_id", "account"])["rule_id"].nunique().ne(15).any(): errors.append("RULES_PER_ACCOUNT_SECURITY")
    if len(combined) != 70 or combined["security_id"].nunique() != 70: errors.append("COMBINED_CONTEXT")
    if not set(account["fit_state"]).issubset(set(contract["account_fit_states"])): errors.append("FIT_STATE_VOCABULARY")
    if not set(rules["rule_state"]).issubset(set(contract["rule_states"])): errors.append("RULE_STATE_VOCABULARY")
    if not set(combined["combined_route"]).issubset(set(contract["combined_routing_states"])): errors.append("ROUTE_VOCABULARY")

    for sid, group in account.groupby("security_id"):
        states = dict(zip(group["account"], group["fit_state"]))
        got = combined.loc[combined["security_id"].eq(sid), "combined_route"]
        if len(got) != 1 or got.iloc[0] != expected_route(states["REAL"], states["SIMULATION"]):
            errors.append("ROUTE_DERIVATION")
            break

    hard_ids = {f"P4R{i:02d}" for i in range(1, 8)}
    hard = rules[rules["rule_id"].isin(hard_ids)]
    positive_or_no_role = account[account["fit_state"].isin({"FIT", "FIT_WITH_CONSTRAINTS", "NO_INCREMENTAL_ROLE"})][["security_id", "account"]]
    for row in positive_or_no_role.itertuples(index=False):
        local = hard[(hard["security_id"].eq(row.security_id)) & (hard["account"].eq(row.account))]
        if local["rule_state"].isin({"BLOCK", "DEFER"}).any():
            errors.append("POSITIVE_WITH_HARD_FAILURE")
            break

    constrained = account[account["fit_state"].eq("FIT_WITH_CONSTRAINTS")]
    if len(constrained) and constrained["constraints"].astype(str).str.len().eq(0).any(): errors.append("CONSTRAINT_STATE_WITHOUT_CONSTRAINT")
    no_role = account[account["fit_state"].eq("NO_INCREMENTAL_ROLE")]
    if len(no_role) and ~no_role["analytical_sizing_envelope"].eq("NO_SIZE_NO_INCREMENTAL_ROLE").all(): errors.append("NO_ROLE_WITH_SIZE")
    deferred = account[account["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT")]
    if len(deferred) and deferred["context_defer_rules"].astype(str).str.len().eq(0).any(): errors.append("DEFER_WITHOUT_RULE")

    for frame, name in ((account, "ACCOUNT"), (rules, "RULES"), (combined, "COMBINED")):
        if "trade_authority" not in frame.columns or not frame["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append(name + "_AUTHORITY")
    if account["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("PORTFOLIO_MUTATION")
    if combined["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("COMBINED_MUTATION")
    if (pd.to_numeric(account["orders_created"], errors="coerce").fillna(0) != 0).any(): errors.append("ACCOUNT_ORDERS")
    if (pd.to_numeric(combined["orders_created"], errors="coerce").fillna(0) != 0).any(): errors.append("COMBINED_ORDERS")

    if decision.get("status") == accept["pass_status"]:
        if len(gaps) != 0: errors.append("PASS_WITH_CONTEXT_GAPS")
        if account["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").any(): errors.append("PASS_WITH_DEFER")
        if decision.get("next_gate") != accept["next_gate_on_pass"]: errors.append("PASS_NEXT_GATE")
        if p4r.get("status") != contract["runtime_context_contract"]["required_status"]: errors.append("PASS_WITHOUT_P4_1R_PASS")
        if int(p4r.get("residual_decision_critical_gap_count", -1)) != 0: errors.append("PASS_WITH_P4_1R_RESIDUAL")
        if int(p4r.get("context_ready_account_security_count", -1)) != 140: errors.append("PASS_WITH_P4_1R_NOT_READY")
    elif decision.get("status") == accept["context_blocked_status"]:
        if len(gaps) == 0 and not account["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").any(): errors.append("BLOCKED_WITHOUT_CONTEXT_GAP")
        if decision.get("next_gate") != accept["context_repair_next_gate"]: errors.append("BLOCKED_NEXT_GATE")

    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "portfolio_allocations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append("DECISION_" + key.upper())
    if decision.get("trade_authority") != TRADE_AUTHORITY or quality.get("trade_authority") != TRADE_AUTHORITY or manifest.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("META_AUTHORITY")
    if quality.get("weighted_score") is not False or quality.get("fixed_top_n") is not False: errors.append("FORBIDDEN_SCORING")
    if quality.get("fuzzy_identity_matching") is not False or quality.get("sector_neutral_fill") is not False: errors.append("FORBIDDEN_INFERENCE")
    if quality.get("ticker_count_diversification_inference") is not False: errors.append("FORBIDDEN_DIVERSIFICATION_INFERENCE")
    if quality.get("trailing_return_called_expected_return") is not False or quality.get("ah_discount_called_alpha") is not False: errors.append("FORBIDDEN_RETURN_SEMANTICS")

    for name, meta in manifest.get("files", {}).items():
        path = out / name
        if not path.exists() or sha256_file(path) != meta.get("sha256") or path.stat().st_size != int(meta.get("bytes", -1)):
            errors.append("MANIFEST_" + name)

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "errors": sorted(set(errors)),
        "account_security_assessment_count": len(account),
        "rule_assessment_row_count": len(rules),
        "combined_routing_count": len(combined),
        "context_gap_count": len(gaps),
        "operational_status": decision.get("status"),
        "trade_authority": TRADE_AUTHORITY,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit("P4_1_REASSESSMENT_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))


if __name__ == "__main__":
    main()
