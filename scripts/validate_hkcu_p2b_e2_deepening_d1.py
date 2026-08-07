#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
EXPECTED_CODES = {
    "00941", "00388", "02388", "00440", "01997", "09992", "02666", "00288", "02356", "00003", "00762", "03968", "06127", "03988", "01398", "00066", "00939", "00917", "02331", "00788", "00371", "03328", "02799"
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(out: Path) -> list[str]:
    names = [
        "HKCU_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURES.csv",
        "HKCU_P2B_E2_D1_CURRENT_EVIDENCE_LEDGER.csv",
        "HKCU_P2B_E2_D1_DIMENSION_MATRIX.csv",
        "HKCU_P2B_E2_D1_OPEN_RESEARCH_QUEUE.csv",
        "HKCU_P2B_E2_D1_UNSTARTED_QUEUE.csv",
        "HKCU_P2B_E2_D1_DECISION.json",
        "HKCU_P2B_E2_D1_QUALITY_REPORT.json",
        "HKCU_P2B_E2_D1_MANIFEST.json",
    ]
    errors = ["MISSING_OUTPUT:" + x for x in names if not (out / x).exists()]
    if errors:
        return errors

    closure = pd.read_csv(out / names[0], dtype={"stock_code_5d": str}, keep_default_na=False)
    ledger = pd.read_csv(out / names[1], dtype={"stock_code_5d": str}, keep_default_na=False)
    dim = pd.read_csv(out / names[2], dtype={"stock_code_5d": str})
    openq = pd.read_csv(out / names[3], dtype={"stock_code_5d": str})
    unstarted = pd.read_csv(out / names[4], dtype={"stock_code_5d": str})
    decision = read_json(out / names[5])
    quality = read_json(out / names[6])
    manifest = read_json(out / names[7])

    if len(closure) != 23 or closure["security_id"].nunique() != 23:
        errors.append("CLOSURE_SHAPE")
    codes = set(closure["stock_code_5d"].astype(str).str.zfill(5))
    if codes != EXPECTED_CODES:
        errors.append("CLOSURE_CODE_SET")
    if not closure["research_dimension"].eq("CATALYST").all():
        errors.append("CLOSURE_DIMENSION")
    if not closure["prior_status"].eq("RESEARCH_REQUIRED").all():
        errors.append("CLOSURE_PRIOR_STATUS")
    if not closure["closure_status"].eq("EVIDENCE_COMPLETE").all():
        errors.append("CLOSURE_STATUS")
    if not closure["catalyst_outcome"].eq("NO_QUALIFYING_ACTIVE_CATALYST").all():
        errors.append("CLOSURE_FINDING")
    if not closure["source_url"].str.startswith("https://www1.hkexnews.hk/").all():
        errors.append("CLOSURE_SOURCE")
    if not closure["directional_signal"].eq("NONE").all():
        errors.append("CLOSURE_DIRECTION")
    if closure["alpha_score"].replace("", pd.NA).notna().any():
        errors.append("CLOSURE_ALPHA_SCORE")
    if (closure["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("CLOSURE_AUTHORITY")

    if len(ledger) != 231 or ledger.duplicated(["security_id", "research_dimension"]).any():
        errors.append("CURRENT_LEDGER_SHAPE")
    company = dim[dim["research_dimension"].isin(["GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"])]
    if len(company) != 231 or company["security_id"].nunique() != 77:
        errors.append("DIMENSION_MATRIX_SHAPE")
    counts = company["evidence_status"].value_counts().to_dict()
    if int(counts.get("EVIDENCE_COMPLETE", 0)) != 45:
        errors.append("COMPLETE_COUNT")
    if int(counts.get("EVIDENCE_PARTIAL", 0)) != 186:
        errors.append("PARTIAL_COUNT")
    if int(counts.get("RESEARCH_REQUIRED", 0)) != 0:
        errors.append("RESEARCH_REQUIRED_NOT_ZERO")
    if company["score"].notna().any():
        errors.append("ALPHA_SCORE_PRESENT")
    if len(openq) != 186:
        errors.append(f"OPEN_QUEUE:{len(openq)}")
    if len(unstarted) != 0:
        errors.append(f"UNSTARTED_QUEUE:{len(unstarted)}")
    if not openq["evidence_status"].eq("EVIDENCE_PARTIAL").all():
        errors.append("OPEN_QUEUE_NOT_ALL_PARTIAL")

    closed_dim = company[
        (company["research_dimension"] == "CATALYST")
        & (company["security_id"].isin(set(closure["security_id"])))
    ]
    if len(closed_dim) != 23 or not closed_dim["evidence_status"].eq("EVIDENCE_COMPLETE").all():
        errors.append("CLOSURE_NOT_APPLIED")
    if not closed_dim["score_status"].eq("NEGATIVE_CATALYST_FINDING_NO_ALPHA_SCORE").all():
        errors.append("NEGATIVE_SCORE_STATUS")

    if decision.get("status") != "PASS_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURE":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")
    expected_decision = {
        "negative_catalyst_closure_count": 23,
        "company_specific_complete_tasks": 45,
        "company_specific_partial_tasks": 186,
        "company_specific_research_required_tasks": 0,
        "company_specific_open_tasks": 186,
        "company_specific_unstarted_tasks": 0,
    }
    for key, value in expected_decision.items():
        if int(decision.get(key, -1)) != value:
            errors.append("DECISION_" + key)
    if decision.get("negative_finding_is_not_bearish_score") is not True:
        errors.append("NEGATIVE_FINDING_SEMANTICS")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_PARTIAL_EVIDENCE_DEEPENING":
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
        raise SystemExit("P2B_E2_D1_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_D1_NEGATIVE_CATALYST_CLOSURE_VALIDATION")


if __name__ == "__main__":
    main()
