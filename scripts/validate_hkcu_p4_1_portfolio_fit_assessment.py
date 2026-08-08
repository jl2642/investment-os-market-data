#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P4-1"
TRADE_AUTHORITY = "NONE"
EXPECTED_RULE_IDS = {f"P4R{i:02d}" for i in range(1, 16)}
EXPECTED_ACCOUNTS = {"REAL", "SIMULATION"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    root, out = Path(args.repo_root), Path(args.output)
    contract = read_json(root / "config/hkcu_p4_1_portfolio_fit_assessment_contract.json")
    prefix = contract["output_prefix"]
    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY_REPORT.json")
    account = pd.read_csv(out / f"{prefix}_ACCOUNT_SECURITY_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    rules = pd.read_csv(out / f"{prefix}_RULE_ASSESSMENT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    combined = pd.read_csv(out / f"{prefix}_COMBINED_ROUTING.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    gaps = pd.read_csv(out / f"{prefix}_CONTEXT_GAP_REGISTER.csv", keep_default_na=False)
    manifest = read_json(out / f"{prefix}_MANIFEST.json")
    errors: list[str] = []

    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") not in {contract["acceptance"]["pass_status"], contract["acceptance"]["context_blocked_status"]}: errors.append("DECISION_STATUS")
    if len(combined) != 70 or combined["security_id"].nunique() != 70: errors.append("COMBINED_COUNT")
    if len(account) != 140 or account.duplicated(["security_id", "account"]).any(): errors.append("ACCOUNT_COUNT_OR_DUPLICATE")
    if set(account["account"]) != EXPECTED_ACCOUNTS: errors.append("ACCOUNT_SET")
    if len(rules) != 2100 or rules.duplicated(["security_id", "account", "rule_id"]).any(): errors.append("RULE_COUNT_OR_DUPLICATE")
    if set(rules["rule_id"]) != EXPECTED_RULE_IDS: errors.append("RULE_SET")
    group_sizes = rules.groupby(["security_id", "account"]).size()
    if not (group_sizes == 15).all(): errors.append("RULES_PER_ACCOUNT_SECURITY")
    if not set(rules["rule_state"]).issubset(set(contract["rule_states"])): errors.append("RULE_STATE_VOCABULARY")
    if not set(account["fit_state"]).issubset(set(contract["account_fit_states"])): errors.append("FIT_STATE_VOCABULARY")
    if not set(combined["combined_route"]).issubset(set(contract["combined_routing_states"])): errors.append("ROUTE_VOCABULARY")
    if not account["trade_authority"].eq(TRADE_AUTHORITY).all() or not rules["trade_authority"].eq(TRADE_AUTHORITY).all() or not combined["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("TRADE_AUTHORITY")
    if account["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("PORTFOLIO_MUTATION")
    if combined["portfolio_mutation"].astype(str).str.lower().isin({"true", "1"}).any(): errors.append("COMBINED_MUTATION")
    if (pd.to_numeric(account["orders_created"], errors="coerce").fillna(0) != 0).any() or (pd.to_numeric(combined["orders_created"], errors="coerce").fillna(0) != 0).any(): errors.append("ORDERS")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "portfolio_allocations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append("DECISION_" + key.upper())

    required_gaps = {"CTX_SECTOR_INDUSTRY", "CTX_MARGINAL_RISK", "CTX_PORTFOLIO_FACTOR_LOOKTHROUGH", "CTX_EXPECTED_RETURN_OPPORTUNITY_COST"}
    observed_gaps = set(gaps["context_id"].astype(str))
    if not required_gaps.issubset(observed_gaps): errors.append("CONTEXT_GAP_REGISTER")
    # Fail-closed proof: P4R10/11/12/13 may not be neutral-filled while these accepted context gaps remain.
    for rid in ("P4R10", "P4R11", "P4R12", "P4R13"):
        x = rules[rules["rule_id"].eq(rid)]
        if len(x) != 140 or not x["rule_state"].eq("DEFER").all(): errors.append("FAIL_CLOSED_" + rid)
    if not account["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").all(): errors.append("ACCOUNT_DEFER_RECONCILIATION")
    if not combined["combined_route"].eq("DEFER_PORTFOLIO_CONTEXT").all(): errors.append("COMBINED_DEFER_RECONCILIATION")
    if decision.get("status") != contract["acceptance"]["context_blocked_status"]: errors.append("EXPECTED_CONTEXT_BLOCK_STATUS")
    if decision.get("next_gate") != contract["acceptance"]["context_repair_next_gate"]: errors.append("CONTEXT_REPAIR_NEXT_GATE")
    if quality.get("status") != "PASS_STRUCTURE_WITH_CONTEXT_BLOCK": errors.append("QUALITY_STATUS")
    if quality.get("hard_failures") != []: errors.append("STRUCTURAL_FAILURES")
    if manifest.get("trade_authority") != TRADE_AUTHORITY: errors.append("MANIFEST_AUTHORITY")

    result = {"program_id": PROGRAM_ID, "status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors)),
              "security_count": len(combined), "account_security_count": len(account), "rule_row_count": len(rules),
              "context_gap_count": len(gaps), "trade_authority": TRADE_AUTHORITY}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        raise SystemExit("P4_1_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))


if __name__ == "__main__":
    main()
