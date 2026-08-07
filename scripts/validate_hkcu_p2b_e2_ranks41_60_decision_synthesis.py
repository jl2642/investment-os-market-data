#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

PREFIX = "HKCU_P2B_E2_S3_RANKS41_60"
PROGRAM_ID = "HKCU-P2B-E2-S3"
PASS_STATUS = "PASS_P2B_E2_RANKS41_60_DECISION_SYNTHESIS"
TRADE_AUTHORITY = "NONE"
EXPECTED_OVERRIDE_KEYS = {
    ("HKEX:03939", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:03939", "CATALYST"),
    ("HKEX:09696", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:09911", "EARNINGS_EXPECTATION_REVISION"),
}


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
    if int(decision.get("rank_start", -1)) != 41 or int(decision.get("rank_end", -1)) != 60: errors.append("RANK_WINDOW")
    if int(decision.get("security_count", -1)) != 20 or len(sec) != 20: errors.append("SECURITY_COUNT")
    if int(decision.get("dimension_rows", -1)) != 60 or len(dim) != 60: errors.append("DIMENSION_COUNT")
    if int(decision.get("advance_security_count", -1)) != 20: errors.append("ADVANCE_COUNT")
    if int(decision.get("blocked_security_count", -1)) != 0 or len(blockers) != 0: errors.append("BLOCKED_COUNT")
    if decision.get("blocked_security_ids", []) not in ([], None): errors.append("BLOCKED_SET")
    if int(decision.get("retained_blocker_event_count", -1)) != 0: errors.append("BLOCKER_EVENT_COUNT")
    if int(decision.get("targeted_override_count", -1)) != 4: errors.append("OVERRIDE_COUNT")
    if int(decision.get("score_non_null_count", -1)) != 0: errors.append("SCORE_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("CANDIDATE_GRADUATION")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("TRADE_AUTHORITY")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append(key.upper())

    ranks = sorted(pd.to_numeric(sec["p2a_overall_rank"], errors="coerce").astype(int).tolist())
    if ranks != list(range(41, 61)): errors.append("SECURITY_RANK_SET")
    if dim.duplicated(["security_id", "research_dimension"]).any(): errors.append("DUPLICATE_DIMENSION")
    if len(dim[dim["upstream_evidence_status"] == "EVIDENCE_PARTIAL"]) != 45: errors.append("PARTIAL_COUNT")
    if len(dim[dim["upstream_evidence_status"] != "EVIDENCE_PARTIAL"]) != 15: errors.append("NON_PARTIAL_COUNT")
    if (dim["upstream_evidence_status"] == "RESEARCH_REQUIRED").any(): errors.append("RESEARCH_REQUIRED_REMAINS")
    if dim["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("DIM_ALPHA_SCORE")
    if sec["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("SEC_ALPHA_SCORE")
    if not dim["trade_authority"].eq(TRADE_AUTHORITY).all() or not sec["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("ROW_TRADE_AUTHORITY")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().eq("false").all(): errors.append("ROW_CANDIDATE_GRADUATION")

    override = dim[list(zip(dim["security_id"], dim["research_dimension"])).__class__([False] * len(dim))] if False else None
    actual_override_keys = set()
    for key in EXPECTED_OVERRIDE_KEYS:
        row = dim[(dim["security_id"] == key[0]) & (dim["research_dimension"] == key[1])]
        if len(row) != 1:
            errors.append("OVERRIDE_KEY_MISSING:" + key[0] + ":" + key[1])
            continue
        r = row.iloc[0]
        if not str(r["source_url"]).startswith("https://www1.hkexnews.hk/"): errors.append("OVERRIDE_SOURCE:" + key[0])
        if pd.to_datetime(r["evidence_date"], errors="coerce") > pd.Timestamp("2026-08-07"): errors.append("OVERRIDE_DATE:" + key[0])
        actual_override_keys.add(key)
    if actual_override_keys != EXPECTED_OVERRIDE_KEYS: errors.append("OVERRIDE_KEY_SET")

    wg_e = dim[(dim["security_id"] == "HKEX:03939") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(wg_e) != 1 or wg_e.iloc[0]["evidence_date"] != "2026-08-04" or wg_e.iloc[0]["final_direction"] != "POSITIVE" or str(wg_e.iloc[0]["final_blocker"]).lower() != "false": errors.append("WANGUO_FRESH_POSITIVE_ALERT")
    if len(wg_e) == 1 and "2026080402273.pdf" not in wg_e.iloc[0]["source_url"]: errors.append("WANGUO_FRESH_SOURCE")

    wg_c = dim[(dim["security_id"] == "HKEX:03939") & (dim["research_dimension"] == "CATALYST")]
    if len(wg_c) != 1 or wg_c.iloc[0]["final_dimension_state"] != "MONITOR_ONLY" or str(wg_c.iloc[0]["final_blocker"]).lower() != "false": errors.append("WANGUO_SLOPE_MONITOR")

    tq = dim[(dim["security_id"] == "HKEX:09696") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(tq) != 1 or tq.iloc[0]["final_direction"] != "POSITIVE" or tq.iloc[0]["final_dimension_state"] != "EVIDENCE_COMPLETE" or str(tq.iloc[0]["final_blocker"]).lower() != "false": errors.append("TIANQI_FORECAST_DIRECTION")
    if len(tq) == 1 and "2026071401090.pdf" not in tq.iloc[0]["source_url"]: errors.append("TIANQI_FORECAST_SOURCE")

    nb = dim[(dim["security_id"] == "HKEX:09911") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(nb) != 1 or nb.iloc[0]["final_direction"] != "POSITIVE" or nb.iloc[0]["final_dimension_state"] != "CONFIDENCE_CAP_MONITOR" or str(nb.iloc[0]["final_blocker"]).lower() != "false": errors.append("NEWBORNTOWN_H1_STATE")
    if len(nb) == 1 and "2026072200334.pdf" not in nb.iloc[0]["source_url"]: errors.append("NEWBORNTOWN_H1_SOURCE")

    if errors:
        raise SystemExit("P2B_E2_S3_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print("PASS_P2B_E2_RANKS41_60_DECISION_SYNTHESIS_VALIDATION")


if __name__ == "__main__":
    main()
