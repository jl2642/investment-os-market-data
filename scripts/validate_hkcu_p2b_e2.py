#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
EXPECTED_DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(output: Path) -> list[str]:
    errors = []
    names = [
        "HKCU_P2B_E2_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_DECISION.json",
        "HKCU_P2B_E2_QUALITY_REPORT.json",
        "HKCU_P2B_E2_MANIFEST.json",
    ]
    for name in names:
        if not (output / name).exists():
            errors.append("MISSING_OUTPUT:" + name)
    if errors:
        return errors

    ledger = pd.read_csv(output / "HKCU_P2B_E2_EVIDENCE_LEDGER.csv", dtype={"stock_code_5d": str})
    dim = pd.read_csv(output / "HKCU_P2B_E2_DIMENSION_MATRIX.csv", dtype={"stock_code_5d": str})
    openq = pd.read_csv(output / "HKCU_P2B_E2_OPEN_RESEARCH_QUEUE.csv", dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(output / "HKCU_P2B_E2_UNSTARTED_QUEUE.csv", dtype={"stock_code_5d": str})
    decision = read_json(output / "HKCU_P2B_E2_DECISION.json")
    quality = read_json(output / "HKCU_P2B_E2_QUALITY_REPORT.json")
    manifest = read_json(output / "HKCU_P2B_E2_MANIFEST.json")

    if decision.get("status") != "PASS_P2B_E2_TOP_QUARTILE_BATCH": errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"): errors.append("QUALITY_STATUS")
    if len(ledger) != 60: errors.append(f"LEDGER_ROWS:{len(ledger)}")
    if ledger["security_id"].nunique() != 20: errors.append("LEDGER_SECURITIES")
    if set(ledger["p2a_overall_rank"].astype(int)) != set(range(1, 21)): errors.append("LEDGER_RANKS")
    if set(ledger["research_dimension"]) != EXPECTED_DIMS: errors.append("LEDGER_DIMS")
    if ledger.duplicated(["security_id", "research_dimension"]).any(): errors.append("LEDGER_DUPLICATE")
    if ledger["score"].notna().any(): errors.append("LEDGER_ALPHA_SCORE")
    if decision.get("batch_security_count") != 20 or decision.get("batch_evidence_rows") != 60: errors.append("DECISION_BATCH_COUNTS")
    if decision.get("evidence_complete_rows") != 3: errors.append("COMPLETE_COUNT")
    if decision.get("evidence_partial_rows") != 51: errors.append("PARTIAL_COUNT")
    if decision.get("evidence_collected_rows") != 54: errors.append("COLLECTED_COUNT")

    company = dim[dim["research_dimension"].isin(EXPECTED_DIMS)]
    if len(company) != 231: errors.append(f"COMPANY_ROWS:{len(company)}")
    if company["score"].notna().any(): errors.append("ALPHA_SCORE_PRESENT")
    if len(openq) != 228: errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 177: errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if set(openq["research_dimension"]) != EXPECTED_DIMS: errors.append("OPEN_QUEUE_DIMS")
    if set(unstarted["research_dimension"]) != EXPECTED_DIMS: errors.append("UNSTARTED_QUEUE_DIMS")
    if not unstarted["evidence_status"].eq("RESEARCH_REQUIRED").all(): errors.append("UNSTARTED_STATUS")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_CONTINUE_COMPANY_SPECIFIC_EVIDENCE": errors.append("NEXT_GATE")
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
        raise SystemExit("P2B_E2_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_TOP_QUARTILE_VALIDATION")


if __name__ == "__main__":
    main()
