#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PREFIX = "HKCU_P2B_FINAL"
PROGRAM_ID = "HKCU-P2B-FINAL"
PASS_STATUS = "PASS_P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS"
TRADE_AUTHORITY = "NONE"
EXPECTED_BLOCKERS = {"HKEX:00551", "HKEX:01114", "HKEX:09636", "HKEX:02313", "HKEX:06110"}
EXPECTED_AH = {
    "HKEX:00177": "688180.SH", "HKEX:00300": "000333.SZ", "HKEX:00358": "000898.SZ",
    "HKEX:00525": "000429.SZ", "HKEX:00564": "601298.SH", "HKEX:00688": "601800.SH",
    "HKEX:01766": "601766.SH", "HKEX:01818": "601898.SH", "HKEX:01880": "601326.SH",
    "HKEX:02314": "001213.SZ", "HKEX:02359": "603259.SH", "HKEX:02600": "601600.SH",
    "HKEX:09696": "002466.SZ",
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
    sec = pd.read_csv(out / f"{PREFIX}_SECURITY_CROSS_SECTION.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    dim = pd.read_csv(out / f"{PREFIX}_COMPANY_DIMENSION_SURFACE.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    blockers = pd.read_csv(out / f"{PREFIX}_RETAINED_BLOCKERS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    ah = pd.read_csv(out / f"{PREFIX}_AH_RELATIVE_VALUE.csv", dtype={"stock_code_5d": str}, keep_default_na=False)

    errors: list[str] = []
    if decision.get("program_id") != PROGRAM_ID: errors.append("PROGRAM_ID")
    if decision.get("status") != PASS_STATUS: errors.append("DECISION_STATUS")
    if quality.get("status") != "PASS" or quality.get("hard_failures"): errors.append("QUALITY_STATUS")
    if int(decision.get("security_count", -1)) != 77 or len(sec) != 77: errors.append("SECURITY_COUNT")
    if int(decision.get("company_dimension_rows", -1)) != 231 or len(dim) != 231: errors.append("DIMENSION_COUNT")
    if int(decision.get("advance_security_count", -1)) != 72: errors.append("ADVANCE_COUNT")
    if int(decision.get("blocked_security_count", -1)) != 5 or len(blockers) != 5: errors.append("BLOCKED_COUNT")
    if set(decision.get("blocked_security_ids", [])) != EXPECTED_BLOCKERS: errors.append("BLOCKED_SET")
    if set(blockers["security_id"]) != EXPECTED_BLOCKERS: errors.append("BLOCKER_FILE_SET")
    if int(decision.get("transaction_tax_complete_count", -1)) != 77: errors.append("TRANSACTION_TAX_COUNT")
    if int(decision.get("true_ah_pair_count", -1)) != 13: errors.append("TRUE_AH_COUNT")
    if int(decision.get("ah_numeric_completed_count", -1)) != 13 or len(ah) != 13: errors.append("AH_NUMERIC_COUNT")
    if int(decision.get("alpha_score_non_null_count", -1)) != 0: errors.append("ALPHA_COUNT")
    if decision.get("formal_candidate_graduation_allowed") is not False: errors.append("CANDIDATE_GRADUATION")
    if decision.get("next_gate") != "P3_0_CANDIDATE_GRADUATION_CONTRACT": errors.append("NEXT_GATE")
    if decision.get("trade_authority") != TRADE_AUTHORITY: errors.append("TRADE_AUTHORITY")
    for k in ["candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders_created"]:
        if int(decision.get(k, -1)) != 0: errors.append(k.upper())

    ranks = pd.to_numeric(sec["p2a_overall_rank"], errors="coerce")
    if ranks.isna().any() or sorted(ranks.astype(int).tolist()) != list(range(1, 78)): errors.append("P2A_RANK_SET")
    if sec["security_id"].duplicated().any(): errors.append("DUPLICATE_SECURITY")
    if dim.duplicated(["security_id", "research_dimension"]).any(): errors.append("DUPLICATE_DIMENSION")
    if set(dim["security_id"]) != set(sec["security_id"]): errors.append("DIMENSION_SECURITY_SET")
    if not dim.groupby("security_id").size().eq(3).all(): errors.append("THREE_COMPANY_DIMENSIONS_PER_SECURITY")

    held = sec[sec["final_p2b_state"].eq("HOLD_RETAINED_INVESTMENT_BLOCKER")]
    ready = sec[sec["final_p2b_state"].eq("READY_FOR_P3_CONTRACT_EVALUATION_WITH_CONFIDENCE_CAP")]
    if len(held) != 5 or set(held["security_id"]) != EXPECTED_BLOCKERS: errors.append("FINAL_STATE_BLOCKERS")
    if len(ready) != 72: errors.append("FINAL_STATE_READY")
    if not sec["transaction_tax_evidence_status"].eq("EVIDENCE_COMPLETE").all(): errors.append("TX_NOT_COMPLETE")
    if not sec["p2a_rank_preserved_not_rescored"].astype(str).str.lower().eq("true").all(): errors.append("P2A_RANK_PRESERVATION")
    if sec["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("SEC_ALPHA_SCORE")
    if dim["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("DIM_ALPHA_SCORE")
    if not sec["formal_candidate_graduation_allowed"].astype(str).str.lower().eq("false").all(): errors.append("SEC_CANDIDATE_GRADUATION")
    if not dim["formal_candidate_graduation_allowed"].astype(str).str.lower().eq("false").all(): errors.append("DIM_CANDIDATE_GRADUATION")
    if not sec["trade_authority"].eq(TRADE_AUTHORITY).all() or not dim["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("ROW_TRADE_AUTHORITY")

    actual_ah = dict(zip(ah["security_id"], ah["a_symbol"]))
    if actual_ah != EXPECTED_AH: errors.append("AH_PAIR_SET")
    for c in ["a_close_cny", "h_close_hkd", "cny_per_hkd", "a_over_h_ratio", "h_discount_to_a_pct"]:
        vals = pd.to_numeric(ah[c], errors="coerce")
        if vals.isna().any(): errors.append("AH_NUMERIC_" + c.upper())
    if not ah["a_price_date"].eq("2026-08-07").all(): errors.append("A_PRICE_DATE")
    if not ah["h_price_date"].eq("2026-08-07").all(): errors.append("H_PRICE_DATE")
    if not ah["fx_date"].eq("2026-08-07").all(): errors.append("FX_DATE")
    ratio = pd.to_numeric(ah["a_close_cny"], errors="coerce") / (pd.to_numeric(ah["h_close_hkd"], errors="coerce") * pd.to_numeric(ah["cny_per_hkd"], errors="coerce"))
    published = pd.to_numeric(ah["a_over_h_ratio"], errors="coerce")
    if ((ratio - published).abs() > 1e-6).any(): errors.append("AH_FORMULA_RATIO")
    published_pct = pd.to_numeric(ah["h_discount_to_a_pct"], errors="coerce")
    if ((((ratio - 1.0) * 100.0) - published_pct).abs() > 0.001).any(): errors.append("AH_FORMULA_DISCOUNT")
    if ah["alpha_score"].astype(str).str.strip().replace({"nan":"", "<NA>":""}).ne("").any(): errors.append("AH_ALPHA_SCORE")
    if not ah["trade_authority"].eq(TRADE_AUTHORITY).all(): errors.append("AH_TRADE_AUTHORITY")

    # Cross-sectional output remains P2B research readiness, not ranking promotion.
    if "aggregate_score" in sec.columns and pd.to_numeric(sec["aggregate_score"], errors="coerce").isna().all(): errors.append("P2A_SCREENING_SCORE_LOST")
    if quality.get("p2a_rank_preserved_not_rescored") is not True: errors.append("QUALITY_P2A_GUARD")
    if quality.get("evidence_balance_descriptive_not_scored") is not True: errors.append("QUALITY_EVIDENCE_BALANCE_GUARD")
    if quality.get("ah_relative_value_is_context_not_alpha") is not True: errors.append("QUALITY_AH_GUARD")
    if quality.get("formal_candidate_graduation_allowed") is not False: errors.append("QUALITY_GRADUATION_GUARD")

    if errors:
        raise SystemExit("P2B_FINAL_VALIDATION_FAILED:" + "|".join(sorted(set(errors))))
    print("PASS_P2B_FINAL_CROSS_SECTIONAL_SYNTHESIS_VALIDATION")


if __name__ == "__main__":
    main()
