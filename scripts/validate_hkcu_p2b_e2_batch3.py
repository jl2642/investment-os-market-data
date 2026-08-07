#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

EXPECTED_DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}
TRADE_AUTHORITY = "NONE"
DIRECT_CODES = {"03939", "02269", "02400", "02145", "02698", "02314", "00917", "09696", "09911"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(output: Path) -> list[str]:
    errors = []
    required = [
        "HKCU_P2B_E2_B3_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_B3_CUMULATIVE_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_B3_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_B3_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_B3_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_B3_DECISION.json",
        "HKCU_P2B_E2_B3_QUALITY_REPORT.json",
        "HKCU_P2B_E2_B3_MANIFEST.json",
    ]
    for name in required:
        if not (output / name).exists():
            errors.append("MISSING_OUTPUT:" + name)
    if errors:
        return errors

    batch = pd.read_csv(output / required[0], dtype={"stock_code_5d": str})
    ledger = pd.read_csv(output / required[1], dtype={"stock_code_5d": str})
    dim = pd.read_csv(output / required[2], dtype={"stock_code_5d": str})
    openq = pd.read_csv(output / required[3], dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(output / required[4], dtype={"stock_code_5d": str})
    decision = read_json(output / required[5])
    quality = read_json(output / required[6])
    manifest = read_json(output / required[7])

    if decision.get("status") != "PASS_P2B_E2_RANKS_41_60_BATCH":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")

    if len(batch) != 60 or batch["security_id"].nunique() != 20:
        errors.append("BATCH3_SHAPE")
    if set(batch["p2a_overall_rank"].astype(int)) != set(range(41, 61)):
        errors.append("BATCH3_RANK_SET")
    if set(batch["research_dimension"]) != EXPECTED_DIMS:
        errors.append("BATCH3_DIM_SET")
    if batch.duplicated(["security_id", "research_dimension"]).any():
        errors.append("BATCH3_DUPLICATE")
    if batch["score"].notna().any():
        errors.append("BATCH3_ALPHA_SCORE")
    counts3 = batch["evidence_status"].value_counts().to_dict()
    expected3 = {"EVIDENCE_COMPLETE": 9, "EVIDENCE_PARTIAL": 45, "RESEARCH_REQUIRED": 6}
    for status, count in expected3.items():
        if int(counts3.get(status, 0)) != count:
            errors.append(f"BATCH3_STATUS:{status}:{counts3.get(status,0)}")
    if int(batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 54:
        errors.append("BATCH3_COLLECTED")
    direct = set(
        batch.loc[
            (batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
            & (batch["evidence_status"] == "EVIDENCE_COMPLETE"),
            "stock_code_5d",
        ].astype(str).str.zfill(5)
    )
    if direct != DIRECT_CODES:
        errors.append("DIRECT_EXPECTATION_CODES")
    complete_titles = " ".join(
        batch.loc[
            (batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
            & (batch["evidence_status"] == "EVIDENCE_COMPLETE"),
            "evidence_title",
        ].astype(str).str.upper()
    )
    if not any(token in complete_titles for token in ["PROFIT ALERT", "RESULTS FORECAST"]):
        errors.append("DIRECT_EXPECTATION_TITLE_GUARD")

    if len(ledger) != 180 or ledger["security_id"].nunique() != 60:
        errors.append("CUMULATIVE_LEDGER_SHAPE")
    if set(ledger["p2a_overall_rank"].astype(int)) != set(range(1, 61)):
        errors.append("CUMULATIVE_RANK_SET")
    if ledger.duplicated(["security_id", "research_dimension"]).any():
        errors.append("CUMULATIVE_LEDGER_DUPLICATE")
    if set(ledger["research_dimension"]) != EXPECTED_DIMS:
        errors.append("CUMULATIVE_DIM_SET")
    if ledger["score"].notna().any():
        errors.append("LEDGER_ALPHA_SCORE")
    if int(ledger["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 160:
        errors.append("CUMULATIVE_COLLECTED")

    company = dim[dim["research_dimension"].isin(EXPECTED_DIMS)]
    if len(company) != 231:
        errors.append(f"COMPANY_ROWS:{len(company)}")
    counts = company["evidence_status"].value_counts().to_dict()
    expected_cum = {"EVIDENCE_COMPLETE": 17, "EVIDENCE_PARTIAL": 143, "RESEARCH_REQUIRED": 71}
    for status, count in expected_cum.items():
        if int(counts.get(status, 0)) != count:
            errors.append(f"CUM_STATUS:{status}:{counts.get(status,0)}")
    if company["score"].notna().any():
        errors.append("CUM_ALPHA_SCORE")
    if len(openq) != 214:
        errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 71:
        errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if not unstarted["evidence_status"].eq("RESEARCH_REQUIRED").all():
        errors.append("UNSTARTED_STATUS")

    if decision.get("cumulative_security_count_started") != 60:
        errors.append("DECISION_STARTED_COUNT")
    if decision.get("cumulative_evidence_rows") != 180:
        errors.append("DECISION_LEDGER_COUNT")
    if decision.get("cumulative_evidence_collected_rows") != 160:
        errors.append("DECISION_COLLECTED_COUNT")
    if decision.get("company_specific_open_tasks") != 214:
        errors.append("DECISION_OPEN_COUNT")
    if decision.get("company_specific_unstarted_tasks") != 71:
        errors.append("DECISION_UNSTARTED_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_FINAL_COMPANY_SPECIFIC_EVIDENCE_RANKS_61_77":
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
        raise SystemExit("P2B_E2_BATCH3_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_RANKS_41_60_VALIDATION")


if __name__ == "__main__":
    main()
