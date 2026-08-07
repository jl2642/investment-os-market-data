#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

PREFIX = "HKCU_P2B_E2_S2_RANKS21_40"
PROGRAM_ID = "HKCU-P2B-E2-S2"
PASS_STATUS = "PASS_P2B_E2_RANKS21_40_DECISION_SYNTHESIS"
TRADE_AUTHORITY = "NONE"


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output)

    decision = read_json(out / f"{PREFIX}_DECISION.json")
    quality = read_json(out / f"{PREFIX}_QUALITY_REPORT.json")
    dim = pd.read_csv(out / f"{PREFIX}_DIMENSION_DECISION_SURFACE.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    sec = pd.read_csv(out / f"{PREFIX}_SECURITY_DECISION_SYNTHESIS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    blockers = pd.read_csv(out / f"{PREFIX}_RETAINED_INVESTMENT_BLOCKERS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != PASS_STATUS: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"): errors.append("QUALITY_STATUS")
    if int(decision.get("security_count", -1)) != 20 or len(sec) != 20: errors.append("SECURITY_COUNT")
    if int(decision.get("dimension_rows", -1)) != 60 or len(dim) != 60: errors.append("DIMENSION_COUNT")
    if int(decision.get("advance_security_count", -1)) != 19: errors.append("ADVANCE_COUNT")
    if int(decision.get("blocked_security_count", -1)) != 1 or len(blockers) != 1: errors.append("BLOCKED_COUNT")
    if set(decision.get("blocked_security_ids", [])) != {"HKEX:09636"}: errors.append("BLOCKED_SET")
    if set(blockers["security_id"]) != {"HKEX:09636"}: errors.append("BLOCKER_FILE_SET")
    if int(decision.get("retained_blocker_event_count", -1)) != 1: errors.append("BLOCKER_EVENT_COUNT")
    if int(decision.get("targeted_override_count", -1)) != 5: errors.append("OVERRIDE_COUNT")
    if int(decision.get("score_non_null_count", -1)) != 0: errors.append("SCORE_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("CANDIDATE_GRADUATION")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("TRADE_AUTHORITY")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append(key.upper())

    if dim.duplicated(["security_id", "research_dimension"]).any(): errors.append("DUPLICATE_DIMENSION")
    if dim["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("DIM_ALPHA_SCORE")
    if sec["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("SEC_ALPHA_SCORE")
    if not dim["trade_authority"].eq(TRADE_AUTHORITY).all() or not sec["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("ROW_TRADE_AUTHORITY")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().eq("false").all(): errors.append("ROW_CANDIDATE_GRADUATION")

    jf = dim[(dim["security_id"] == "HKEX:09636") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(jf) != 1: errors.append("JF_EARNINGS_ROW")
    else:
        r = jf.iloc[0]
        if r["final_dimension_state"] != "RETAINED_DIRECT_NEGATIVE_SIGNAL" or str(r["final_blocker"]).lower() != "true": errors.append("JF_NEGATIVE_BLOCKER")
        if "2026072901105.pdf" not in r["source_url"] or r["evidence_date"] != "2026-07-29" or "Profit Warning" not in r["evidence_title"]: errors.append("JF_FRESH_SOURCE")

    jfg = dim[(dim["security_id"] == "HKEX:09636") & (dim["research_dimension"] == "GOVERNANCE_VALUE_TRAP")]
    if len(jfg) != 1 or str(jfg.iloc[0]["final_blocker"]).lower() != "false": errors.append("JF_GOVERNANCE_DEDUP")
    if len(jfg) == 1 and len(jf) == 1 and jfg.iloc[0]["event_id"] != jf.iloc[0]["event_id"]: errors.append("JF_EVENT_LINEAGE")

    joinn = dim[(dim["security_id"] == "HKEX:06127") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(joinn) != 1 or str(joinn.iloc[0]["final_blocker"]).lower() != "false" or "2026042902973.pdf" not in joinn.iloc[0]["source_url"]: errors.append("JOINN_Q1_RECONCILIATION")

    uni = dim[(dim["security_id"] == "HKEX:02666") & (dim["research_dimension"] == "GOVERNANCE_VALUE_TRAP")]
    if len(uni) != 1 or uni.iloc[0]["final_dimension_state"] != "CONFIDENCE_CAP_MONITOR" or str(uni.iloc[0]["final_blocker"]).lower() != "false": errors.append("UNI_REMEDIATION_STATE")

    override_rows = dim[dim["decision_lineage"] == "S2_TARGETED_PRIMARY_OVERRIDE"]
    if len(override_rows) != 5: errors.append("OVERRIDE_LINEAGE_COUNT")
    if not override_rows["source_url"].str.startswith("https://www1.hkexnews.hk/").all(): errors.append("OVERRIDE_SOURCE")
    dates = pd.to_datetime(override_rows["evidence_date"], errors="coerce")
    if dates.isna().any() or (dates > pd.Timestamp("2026-08-07")).any(): errors.append("OVERRIDE_DATE")

    if errors:
        raise SystemExit("P2B_E2_S2_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print("PASS_P2B_E2_RANKS21_40_DECISION_SYNTHESIS_VALIDATION")


if __name__ == "__main__":
    main()
