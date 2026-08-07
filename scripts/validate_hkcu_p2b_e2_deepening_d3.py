#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

TRADE_AUTHORITY = "NONE"
ALLOWED = {"CLEARED_MONITOR", "RECLASSIFIED_MONITOR", "RETAINED_TARGETED", "RECLASSIFIED_TARGETED"}
CLEARED = {"CLEARED_MONITOR", "RECLASSIFIED_MONITOR"}
RETAINED = {"RETAINED_TARGETED", "RECLASSIFIED_TARGETED"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1"])


def validate(out: Path) -> list[str]:
    required = [
        "HKCU_P2B_E2_D3_HIGH_BLOCKER_RESOLUTION.csv",
        "HKCU_P2B_E2_D3_REMAINING_BLOCKER_QUEUE.csv",
        "HKCU_P2B_E2_D3_TOP20_SECURITY_READINESS.csv",
        "HKCU_P2B_E2_D3_DECISION.json",
        "HKCU_P2B_E2_D3_QUALITY_REPORT.json",
        "HKCU_P2B_E2_D3_MANIFEST.json",
    ]
    errors = ["MISSING_OUTPUT:" + n for n in required if not (out / n).exists()]
    if errors:
        return errors

    res = pd.read_csv(out / required[0], dtype={"stock_code_5d": str}, keep_default_na=False)
    rem = pd.read_csv(out / required[1], dtype={"stock_code_5d": str}, keep_default_na=False)
    sec = pd.read_csv(out / required[2], dtype={"stock_code_5d": str}, keep_default_na=False)
    decision = read_json(out / required[3])
    quality = read_json(out / required[4])
    manifest = read_json(out / required[5])

    if len(res) != 14 or res["security_id"].nunique() != 9:
        errors.append("RESOLUTION_SHAPE")
    if not res["prior_materiality"].eq("HIGH").all():
        errors.append("NON_HIGH_TARGET")
    if res.duplicated(["security_id", "research_dimension"]).any():
        errors.append("DUPLICATE_TARGET")
    if not set(res["resolution_status"]).issubset(ALLOWED):
        errors.append("RESOLUTION_VOCABULARY")
    post = truthy(res["post_blocker"])
    if len(res[~post]) != 9 or len(res[post]) != 5:
        errors.append("POST_BLOCKER_COUNTS")
    if not res[~post]["resolution_status"].isin(CLEARED).all():
        errors.append("CLEARED_STATUS_INCONSISTENT")
    if not res[post]["resolution_status"].isin(RETAINED).all():
        errors.append("RETAINED_STATUS_INCONSISTENT")
    if res["alpha_score"].replace("", pd.NA).notna().any():
        errors.append("ALPHA_SCORE_RESOLUTION")
    if (res["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("AUTHORITY_RESOLUTION")

    if len(rem) != 12:
        errors.append(f"REMAINING_BLOCKER_COUNT:{len(rem)}")
    if not rem.empty:
        if not truthy(rem["graduation_blocker"]).all():
            errors.append("REMAINING_NON_BLOCKER")
        if (rem["materiality"] == "HIGH").sum() != 5:
            errors.append("REMAINING_HIGH_COUNT")
        if (rem["materiality"] == "MEDIUM").sum() != 7:
            errors.append("REMAINING_MEDIUM_COUNT")

    if len(sec) != 20 or set(sec["p2a_overall_rank"].astype(int)) != set(range(1, 21)):
        errors.append("SECURITY_READINESS_SHAPE")
    targeted = sec["d3_readiness"] == "TARGETED_DEEPENING_REQUIRED"
    ready = sec["d3_readiness"] == "READY_WITH_CONFIDENCE_CAP"
    if int(targeted.sum()) != 10 or int(ready.sum()) != 10:
        errors.append("SECURITY_READINESS_COUNTS")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().isin(["false", "0"]).all():
        errors.append("PREMATURE_GRADUATION")
    if sec["alpha_score"].replace("", pd.NA).notna().any():
        errors.append("ALPHA_SCORE_SECURITY")
    if (sec["trade_authority"] != TRADE_AUTHORITY).any():
        errors.append("AUTHORITY_SECURITY")

    def row(sec_id: str, dim: str):
        x = res[(res["security_id"] == sec_id) & (res["research_dimension"] == dim)]
        return None if len(x) != 1 else x.iloc[0]

    midea = row("HKEX:00300", "CATALYST")
    if midea is None or not str(midea["post_blocker"]).lower() in ("true", "1"):
        errors.append("MIDEA_SPINOFF_PREMATURE_CLEAR")
    sbio = row("HKEX:01530", "CATALYST")
    if sbio is None or not str(sbio["post_blocker"]).lower() in ("true", "1"):
        errors.append("3SBIO_SPINOFF_PREMATURE_CLEAR")
    yue = row("HKEX:00551", "GOVERNANCE_VALUE_TRAP")
    if yue is None or yue["resolution_status"] != "RECLASSIFIED_TARGETED":
        errors.append("YUE_YUEN_MATERIAL_CCT_GUARD")
    bric = row("HKEX:01114", "CATALYST")
    if bric is None or bric["cross_dimension_signal"] != "FRESH_NEGATIVE_EARNINGS_ALERT" or bric["resolution_direction"] != "NEGATIVE":
        errors.append("BRILLIANCE_FRESH_WARNING_GUARD")
    brig = row("HKEX:01114", "GOVERNANCE_VALUE_TRAP")
    if brig is None or not str(brig["post_blocker"]).lower() in ("true", "1"):
        errors.append("BRILLIANCE_CONNECTED_GOVERNANCE_PREMATURE_CLEAR")
    gdie = row("HKEX:00270", "EARNINGS_EXPECTATION_REVISION")
    if gdie is None or gdie["cross_dimension_signal"] != "LINEAGE_RECONCILED_CURRENT_OPERATING_GROWTH" or str(gdie["post_blocker"]).lower() not in ("false", "0"):
        errors.append("GUANGDONG_LINEAGE_RECONCILIATION_GUARD")

    if decision.get("status") != "PASS_P2B_E2_D3_HIGH_BLOCKER_DEEPENING":
        errors.append("DECISION_STATUS")
    expected_decision = {
        "target_rows": 14,
        "cleared_or_monitor_only_rows": 9,
        "retained_targeted_rows": 5,
        "remaining_total_blocker_rows_after_d3": 12,
        "remaining_targeted_security_count": 10,
        "ready_with_confidence_cap_security_count": 10,
        "score_non_null_count": 0,
    }
    for k, v in expected_decision.items():
        if int(decision.get(k, -1)) != v:
            errors.append("DECISION_COUNT:" + k)
    if decision.get("formal_candidate_graduation_allowed") is not False:
        errors.append("DECISION_PREMATURE_GRADUATION")
    if decision.get("next_gate") != "P2B_E2_TOP20_REMAINING_BLOCKER_DEEPENING":
        errors.append("NEXT_GATE")
    for k in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(k, -1)) != 0:
            errors.append("PROTECTED_MUTATION:" + k)

    if quality.get("status") != "PASS" or quality.get("hard_failures"):
        errors.append("QUALITY_STATUS")
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
        raise SystemExit("P2B_E2_D3_VALIDATION_FAILED:" + "|".join(errors))
    print("PASS_P2B_E2_D3_HIGH_BLOCKER_DEEPENING_VALIDATION")


if __name__ == "__main__":
    main()
