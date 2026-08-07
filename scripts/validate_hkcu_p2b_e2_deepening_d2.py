#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
DIMS = {"GOVERNANCE_VALUE_TRAP", "EARNINGS_EXPECTATION_REVISION", "CATALYST"}
READINESS = {"READY_FOR_P2B_SYNTHESIS", "READY_WITH_CONFIDENCE_CAP", "TARGETED_DEEPENING_REQUIRED"}
SUFFICIENCY = {"SUFFICIENT_FOR_PRELIMINARY_DECISION", "LIMITED_CONFIDENCE", "TARGETED_DEEPENING_REQUIRED"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(out: Path) -> list[str]:
    names = [
        "HKCU_P2B_E2_D2_TOP20_PARTIAL_SYNTHESIS.csv",
        "HKCU_P2B_E2_D2_TOP20_SECURITY_READINESS.csv",
        "HKCU_P2B_E2_D2_TOP20_BLOCKER_QUEUE.csv",
        "HKCU_P2B_E2_D2_DECISION.json",
        "HKCU_P2B_E2_D2_QUALITY_REPORT.json",
        "HKCU_P2B_E2_D2_MANIFEST.json",
    ]
    errors = ["MISSING_OUTPUT:" + x for x in names if not (out / x).exists()]
    if errors:
        return errors

    syn = pd.read_csv(out / names[0], dtype={"stock_code_5d": str}, keep_default_na=False)
    sec = pd.read_csv(out / names[1], dtype={"stock_code_5d": str}, keep_default_na=False)
    blockers = pd.read_csv(out / names[2], dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = read_json(out / names[3])
    quality = read_json(out / names[4])
    manifest = read_json(out / names[5])

    if len(syn) != 51 or syn["security_id"].nunique() != 20:
        errors.append("SYNTHESIS_SHAPE")
    if set(syn["p2a_overall_rank"].astype(int)) != set(range(1, 21)):
        errors.append("RANK_SET")
    if not set(syn["research_dimension"]).issubset(DIMS):
        errors.append("DIMENSION_SET")
    counts = syn["research_dimension"].value_counts().to_dict()
    expected = {"GOVERNANCE_VALUE_TRAP": 20, "EARNINGS_EXPECTATION_REVISION": 17, "CATALYST": 14}
    for dim, count in expected.items():
        if int(counts.get(dim, 0)) != count:
            errors.append(f"DIMENSION_COUNT:{dim}:{counts.get(dim,0)}")
    if not syn["prior_evidence_status"].eq("EVIDENCE_PARTIAL").all():
        errors.append("PRIOR_STATUS")
    if syn.duplicated(["security_id", "research_dimension"]).any():
        errors.append("DUPLICATE_SECURITY_DIMENSION")
    if not set(syn["evidence_sufficiency"]).issubset(SUFFICIENCY):
        errors.append("SUFFICIENCY_VOCABULARY")
    if syn["alpha_score"].replace("", pd.NA).notna().any():
        errors.append("ALPHA_SCORE")
    if (syn["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("SYNTHESIS_AUTHORITY")

    earnings = syn[syn["research_dimension"] == "EARNINGS_EXPECTATION_REVISION"]
    if len(earnings) != 17 or not earnings["finding_direction"].eq("UNKNOWN").all():
        errors.append("EARNINGS_DIRECTION_GUARD")
    if earnings["evidence_title"].str.contains(
        "profit alert|profit warning|profit increase|estimated results|results forecast",
        case=False,
        regex=True,
    ).any():
        errors.append("DIRECT_EXPECTATION_LEFT_PARTIAL")
    if not earnings["finding"].str.contains(
        "OPERATING_EVIDENCE|ANNUAL_ONLY", case=False, regex=True
    ).all():
        errors.append("EARNINGS_FINDING_GUARD")

    governance = syn[syn["research_dimension"] == "GOVERNANCE_VALUE_TRAP"]
    risky = governance[
        governance["evidence_title"].str.contains("auditor|connected transaction", case=False, regex=True)
        | governance["evidence_summary"].str.contains("auditor|connected transaction|related-party", case=False, regex=True)
    ]
    if risky.empty:
        errors.append("NO_GOVERNANCE_RISK_ROWS")
    elif not risky["graduation_blocker"].astype(str).str.lower().isin(["true", "1"]).all():
        errors.append("GOVERNANCE_BLOCKER_GUARD")

    if len(sec) != 20 or set(sec["p2a_overall_rank"].astype(int)) != set(range(1, 21)):
        errors.append("SECURITY_READINESS_SHAPE")
    if not set(sec["d2_readiness"]).issubset(READINESS):
        errors.append("READINESS_VOCABULARY")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().isin(["false", "0"]).all():
        errors.append("PREMATURE_SECURITY_GRADUATION")
    if (sec["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("SECURITY_AUTHORITY")

    blocker_mask = syn["graduation_blocker"].astype(str).str.lower().isin(["true", "1"])
    if len(blockers) != int(blocker_mask.sum()):
        errors.append("BLOCKER_QUEUE_COUNT")
    if not blockers.empty:
        if not blockers["graduation_blocker"].astype(str).str.lower().isin(["true", "1"]).all():
            errors.append("BLOCKER_QUEUE_FLAG")
        if (blockers["trade_authority"] != TRADE_AUTHORITY).any():
            errors.append("BLOCKER_AUTHORITY")

    if decision.get("status") != "PASS_P2B_E2_D2_TOP20_SYNTHESIS":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")
    if int(decision.get("partial_synthesis_rows", -1)) != 51:
        errors.append("DECISION_SYNTHESIS_ROWS")
    if int(decision.get("security_count", -1)) != 20:
        errors.append("DECISION_SECURITY_COUNT")
    if int(decision.get("graduation_blocker_rows", -1)) != len(blockers):
        errors.append("DECISION_BLOCKER_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_TARGETED_TOP20_BLOCKER_DEEPENING":
        errors.append("NEXT_GATE")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0:
            errors.append("PROTECTED_MUTATION:" + key)
    for payload in [decision, quality, manifest]:
        if payload.get("trade_authority") != TRADE_AUTHORITY:
            errors.append("JSON_AUTHORITY")
    return sorted(set(errors))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    errors = validate(Path(args.output))
    if errors:
        raise SystemExit("P2B_E2_D2_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_D2_TOP20_SYNTHESIS_VALIDATION")


if __name__ == "__main__":
    main()
