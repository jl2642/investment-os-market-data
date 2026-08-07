#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

EXPECTED_DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}
DIRECT_CODES = {"01208", "02157", "03759", "02313", "03339"}
TRADE_AUTHORITY = "NONE"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(output: Path) -> list[str]:
    errors = []
    required = [
        "HKCU_P2B_E2_B4_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_B4_CUMULATIVE_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_B4_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_B4_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_B4_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_B4_DECISION.json",
        "HKCU_P2B_E2_B4_QUALITY_REPORT.json",
        "HKCU_P2B_E2_B4_MANIFEST.json",
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

    if decision.get("status") != "PASS_P2B_E2_RANKS_61_77_BATCH":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")

    if len(batch) != 51 or batch["security_id"].nunique() != 17:
        errors.append("BATCH4_SHAPE")
    if set(batch["p2a_overall_rank"].astype(int)) != set(range(61, 78)):
        errors.append("BATCH4_RANK_SET")
    if set(batch["research_dimension"]) != EXPECTED_DIMS:
        errors.append("BATCH4_DIM_SET")
    if batch.duplicated(["security_id", "research_dimension"]).any():
        errors.append("BATCH4_DUPLICATE")
    if batch["score"].notna().any():
        errors.append("BATCH4_ALPHA_SCORE")
    counts4 = batch["evidence_status"].value_counts().to_dict()
    expected4 = {"EVIDENCE_COMPLETE": 5, "EVIDENCE_PARTIAL": 43, "RESEARCH_REQUIRED": 3}
    for status, count in expected4.items():
        if int(counts4.get(status, 0)) != count:
            errors.append(f"BATCH4_STATUS:{status}:{counts4.get(status,0)}")
    if int(batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 48:
        errors.append("BATCH4_COLLECTED")

    direct_rows = batch[
        (batch["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
        & (batch["evidence_status"] == "EVIDENCE_COMPLETE")
    ]
    direct = set(direct_rows["stock_code_5d"].astype(str).str.zfill(5))
    if direct != DIRECT_CODES:
        errors.append("DIRECT_EXPECTATION_CODES")
    if not direct_rows["evidence_title"].str.contains("profit|estimate|forecast", case=False, regex=True).all():
        errors.append("DIRECT_EXPECTATION_TITLE_GUARD")

    ordinary_complete = direct_rows[~direct_rows["evidence_title"].str.contains("profit|estimate|forecast", case=False, regex=True)]
    if len(ordinary_complete):
        errors.append("ORDINARY_RESULTS_MASQUERADE")

    dates = pd.to_datetime(batch["evidence_date"], errors="coerce")
    if dates.isna().any() or (dates > pd.Timestamp("2026-08-07")).any():
        errors.append("EVIDENCE_DATE_POLICY")
    collected = batch[batch["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"])]
    if not collected["source_url"].astype(str).str.startswith("https://www1.hkexnews.hk/").all():
        errors.append("PRIMARY_SOURCE_POLICY")

    if len(ledger) != 231 or ledger["security_id"].nunique() != 77:
        errors.append("CUMULATIVE_LEDGER_SHAPE")
    if set(ledger["p2a_overall_rank"].astype(int)) != set(range(1, 78)):
        errors.append("CUMULATIVE_RANK_SET")
    if ledger.duplicated(["security_id", "research_dimension"]).any():
        errors.append("CUMULATIVE_LEDGER_DUPLICATE")
    if set(ledger["research_dimension"]) != EXPECTED_DIMS:
        errors.append("CUMULATIVE_DIM_SET")
    if ledger["score"].notna().any():
        errors.append("LEDGER_ALPHA_SCORE")
    if int(ledger["evidence_status"].isin(["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]).sum()) != 208:
        errors.append("CUMULATIVE_COLLECTED")

    company = dim[dim["research_dimension"].isin(EXPECTED_DIMS)]
    if len(company) != 231:
        errors.append(f"COMPANY_ROWS:{len(company)}")
    counts = company["evidence_status"].value_counts().to_dict()
    expected_cum = {"EVIDENCE_COMPLETE": 22, "EVIDENCE_PARTIAL": 186, "RESEARCH_REQUIRED": 23}
    for status, count in expected_cum.items():
        if int(counts.get(status, 0)) != count:
            errors.append(f"CUM_STATUS:{status}:{counts.get(status,0)}")
    if company["score"].notna().any():
        errors.append("CUM_ALPHA_SCORE")
    if len(openq) != 209:
        errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 23:
        errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if not unstarted["evidence_status"].eq("RESEARCH_REQUIRED").all():
        errors.append("UNSTARTED_STATUS")

    if decision.get("cumulative_security_count_started") != 77 or decision.get("first_pass_company_coverage_complete") is not True:
        errors.append("FIRST_PASS_COVERAGE")
    if decision.get("cumulative_evidence_rows") != 231:
        errors.append("DECISION_LEDGER_COUNT")
    if decision.get("cumulative_evidence_collected_rows") != 208:
        errors.append("DECISION_COLLECTED_COUNT")
    if decision.get("company_specific_open_tasks") != 209:
        errors.append("DECISION_OPEN_COUNT")
    if decision.get("company_specific_unstarted_tasks") != 23:
        errors.append("DECISION_UNSTARTED_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_COMPANY_EVIDENCE_DEEPENING":
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
        raise SystemExit("P2B_E2_BATCH4_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_RANKS_61_77_VALIDATION")


if __name__ == "__main__":
    main()
