#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

EXPECTED_DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}
TRADE_AUTHORITY = "NONE"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(output: Path) -> list[str]:
    errors = []
    required = [
        "HKCU_P2B_E2_B2_CUMULATIVE_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_B2_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_B2_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_B2_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_B2_DECISION.json",
        "HKCU_P2B_E2_B2_QUALITY_REPORT.json",
        "HKCU_P2B_E2_B2_MANIFEST.json",
    ]
    for name in required:
        if not (output / name).exists():
            errors.append("MISSING_OUTPUT:" + name)
    if errors:
        return errors

    ledger = pd.read_csv(output / required[0], dtype={"stock_code_5d": str})
    dim = pd.read_csv(output / required[1], dtype={"stock_code_5d": str})
    openq = pd.read_csv(output / required[2], dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(output / required[3], dtype={"stock_code_5d": str})
    decision = read_json(output / required[4])
    quality = read_json(output / required[5])
    manifest = read_json(output / required[6])

    if decision.get("status") != "PASS_P2B_E2_RANKS_21_40_BATCH": errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"): errors.append("QUALITY_STATUS")
    if len(ledger) != 120: errors.append(f"CUMULATIVE_LEDGER_ROWS:{len(ledger)}")
    if ledger["security_id"].nunique() != 40: errors.append(f"STARTED_SECURITY_COUNT:{ledger['security_id'].nunique()}")
    if ledger.duplicated(["security_id", "research_dimension"]).any(): errors.append("CUMULATIVE_LEDGER_DUPLICATE")
    if set(ledger["p2a_overall_rank"].astype(int)) != set(range(1, 41)): errors.append("CUMULATIVE_RANK_SET")
    if set(ledger["research_dimension"]) != EXPECTED_DIMS: errors.append("CUMULATIVE_DIM_SET")
    if ledger["score"].notna().any(): errors.append("LEDGER_ALPHA_SCORE")

    batch2 = ledger[ledger["p2a_overall_rank"].astype(int).between(21, 40)]
    if len(batch2) != 60 or batch2["security_id"].nunique() != 20: errors.append("BATCH2_SHAPE")
    b2_counts = batch2["evidence_status"].value_counts().to_dict()
    expected_b2 = {"EVIDENCE_COMPLETE": 5, "EVIDENCE_PARTIAL": 47, "RESEARCH_REQUIRED": 8}
    for status, count in expected_b2.items():
        if int(b2_counts.get(status, 0)) != count: errors.append(f"BATCH2_STATUS:{status}:{b2_counts.get(status,0)}")
    if int(batch2["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 52:
        errors.append("BATCH2_COLLECTED_COUNT")

    company = dim[dim["research_dimension"].isin(EXPECTED_DIMS)]
    if len(company) != 231: errors.append(f"COMPANY_ROWS:{len(company)}")
    counts = company["evidence_status"].value_counts().to_dict()
    expected_cum = {"EVIDENCE_COMPLETE": 8, "EVIDENCE_PARTIAL": 98, "RESEARCH_REQUIRED": 125}
    for status, count in expected_cum.items():
        if int(counts.get(status, 0)) != count: errors.append(f"CUM_STATUS:{status}:{counts.get(status,0)}")
    if company["score"].notna().any(): errors.append("CUM_ALPHA_SCORE")
    if len(openq) != 223: errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 125: errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if not unstarted["evidence_status"].eq("RESEARCH_REQUIRED").all(): errors.append("UNSTARTED_STATUS")
    if set(openq["research_dimension"]) != EXPECTED_DIMS: errors.append("OPEN_DIMS")
    if set(unstarted["research_dimension"]) != EXPECTED_DIMS: errors.append("UNSTARTED_DIMS")

    direct_codes = set(batch2[batch2["evidence_status"] == "EVIDENCE_COMPLETE"]["stock_code_5d"].astype(str).str.zfill(5))
    if direct_codes != {"03698", "09636", "06127", "06181", "06066"}:
        errors.append("DIRECT_EXPECTATION_CODES")
    if decision.get("cumulative_security_count_started") != 40: errors.append("DECISION_STARTED_COUNT")
    if decision.get("cumulative_evidence_rows") != 120: errors.append("DECISION_LEDGER_COUNT")
    if decision.get("cumulative_evidence_collected_rows") != 106: errors.append("DECISION_COLLECTED_COUNT")
    if decision.get("company_specific_open_tasks") != 223: errors.append("DECISION_OPEN_COUNT")
    if decision.get("company_specific_unstarted_tasks") != 125: errors.append("DECISION_UNSTARTED_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_CONTINUE_COMPANY_SPECIFIC_EVIDENCE_RANKS_41_60": errors.append("NEXT_GATE")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append("PROTECTED_MUTATION:" + key)
    for payload in [decision, quality, manifest]:
        if payload.get("trade_authority") != TRADE_AUTHORITY: errors.append("TRADE_AUTHORITY")
    return sorted(set(errors))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    errors = validate(Path(args.output))
    if errors:
        raise SystemExit("P2B_E2_BATCH2_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_RANKS_21_40_VALIDATION")


if __name__ == "__main__":
    main()
