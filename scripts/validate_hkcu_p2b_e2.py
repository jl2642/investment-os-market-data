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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output).resolve()

    evidence = pd.read_csv(out / "HKCU_P2B_E2_COMPANY_EVIDENCE_INTAKE.csv", dtype={"stock_code_5d": str})
    dim = pd.read_csv(out / "HKCU_P2B_E2_DIMENSION_EVIDENCE.csv", dtype={"stock_code_5d": str})
    queue = pd.read_csv(out / "HKCU_P2B_E2_PRIMARY_RESEARCH_QUEUE.csv", dtype={"stock_code_5d": str})
    decision = read_json(out / "HKCU_P2B_E2_DECISION.json")
    quality = read_json(out / "HKCU_P2B_E2_QUALITY_REPORT.json")

    failures = []
    if len(evidence) != 77:
        failures.append(f"EVIDENCE_ROWS:{len(evidence)}")
    if evidence["security_id"].duplicated().any():
        failures.append("DUPLICATE_EVIDENCE_SECURITY")
    if len(dim) != 231:
        failures.append(f"DIMENSION_ROWS:{len(dim)}")
    if set(dim["research_dimension"].unique()) != DIMS:
        failures.append("DIMENSION_SET")
    counts = dim["research_dimension"].value_counts().to_dict()
    if any(int(counts.get(d, 0)) != 77 for d in DIMS):
        failures.append("DIMENSION_COUNT_PER_SECURITY")
    per_sec = dim.groupby("security_id")["research_dimension"].nunique()
    if len(per_sec) != 77 or not (per_sec == 3).all():
        failures.append("THREE_DIMENSIONS_PER_SECURITY")
    if "score" in dim.columns and dim["score"].notna().any():
        failures.append("UNSUPPORTED_SCORE_PRESENT")
    if (evidence["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("EVIDENCE_TRADE_AUTHORITY")
    if (dim["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("DIM_TRADE_AUTHORITY")
    if (queue["trade_authority"] != TRADE_AUTHORITY).any():
        failures.append("QUEUE_TRADE_AUTHORITY")
    if len(queue) != 231:
        failures.append(f"PRIMARY_QUEUE_ROWS:{len(queue)}")
    if int((queue["priority_bucket"] == "P1_TOP20").sum()) != 60:
        failures.append("TOP20_TASK_COUNT")
    rev = dim[dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION"]
    if not (rev["score_status"] == "NO_SCORE_TRAILING_GROWTH_NOT_REVISION").all():
        failures.append("REVISION_PROXY_GUARD")
    if not (evidence["primary_verification_required"].astype(str).str.lower().isin(["true", "1"])).all():
        failures.append("PRIMARY_VERIFICATION_GUARD")
    if decision.get("trade_authority") != TRADE_AUTHORITY or quality.get("trade_authority") != TRADE_AUTHORITY:
        failures.append("JSON_TRADE_AUTHORITY")
    if decision.get("candidate_pool_mutations") != 0 or decision.get("simulation_mutations") != 0 or decision.get("real_account_mutations") != 0 or decision.get("orders_created") != 0:
        failures.append("PROTECTED_MUTATION")
    if quality.get("status") != "PASS":
        failures.append("QUALITY_NOT_PASS")
    if decision.get("status") != "PASS_P2B_E2_SECONDARY_INTAKE_PRIMARY_REVIEW_REQUIRED":
        failures.append("DECISION_NOT_PASS")

    print(json.dumps({
        "validator": "HKCU-P2B-E2-INDEPENDENT",
        "status": "PASS" if not failures else "FAIL",
        "evidence_rows": len(evidence),
        "dimension_rows": len(dim),
        "queue_rows": len(queue),
        "profile_success_count": quality.get("profile_success_count"),
        "financial_indicator_success_count": quality.get("financial_indicator_success_count"),
        "dividend_event_available_count": quality.get("dividend_event_available_count"),
        "hard_failures": failures,
        "trade_authority": TRADE_AUTHORITY,
    }, indent=2))
    if failures:
        raise SystemExit("P2B_E2_VALIDATION_FAILED:" + ",".join(failures))


if __name__ == "__main__":
    main()
