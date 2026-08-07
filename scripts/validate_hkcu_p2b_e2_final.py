#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}
TRADE_AUTHORITY = "NONE"
DIRECT_CODES = {"01208", "02157", "03759", "06110", "03339"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(out: Path) -> list[str]:
    names = [
        "HKCU_P2B_E2_FINAL_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_FINAL_CUMULATIVE_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_FINAL_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_FINAL_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_FINAL_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_FINAL_DECISION.json",
        "HKCU_P2B_E2_FINAL_QUALITY_REPORT.json",
        "HKCU_P2B_E2_FINAL_MANIFEST.json",
    ]
    errors = ["MISSING_OUTPUT:" + n for n in names if not (out / n).exists()]
    if errors:
        return errors

    batch = pd.read_csv(out / names[0], dtype={"stock_code_5d": str})
    ledger = pd.read_csv(out / names[1], dtype={"stock_code_5d": str})
    dim = pd.read_csv(out / names[2], dtype={"stock_code_5d": str})
    openq = pd.read_csv(out / names[3], dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(out / names[4], dtype={"stock_code_5d": str})
    decision = read_json(out / names[5])
    quality = read_json(out / names[6])
    manifest = read_json(out / names[7])

    if decision.get("status") != "PASS_P2B_E2_ALL_77_FIRST_PASS_EVIDENCE":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")

    if len(batch) != 51 or batch["security_id"].nunique() != 17:
        errors.append("FINAL_BATCH_SHAPE")
    if set(batch["p2a_overall_rank"].astype(int)) != set(range(61, 78)):
        errors.append("FINAL_BATCH_RANK_SET")
    if set(batch["research_dimension"]) != DIMS:
        errors.append("FINAL_BATCH_DIM_SET")
    if batch.duplicated(["security_id", "research_dimension"]).any():
        errors.append("FINAL_BATCH_DUPLICATE")
    if batch["score"].notna().any():
        errors.append("FINAL_BATCH_ALPHA_SCORE")
    batch_counts = batch["evidence_status"].value_counts().to_dict()
    for status, count in {"EVIDENCE_COMPLETE": 5, "EVIDENCE_PARTIAL": 42, "RESEARCH_REQUIRED": 4}.items():
        if int(batch_counts.get(status, 0)) != count:
            errors.append(f"FINAL_BATCH_STATUS:{status}:{batch_counts.get(status,0)}")
    if int(batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 47:
        errors.append("FINAL_BATCH_COLLECTED")
    collected = batch[batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"])]
    if not collected["source_url"].str.startswith("https://www1.hkexnews.hk/").all():
        errors.append("NON_HKEX_COLLECTED_SOURCE")
    if (batch["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("FINAL_BATCH_AUTHORITY")

    direct = set(
        batch.loc[
            (batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
            & (batch["evidence_status"] == "EVIDENCE_COMPLETE"),
            "stock_code_5d",
        ].astype(str).str.zfill(5)
    )
    if direct != DIRECT_CODES:
        errors.append("DIRECT_EXPECTATION_CODES")
    topsports = batch[
        (batch["stock_code_5d"].astype(str).str.zfill(5) == "06110")
        & (batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
    ]
    if len(topsports) != 1:
        errors.append("TOPSPORTS_ROW")
    else:
        text = (str(topsports.iloc[0]["evidence_title"]) + " " + str(topsports.iloc[0]["evidence_summary"])).lower()
        if not all(token in text for token in ["nike", "significant", "22%"]):
            errors.append("TOPSPORTS_FORWARD_IMPACT")

    if len(ledger) != 231 or ledger["security_id"].nunique() != 77:
        errors.append("CUMULATIVE_LEDGER_SHAPE")
    if set(ledger["p2a_overall_rank"].astype(int)) != set(range(1, 78)):
        errors.append("CUMULATIVE_RANK_SET")
    if ledger.duplicated(["security_id", "research_dimension"]).any():
        errors.append("CUMULATIVE_LEDGER_DUPLICATE")
    if set(ledger["research_dimension"]) != DIMS:
        errors.append("CUMULATIVE_DIM_SET")
    if ledger["score"].notna().any():
        errors.append("LEDGER_ALPHA_SCORE")
    if int(ledger["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 207:
        errors.append("CUMULATIVE_COLLECTED")

    company = dim[dim["research_dimension"].isin(DIMS)]
    if len(company) != 231:
        errors.append(f"COMPANY_ROWS:{len(company)}")
    counts = company["evidence_status"].value_counts().to_dict()
    for status, count in {"EVIDENCE_COMPLETE": 22, "EVIDENCE_PARTIAL": 185, "RESEARCH_REQUIRED": 24}.items():
        if int(counts.get(status, 0)) != count:
            errors.append(f"CUM_STATUS:{status}:{counts.get(status,0)}")
    if company["score"].notna().any():
        errors.append("CUM_ALPHA_SCORE")
    if company["security_id"].nunique() != 77:
        errors.append("ALL_77_NOT_PRESENT")
    if len(openq) != 209:
        errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 24:
        errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if not unstarted["evidence_status"].eq("RESEARCH_REQUIRED").all():
        errors.append("UNSTARTED_STATUS")

    expected_decision = {
        "cumulative_security_count_started": 77,
        "cumulative_evidence_rows": 231,
        "cumulative_evidence_collected_rows": 207,
        "cumulative_evidence_complete_rows": 22,
        "cumulative_evidence_partial_rows": 185,
        "company_specific_open_tasks": 209,
        "company_specific_unstarted_tasks": 24,
    }
    for key, expected in expected_decision.items():
        if int(decision.get(key, -1)) != expected:
            errors.append("DECISION_" + key)
    if decision.get("all_77_securities_started") is not True:
        errors.append("ALL_77_STARTED_FLAG")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E3_EVIDENCE_SYNTHESIS_AND_GRADUATION_READINESS":
        errors.append("NEXT_GATE")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0:
            errors.append("PROTECTED_MUTATION:" + key)
    for payload in [decision, quality, manifest]:
        if payload.get("trade_authority") != TRADE_AUTHORITY:
            errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    errors = validate(Path(args.output))
    if errors:
        raise SystemExit("P2B_E2_FINAL_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_ALL_77_FIRST_PASS_EVIDENCE_VALIDATION")


if __name__ == "__main__":
    main()
