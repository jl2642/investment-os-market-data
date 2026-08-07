#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def run_baseline(repo_root: Path, temp: Path):
    temp.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(repo_root / "pipeline/hkcu_p2b_build_research_baseline.py"),
        "--repo-root", str(repo_root),
        "--output", str(temp),
    ]
    subprocess.run(cmd, check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    root = Path(args.repo_root).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    contract = read_json(root / "config/hkcu_p2b_e1_evidence_contract.json")
    market = read_json(root / "evidence/hkcu_p2b/HKCU_P2B_COMMON_MARKET_RULES_20260807.json")
    ah = pd.read_csv(root / "evidence/hkcu_p2b/HKCU_P2B_AH_PAIR_REGISTRY_20260807.csv", dtype={"a_code": str, "h_code": str, "hk_code": str})

    baseline_dir = out / "_baseline"
    run_baseline(root, baseline_dir)
    dim = pd.read_csv(baseline_dir / "HKCU_P2B_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str})
    sec = pd.read_csv(baseline_dir / "HKCU_P2B_SECURITY_TYPE_MATRIX.csv", dtype={"stock_code_5d": str})

    failures = []
    expected = contract["expected_counts"]
    if len(sec) != int(expected["accepted_security_count"]):
        failures.append(f"SECURITY_COUNT:{len(sec)}")
    if len(ah) != int(expected["ah_leads_to_resolve"]):
        failures.append(f"AH_REGISTRY_COUNT:{len(ah)}")
    if int((ah["pair_status"] == "TRUE_AH_PAIR").sum()) != int(expected["expected_true_ah_pairs"]):
        failures.append("AH_TRUE_PAIR_COUNT")
    if int((ah["pair_status"] != "TRUE_AH_PAIR").sum()) != int(expected["expected_not_applicable_ah_leads"]):
        failures.append("AH_NOT_APPLICABLE_COUNT")
    if ah["security_id"].duplicated().any():
        failures.append("AH_DUPLICATE_SECURITY")

    tx_mask = dim["research_dimension"].eq("TRANSACTION_COST_TAX")
    if int(tx_mask.sum()) != int(expected["transaction_tax_rows_to_close"]):
        failures.append(f"TX_ROW_COUNT:{int(tx_mask.sum())}")
    dim.loc[tx_mask, "evidence_status"] = "EVIDENCE_COMPLETE"
    dim.loc[tx_mask, "evidence_count"] = len(market["rules"])
    dim.loc[tx_mask, "score_status"] = "EVIDENCE_COMPLETE_NO_ALPHA_SCORE"
    dim.loc[tx_mask, "next_action"] = "EXECUTION_MODEL_READY_BROKERAGE_VARIABLE"
    dim.loc[tx_mask, "applicability_reason"] = "COMMON_SOUTBOUND_MARKET_AND_TAX_RULES_EVIDENCED"

    pair_map = ah.set_index("security_id").to_dict("index")
    ah_mask = dim["research_dimension"].eq("A_H_RELATIVE_VALUATION")
    ah_rows = dim.loc[ah_mask].copy()
    leads = set(ah["security_id"])
    baseline_leads = set(ah_rows.loc[ah_rows["applicability"].eq("POTENTIALLY_APPLICABLE"), "security_id"])
    if leads != baseline_leads:
        failures.append("AH_LEAD_SET_MISMATCH")

    for idx, row in dim.loc[ah_mask].iterrows():
        sid = row["security_id"]
        if sid not in pair_map:
            continue
        rec = pair_map[sid]
        dim.at[idx, "evidence_status"] = "EVIDENCE_COMPLETE"
        dim.at[idx, "evidence_count"] = 1
        dim.at[idx, "score_status"] = "EVIDENCE_COMPLETE_NO_ALPHA_SCORE"
        if rec["pair_status"] == "TRUE_AH_PAIR":
            dim.at[idx, "applicability"] = "APPLICABLE"
            dim.at[idx, "applicability_reason"] = f"SAME_ISSUER_AH_PAIR_CONFIRMED:{rec['a_exchange']}:{rec['a_code']}"
            dim.at[idx, "next_action"] = "A_H_RELATIVE_VALUATION_DATA_READY_FOR_PRICE_FX_STAGE"
        else:
            dim.at[idx, "applicability"] = "NOT_APPLICABLE"
            dim.at[idx, "applicability_reason"] = rec["pair_status"]
            dim.at[idx, "next_action"] = "NO_A_H_RELATIVE_VALUATION_REQUIRED"

    remaining = dim[
        dim["research_dimension"].isin(contract["remaining_company_specific_dimensions"])
        & dim["evidence_status"].eq("RESEARCH_REQUIRED")
    ].copy()
    remaining = remaining.sort_values(["p2a_overall_rank", "dimension_order", "security_id"]).reset_index(drop=True)
    remaining.insert(0, "queue_rank", range(1, len(remaining) + 1))

    ah_out = ah.copy()
    ah_out["evidence_status"] = "EVIDENCE_COMPLETE"
    ah_out["trade_authority"] = TRADE_AUTHORITY

    decision = {
        "program_id":"HKCU-P2B-E1",
        "phase":"P2B_EVIDENCE_COLLECTION_E1",
        "status":"PASS_P2B_E1_COMMON_AH_EVIDENCE" if not failures else "FAIL_P2B_E1",
        "accepted_security_count":int(len(sec)),
        "transaction_tax_tasks_completed":int(tx_mask.sum()),
        "ah_leads_resolved":int(len(ah)),
        "true_ah_pairs":int((ah["pair_status"]=="TRUE_AH_PAIR").sum()),
        "not_applicable_ah_leads":int((ah["pair_status"]!="TRUE_AH_PAIR").sum()),
        "completed_evidence_tasks":int(tx_mask.sum()+len(ah)),
        "remaining_company_specific_tasks":int(len(remaining)),
        "remaining_dimensions":contract["remaining_company_specific_dimensions"],
        "hard_failures":failures,
        "next_gate":contract["next_gate"] if not failures else None,
        "candidate_pool_mutations":0,
        "simulation_mutations":0,
        "real_account_mutations":0,
        "orders_created":0,
        "trade_authority":TRADE_AUTHORITY,
    }
    quality = {
        "program_id":"HKCU-P2B-E1",
        "status":"PASS" if not failures else "FAIL",
        "hard_failures":failures,
        "security_count":int(len(sec)),
        "transaction_tax_complete_count":int((dim["research_dimension"].eq("TRANSACTION_COST_TAX") & dim["evidence_status"].eq("EVIDENCE_COMPLETE")).sum()),
        "ah_complete_count":int((dim["research_dimension"].eq("A_H_RELATIVE_VALUATION") & dim["evidence_status"].eq("EVIDENCE_COMPLETE")).sum()),
        "remaining_research_required_by_dimension":remaining["research_dimension"].value_counts().to_dict(),
        "remaining_queue_count":int(len(remaining)),
        "market_rule_evidence_ids":[r["evidence_id"] for r in market["rules"]],
        "trade_authority":TRADE_AUTHORITY,
    }

    dim.to_csv(out/"HKCU_P2B_E1_DIMENSION_MATRIX.csv", index=False)
    ah_out.to_csv(out/"HKCU_P2B_E1_AH_PAIR_REGISTRY.csv", index=False)
    remaining.to_csv(out/"HKCU_P2B_E1_REMAINING_RESEARCH_QUEUE.csv", index=False)
    (out/"HKCU_P2B_E1_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    (out/"HKCU_P2B_E1_QUALITY_REPORT.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "program_id":"HKCU-P2B-E1",
        "inputs":{
            "config/hkcu_p2b_e1_evidence_contract.json":sha256_file(root/"config/hkcu_p2b_e1_evidence_contract.json"),
            "evidence/hkcu_p2b/HKCU_P2B_COMMON_MARKET_RULES_20260807.json":sha256_file(root/"evidence/hkcu_p2b/HKCU_P2B_COMMON_MARKET_RULES_20260807.json"),
            "evidence/hkcu_p2b/HKCU_P2B_AH_PAIR_REGISTRY_20260807.csv":sha256_file(root/"evidence/hkcu_p2b/HKCU_P2B_AH_PAIR_REGISTRY_20260807.csv"),
        },
        "outputs":{
            name:sha256_file(out/name) for name in [
                "HKCU_P2B_E1_DIMENSION_MATRIX.csv","HKCU_P2B_E1_AH_PAIR_REGISTRY.csv",
                "HKCU_P2B_E1_REMAINING_RESEARCH_QUEUE.csv","HKCU_P2B_E1_DECISION.json",
                "HKCU_P2B_E1_QUALITY_REPORT.json"
            ]
        },
        "trade_authority":TRADE_AUTHORITY,
    }
    (out/"HKCU_P2B_E1_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if failures:
        raise SystemExit("P2B_E1_FAILED:" + ",".join(failures))

if __name__ == "__main__":
    main()
