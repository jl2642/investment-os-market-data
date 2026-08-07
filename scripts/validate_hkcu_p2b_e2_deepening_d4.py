#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
EXPECTED_RETAINED = {
    "HKEX:00551|GOVERNANCE_VALUE_TRAP",
    "HKEX:01114|CATALYST",
}
READINESS = {"READY_WITH_CONFIDENCE_CAP", "RETAINED_INVESTMENT_BLOCKER"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1"])


def validate(out: Path) -> list[str]:
    names = [
        "HKCU_P2B_E2_D4_REMAINING_BLOCKER_RESOLUTION.csv",
        "HKCU_P2B_E2_D4_RETAINED_INVESTMENT_BLOCKERS.csv",
        "HKCU_P2B_E2_D4_TOP20_SECURITY_READINESS.csv",
        "HKCU_P2B_E2_D4_DECISION.json",
        "HKCU_P2B_E2_D4_QUALITY_REPORT.json",
        "HKCU_P2B_E2_D4_MANIFEST.json",
    ]
    errors = ["MISSING_OUTPUT:" + x for x in names if not (out / x).exists()]
    if errors:
        return errors

    resolution = pd.read_csv(out / names[0], dtype={"stock_code_5d": str}, keep_default_na=False)
    retained = pd.read_csv(out / names[1], dtype={"stock_code_5d": str}, keep_default_na=False)
    sec = pd.read_csv(out / names[2], dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = read_json(out / names[3])
    quality = read_json(out / names[4])
    manifest = read_json(out / names[5])

    if len(resolution) != 12 or resolution["security_id"].nunique() != 10:
        errors.append("RESOLUTION_SHAPE")
    if set(resolution["remaining_priority_rank"].astype(int)) != set(range(1, 13)):
        errors.append("PRIORITY_SET")
    if resolution.duplicated(["security_id", "research_dimension"]).any():
        errors.append("DUPLICATE_SECURITY_DIMENSION")
    if resolution["alpha_score"].replace("", pd.NA).notna().any():
        errors.append("ALPHA_SCORE")
    if (resolution["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("RESOLUTION_AUTHORITY")

    post = bool_series(resolution["post_blocker"])
    actual_retained = set(
        resolution.loc[post, "security_id"].astype(str)
        + "|"
        + resolution.loc[post, "research_dimension"].astype(str)
    )
    if actual_retained != EXPECTED_RETAINED:
        errors.append("RETAINED_KEY_SET:" + ",".join(sorted(actual_retained)))
    if len(retained) != 2 or retained["security_id"].nunique() != 2:
        errors.append("RETAINED_SHAPE")
    retained_keys = set(retained["security_id"].astype(str) + "|" + retained["research_dimension"].astype(str))
    if retained_keys != EXPECTED_RETAINED:
        errors.append("RETAINED_TABLE_KEYS")

    yue = resolution[
        (resolution["security_id"] == "HKEX:00551")
        & (resolution["research_dimension"] == "GOVERNANCE_VALUE_TRAP")
    ]
    brilliance = resolution[
        (resolution["security_id"] == "HKEX:01114")
        & (resolution["research_dimension"] == "CATALYST")
    ]
    if len(yue) != 1 or not yue["post_finding"].str.contains("NEGATIVE_EARNINGS", case=False).all():
        errors.append("YUE_YUEN_RECLASSIFICATION")
    if len(brilliance) != 1 or not brilliance["post_finding"].str.contains("NEGATIVE_EARNINGS", case=False).all():
        errors.append("BRILLIANCE_NEGATIVE_EARNINGS")
    if not yue["resolution_direction"].eq("NEGATIVE").all() or not brilliance["resolution_direction"].eq("NEGATIVE").all():
        errors.append("NEGATIVE_DIRECTION_GUARD")

    cleared_keys = set(
        resolution.loc[~post, "security_id"].astype(str)
        + "|"
        + resolution.loc[~post, "research_dimension"].astype(str)
    )
    for key in [
        "HKEX:00300|CATALYST",
        "HKEX:01530|CATALYST",
        "HKEX:00941|GOVERNANCE_VALUE_TRAP",
        "HKEX:01308|EARNINGS_EXPECTATION_REVISION",
        "HKEX:00669|EARNINGS_EXPECTATION_REVISION",
        "HKEX:01530|EARNINGS_EXPECTATION_REVISION",
        "HKEX:00440|EARNINGS_EXPECTATION_REVISION",
        "HKEX:02888|GOVERNANCE_VALUE_TRAP",
        "HKEX:01997|EARNINGS_EXPECTATION_REVISION",
        "HKEX:01114|GOVERNANCE_VALUE_TRAP",
    ]:
        if key not in cleared_keys:
            errors.append("EXPECTED_NON_BLOCKER_MISSING:" + key)

    missing_data = resolution[
        (resolution["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")
        & (resolution["resolution_direction"] == "UNKNOWN")
    ]
    if bool_series(missing_data["post_blocker"]).any():
        errors.append("MISSING_DATA_TREATED_AS_BEARISH")

    if len(sec) != 20 or set(sec["p2a_overall_rank"].astype(int)) != set(range(1, 21)):
        errors.append("SECURITY_READINESS_SHAPE")
    if not set(sec["d4_readiness"]).issubset(READINESS):
        errors.append("READINESS_VOCABULARY")
    if int((sec["d4_readiness"] == "RETAINED_INVESTMENT_BLOCKER").sum()) != 2:
        errors.append("SECURITY_BLOCKER_COUNT")
    if int((sec["d4_readiness"] == "READY_WITH_CONFIDENCE_CAP").sum()) != 18:
        errors.append("SECURITY_READY_COUNT")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().isin(["false", "0"]).all():
        errors.append("PREMATURE_SECURITY_GRADUATION")
    if (sec["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("SECURITY_AUTHORITY")

    if decision.get("status") != "PASS_P2B_E2_D4_REMAINING_BLOCKER_DEEPENING":
        errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")
    expected_counts = {
        "target_rows": 12,
        "target_security_count": 10,
        "cleared_or_confidence_cap_rows": 10,
        "retained_investment_blocker_rows": 2,
        "remaining_blocker_rows": 2,
        "remaining_blocker_security_count": 2,
        "ready_with_confidence_cap_security_count": 18,
    }
    for key, value in expected_counts.items():
        if int(decision.get(key, -1)) != value:
            errors.append("DECISION_COUNT:" + key)
    if decision.get("next_gate") != "P2B_E2_TOP20_DECISION_SYNTHESIS":
        errors.append("NEXT_GATE")
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("PREMATURE_CANDIDATE_GRADUATION")
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
        raise SystemExit("P2B_E2_D4_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_D4_REMAINING_BLOCKER_DEEPENING_VALIDATION")


if __name__ == "__main__":
    main()
