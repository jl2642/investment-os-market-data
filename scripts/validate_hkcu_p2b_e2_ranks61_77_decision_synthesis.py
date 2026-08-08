#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PREFIX = "HKCU_P2B_E2_S4_RANKS61_77"
PROGRAM_ID = "HKCU-P2B-E2-S4"
PASS_STATUS = "PASS_P2B_E2_RANKS61_77_DECISION_SYNTHESIS"
TRADE_AUTHORITY = "NONE"
EXPECTED_BLOCKERS = {"HKEX:02313", "HKEX:06110"}
EXPECTED_OVERRIDE_KEYS = {
    ("HKEX:01208", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:03759", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:03759", "CATALYST"),
    ("HKEX:02313", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:02313", "CATALYST"),
    ("HKEX:06110", "EARNINGS_EXPECTATION_REVISION"),
    ("HKEX:06110", "CATALYST"),
}


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def b(v) -> bool:
    return str(v).lower() == "true"


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
    if int(decision.get("rank_start", -1)) != 61 or int(decision.get("rank_end", -1)) != 77: errors.append("RANK_WINDOW")
    if int(decision.get("security_count", -1)) != 17 or len(sec) != 17: errors.append("SECURITY_COUNT")
    if int(decision.get("dimension_rows", -1)) != 51 or len(dim) != 51: errors.append("DIMENSION_COUNT")
    if int(decision.get("advance_security_count", -1)) != 15: errors.append("ADVANCE_COUNT")
    if int(decision.get("blocked_security_count", -1)) != 2 or len(blockers) != 2: errors.append("BLOCKED_COUNT")
    if set(decision.get("blocked_security_ids", [])) != EXPECTED_BLOCKERS: errors.append("BLOCKED_SET")
    if set(blockers["security_id"]) != EXPECTED_BLOCKERS: errors.append("BLOCKER_FILE_SET")
    if int(decision.get("retained_blocker_event_count", -1)) != 2: errors.append("BLOCKER_EVENT_COUNT")
    if int(decision.get("targeted_override_count", -1)) != 7: errors.append("OVERRIDE_COUNT")
    if int(decision.get("score_non_null_count", -1)) != 0: errors.append("SCORE_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("CANDIDATE_GRADUATION")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("TRADE_AUTHORITY")
    if decision.get("next_gate") != "P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS": errors.append("NEXT_GATE")
    for key in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(key, -1)) != 0: errors.append(key.upper())

    ranks = sorted(pd.to_numeric(sec["p2a_overall_rank"], errors="coerce").astype(int).tolist())
    if ranks != list(range(61, 78)): errors.append("SECURITY_RANK_SET")
    if dim.duplicated(["security_id", "research_dimension"]).any(): errors.append("DUPLICATE_DIMENSION")
    if len(dim[dim["upstream_evidence_status"] == "EVIDENCE_PARTIAL"]) != 43: errors.append("PARTIAL_COUNT")
    if len(dim[dim["upstream_evidence_status"] != "EVIDENCE_PARTIAL"]) != 8: errors.append("NON_PARTIAL_COUNT")
    if (dim["upstream_evidence_status"] == "RESEARCH_REQUIRED").any(): errors.append("RESEARCH_REQUIRED_REMAINS")
    if dim["alpha_score"].astype(str).str.strip().replace({"nan": "", "<NA>": ""}).ne("").any(): errors.append("DIM_ALPHA_SCORE")
    if sec["alpha_score"].astype(str).str.strip().replace({"nan": "", "<NA>": ""}).ne("").any(): errors.append("SEC_ALPHA_SCORE")
    if not dim["trade_authority"].eq(TRADE_AUTHORITY).all() or not sec["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("ROW_TRADE_AUTHORITY")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().eq("false").all(): errors.append("ROW_CANDIDATE_GRADUATION")

    override_rows = dim[dim["decision_lineage"] == "S2_TARGETED_PRIMARY_OVERRIDE"]
    actual_override_keys = set(zip(override_rows["security_id"], override_rows["research_dimension"]))
    if actual_override_keys != EXPECTED_OVERRIDE_KEYS: errors.append("OVERRIDE_KEY_SET")
    if len(override_rows) != 7: errors.append("OVERRIDE_LINEAGE_COUNT")
    if not override_rows["source_url"].str.startswith("https://www1.hkexnews.hk/").all(): errors.append("OVERRIDE_SOURCE")
    dates = pd.to_datetime(override_rows["evidence_date"], errors="coerce")
    if dates.isna().any() or (dates > pd.Timestamp("2026-08-07")).any(): errors.append("OVERRIDE_DATE")

    mmg = dim[(dim["security_id"] == "HKEX:01208") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    if len(mmg) != 1 or mmg.iloc[0]["evidence_date"] != "2026-07-21" or mmg.iloc[0]["final_dimension_state"] != "CONFIDENCE_CAP_MONITOR" or b(mmg.iloc[0]["final_blocker"]): errors.append("MMG_CURRENT_OUTLOOK_STATE")
    if len(mmg) == 1 and "2026072100440.pdf" not in mmg.iloc[0]["source_url"]: errors.append("MMG_CURRENT_OUTLOOK_SOURCE")

    pe = dim[(dim["security_id"] == "HKEX:03759") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    pc = dim[(dim["security_id"] == "HKEX:03759") & (dim["research_dimension"] == "CATALYST")]
    if len(pe) != 1 or pe.iloc[0]["final_direction"] != "POSITIVE" or pe.iloc[0]["final_dimension_state"] != "EVIDENCE_COMPLETE" or b(pe.iloc[0]["final_blocker"]): errors.append("PHARMARON_POSITIVE_ESTIMATE")
    if len(pc) != 1 or pc.iloc[0]["final_direction"] != "POSITIVE" or b(pc.iloc[0]["final_blocker"]): errors.append("PHARMARON_POSITIVE_CATALYST")
    if len(pe) == 1 and len(pc) == 1 and pe.iloc[0]["event_id"] != pc.iloc[0]["event_id"]: errors.append("PHARMARON_EVENT_LINEAGE")
    if len(pe) == 1 and "2026071300959.pdf" not in pe.iloc[0]["source_url"]: errors.append("PHARMARON_SOURCE")

    se = dim[(dim["security_id"] == "HKEX:02313") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    sc = dim[(dim["security_id"] == "HKEX:02313") & (dim["research_dimension"] == "CATALYST")]
    if len(se) != 1 or se.iloc[0]["final_direction"] != "NEGATIVE" or not b(se.iloc[0]["final_blocker"]): errors.append("SHENZHOU_EARNINGS_BLOCKER")
    if len(sc) != 1 or sc.iloc[0]["final_direction"] != "NEGATIVE" or b(sc.iloc[0]["final_blocker"]): errors.append("SHENZHOU_CATALYST_DEDUP")
    if len(se) == 1 and len(sc) == 1 and se.iloc[0]["event_id"] != sc.iloc[0]["event_id"]: errors.append("SHENZHOU_EVENT_LINEAGE")
    if len(se) == 1 and (se.iloc[0]["evidence_date"] != "2026-08-07" or "2026080700424.pdf" not in se.iloc[0]["source_url"]): errors.append("SHENZHOU_FRESH_SOURCE")

    te = dim[(dim["security_id"] == "HKEX:06110") & (dim["research_dimension"] == "EARNINGS_EXPECTATION_REVISION")]
    tc = dim[(dim["security_id"] == "HKEX:06110") & (dim["research_dimension"] == "CATALYST")]
    if len(te) != 1 or te.iloc[0]["final_direction"] != "NEGATIVE" or te.iloc[0]["final_dimension_state"] != "CONFIDENCE_CAP_MONITOR" or b(te.iloc[0]["final_blocker"]): errors.append("TOPSPORTS_EARNINGS_CONFIDENCE_CAP")
    if len(tc) != 1 or tc.iloc[0]["final_direction"] != "NEGATIVE" or not b(tc.iloc[0]["final_blocker"]): errors.append("TOPSPORTS_BLOCKER")
    if len(te) == 1 and len(tc) == 1 and te.iloc[0]["event_id"] != tc.iloc[0]["event_id"]: errors.append("TOPSPORTS_EVENT_LINEAGE")
    if len(tc) == 1 and (tc.iloc[0]["evidence_date"] != "2026-07-22" or "2026072200069.pdf" not in tc.iloc[0]["source_url"]): errors.append("TOPSPORTS_SOURCE")

    if errors:
        raise SystemExit("P2B_E2_S4_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print("PASS_P2B_E2_RANKS61_77_DECISION_SYNTHESIS_VALIDATION")


if __name__ == "__main__":
    main()
