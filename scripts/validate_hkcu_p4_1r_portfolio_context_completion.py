#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

PROGRAM_ID = "HKCU-P4-1R"
TRADE_AUTHORITY = "NONE"


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--repo-root", default="."); ap.add_argument("--output", required=True); args = ap.parse_args()
    root, out = Path(args.repo_root), Path(args.output)
    c = read_json(root / "config/hkcu_p4_1r_portfolio_context_completion_contract.json")
    d = read_json(out / "HKCU_P4_1R_DECISION.json"); q = read_json(out / "HKCU_P4_1R_QUALITY_REPORT.json"); m = read_json(out / "HKCU_P4_1R_MANIFEST.json")
    cand = pd.read_csv(out / "HKCU_P4_1R_CANDIDATE_CONTEXT.csv", dtype={"stock_code_5d": str, "a_share_code_6d": str}, keep_default_na=False)
    hold = pd.read_csv(out / "HKCU_P4_1R_ACCOUNT_HOLDING_CONTEXT.csv", keep_default_na=False)
    ctx = pd.read_csv(out / "HKCU_P4_1R_ACCOUNT_SECURITY_CONTEXT.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    gaps = pd.read_csv(out / "HKCU_P4_1R_RESIDUAL_GAPS.csv", keep_default_na=False)
    errors = []
    if d.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if d.get("status") not in {c["acceptance"]["pass_status"], c["acceptance"]["blocked_status"]}: errors.append("STATUS")
    if len(cand) != 70 or cand["security_id"].nunique() != 70: errors.append("CANDIDATE_CONTEXT")
    if len(hold) != 24: errors.append(f"HOLDING_CONTEXT:{len(hold)}")
    if len(ctx) != 140 or ctx.duplicated(["security_id", "account"]).any(): errors.append("ACCOUNT_SECURITY_CONTEXT")
    if set(ctx["account"]) != {"REAL", "SIMULATION"}: errors.append("ACCOUNT_SET")
    true_ah = cand[cand["true_ah_pair"].astype(str).str.lower().isin({"true", "1"})]
    if d.get("status") == c["acceptance"]["pass_status"]:
        if len(gaps) != 0: errors.append("PASS_WITH_RESIDUAL_GAPS")
        if not true_ah["a_share_code_6d"].astype(str).str.len().eq(6).all(): errors.append("PASS_WITH_UNMAPPED_AH")
        if not cand["economic_sector_industry"].astype(str).str.len().gt(0).all(): errors.append("PASS_WITH_MISSING_INDUSTRY")
        if not ctx["context_ready"].astype(str).str.lower().isin({"true", "1"}).all(): errors.append("PASS_WITH_NONREADY_CONTEXT")
        if d.get("next_gate") != c["acceptance"]["next_gate_on_pass"]: errors.append("PASS_NEXT_GATE")
    else:
        if len(gaps) == 0: errors.append("BLOCKED_WITHOUT_GAPS")
        if d.get("next_gate") is not None: errors.append("BLOCKED_NEXT_GATE")
    for frame, name in [(cand,"CAND"),(hold,"HOLD"),(ctx,"CTX")]:
        if "trade_authority" not in frame.columns or not frame["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append(name + "_AUTHORITY")
    if ctx["portfolio_mutation"].astype(str).str.lower().isin({"true","1"}).any(): errors.append("PORTFOLIO_MUTATION")
    if (pd.to_numeric(ctx["orders_created"], errors="coerce").fillna(0) != 0).any(): errors.append("ORDERS")
    for key in ["candidate_pool_mutations","simulation_mutations","real_account_mutations","portfolio_allocations","orders_created"]:
        if int(d.get(key, -1)) != 0: errors.append("DECISION_" + key.upper())
    for name, meta in m.get("files", {}).items():
        p = out / name
        if not p.exists() or sha256_file(p) != meta.get("sha256") or p.stat().st_size != int(meta.get("bytes", -1)): errors.append("MANIFEST_" + name)
    if m.get("trade_authority") != TRADE_AUTHORITY or q.get("trade_authority") != TRADE_AUTHORITY: errors.append("META_AUTHORITY")
    result = {"program_id":PROGRAM_ID,"status":"PASS" if not errors else "FAIL","errors":sorted(set(errors)),"candidate_context_count":len(cand),"holding_context_count":len(hold),"account_security_context_count":len(ctx),"residual_gap_count":len(gaps),"operational_status":d.get("status"),"trade_authority":TRADE_AUTHORITY}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if errors: raise SystemExit("P4_1R_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))

if __name__ == "__main__": main()
