#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output).resolve()

    batch = pd.read_csv(out / "HKCU_P2B_E2_R21_40_EVIDENCE_LEDGER.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    cumulative = pd.read_csv(out / "HKCU_P2B_E2_CUMULATIVE_EVIDENCE_LEDGER.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    dim = pd.read_csv(out / "HKCU_P2B_E2_CUMULATIVE_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str})
    openq = pd.read_csv(out / "HKCU_P2B_E2_CUMULATIVE_OPEN_RESEARCH_QUEUE.csv", dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(out / "HKCU_P2B_E2_CUMULATIVE_UNSTARTED_QUEUE.csv", dtype={"stock_code_5d": str})
    decision = read_json(out / "HKCU_P2B_E2_R21_40_DECISION.json")
    quality = read_json(out / "HKCU_P2B_E2_R21_40_QUALITY_REPORT.json")

    failures = []
    if len(batch) != 60:
        failures.append(f"BATCH_ROWS:{len(batch)}")
    if batch["security_id"].nunique() != 20:
        failures.append("BATCH_SECURITIES")
    if set(batch["p2a_overall_rank"].astype(int)) != set(range(21, 41)):
        failures.append("BATCH_RANKS")
    if batch.duplicated(["security_id", "research_dimension"]).any():
        failures.append("BATCH_DUPLICATE_KEYS")
    if set(batch["research_dimension"]) != DIMS:
        failures.append("BATCH_DIMENSIONS")
    if int(batch["evidence_status"].isin(["EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"]).sum()) != 54:
        failures.append("BATCH_COLLECTED")
    if int((batch["evidence_status"] == "EVIDENCE_COMPLETE").sum()) != 5:
        failures.append("BATCH_COMPLETE")
    if int((batch["evidence_status"] == "EVIDENCE_PARTIAL").sum()) != 49:
        failures.append("BATCH_PARTIAL")
    if int((batch["evidence_status"] == "RESEARCH_REQUIRED").sum()) != 6:
        failures.append("BATCH_RESEARCH_REQUIRED")
    if batch["score"].replace("", pd.NA).notna().any():
        failures.append("BATCH_SCORE_PRESENT")
    collected_batch = batch[batch["evidence_status"].isin(["EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"])]
    if not collected_batch["source_url"].str.startswith("https://www1.hkexnews.hk/").all():
        failures.append("NON_HKEX_COLLECTED_SOURCE")
    if (batch["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("BATCH_AUTHORITY")

    if len(cumulative) != 120 or cumulative["security_id"].nunique() != 40:
        failures.append("CUMULATIVE_LEDGER_SURFACE")
    if cumulative.duplicated(["security_id", "research_dimension"]).any():
        failures.append("CUMULATIVE_DUPLICATE_KEYS")
    if len(dim[dim["research_dimension"].isin(DIMS)]) != 231:
        failures.append("COMPANY_DIMENSION_231")
    company = dim[dim["research_dimension"].isin(DIMS)]
    if int((company["evidence_status"] == "EVIDENCE_COMPLETE").sum()) != 8:
        failures.append("CUMULATIVE_COMPLETE_8")
    if int(company["evidence_status"].isin(["EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"]).sum()) != 108:
        failures.append("CUMULATIVE_COLLECTED_108")
    if len(openq) != 223:
        failures.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 123:
        failures.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if company["score"].notna().any():
        failures.append("CUMULATIVE_SCORE_PRESENT")
    for frame, label in [(cumulative, "CUMULATIVE"), (openq, "OPEN"), (unstarted, "UNSTARTED")]:
        if "trade_authority" in frame.columns and (frame["trade_authority"] != TRADE_AUTHORITY).any():
            failures.append(label + "_AUTHORITY")

    earnings = batch[batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION"]
    complete_titles = " ".join(earnings.loc[earnings["evidence_status"] == "EVIDENCE_COMPLETE", "evidence_title"].astype(str)).upper()
    for token in ["PROFIT ALERT", "ESTIMATED RESULTS", "PROFIT INCREASE", "PROFIT WARNING"]:
        if token not in complete_titles:
            failures.append("DIRECT_EXPECTATION_EVIDENCE_GUARD:" + token)
    partial_earnings = earnings[earnings["evidence_status"] == "EVIDENCE_PARTIAL"]
    if partial_earnings["evidence_title"].str.contains("profit alert|profit warning|profit increase", case=False, regex=True).any():
        failures.append("DIRECT_EXPECTATION_MISCLASSIFIED_PARTIAL")

    if decision.get("status") != "PASS_P2B_E2_RANK21_40_BATCH":
        failures.append("DECISION_NOT_PASS")
    if quality.get("status") != "PASS":
        failures.append("QUALITY_NOT_PASS")
    if decision.get("trade_authority") != TRADE_AUTHORITY or quality.get("trade_authority") != TRADE_AUTHORITY:
        failures.append("JSON_AUTHORITY")
    if any(decision.get(k) != 0 for k in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]):
        failures.append("PROTECTED_MUTATION")

    print(json.dumps({
        "validator": "HKCU-P2B-E2-RANK21-40-INDEPENDENT",
        "status": "PASS" if not failures else "FAIL",
        "batch_rows": len(batch),
        "batch_collected": int(batch["evidence_status"].isin(["EVIDENCE_PARTIAL", "EVIDENCE_COMPLETE"]).sum()),
        "batch_complete": int((batch["evidence_status"] == "EVIDENCE_COMPLETE").sum()),
        "cumulative_covered_securities": cumulative["security_id"].nunique(),
        "cumulative_complete": int((company["evidence_status"] == "EVIDENCE_COMPLETE").sum()),
        "open_tasks": len(openq),
        "unstarted_tasks": len(unstarted),
        "hard_failures": failures,
        "trade_authority": TRADE_AUTHORITY,
    }, indent=2))
    if failures:
        raise SystemExit("P2B_E2_R21_40_VALIDATION_FAILED:" + ",".join(failures))


if __name__ == "__main__":
    main()
