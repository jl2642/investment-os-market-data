from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/occ_r2/valuation/candidate"


def main() -> int:
    decision = json.loads((CANDIDATE / "VALUATION_CONTEXT_DECISION.json").read_text(encoding="utf-8"))
    validation = json.loads((CANDIDATE / "VALUATION_CONTEXT_VALIDATION.json").read_text(encoding="utf-8"))
    release = json.loads((CANDIDATE / "FMDL3DC_MARKET_REFRESH_RELEASE.json").read_text(encoding="utf-8"))
    detail = pd.read_parquet(CANDIDATE / "FMDL3DC_MARKET_REFRESH_DETAIL.parquet")

    errors: list[str] = []
    expected_qc = "PASS_MARKET_VALUATION_REFRESH_EXACT_DENOMINATOR_LKG"
    if decision.get("status") != "PASS" or decision.get("qc_status") != expected_qc:
        errors.append("DECISION_NOT_PASS")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        errors.append("VALIDATION_NOT_PASS")
    if release.get("status") != "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED":
        errors.append("RELEASE_NOT_ACCEPTED")
    if release.get("qc_status") != expected_qc:
        errors.append("RELEASE_QC_NOT_EXACT_BASELINE_REFRESH")
    if decision.get("financial_denominator", {}).get("status") != "EXACT_LKG_FROM_ACCEPTED_R2B2_BASELINE":
        errors.append("EXACT_FINANCIAL_BASELINE_NOT_BOUND")
    if decision.get("financial_denominator", {}).get("financial_event_propagation") != "COMPLETE_AS_OF_EXACT_BASELINE":
        errors.append("FINANCIAL_EVENT_PROPAGATION_REGRESSED")
    if set(detail["market_as_of_date"].astype(str)) != {str(decision.get("market_as_of_date"))}:
        errors.append("MARKET_AS_OF_MISMATCH")
    if set(detail["trade_authority"].astype(str)) != {"NONE"}:
        errors.append("TRADE_AUTHORITY_PRESENT")
    if float(validation.get("market_coverage_ratio") or 0.0) < 0.99:
        errors.append("MARKET_COVERAGE_BELOW_0_99")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": errors,
        "market_as_of_date": decision.get("market_as_of_date"),
        "exact_baseline_market_as_of_date": decision.get("exact_baseline_market_as_of_date"),
        "detail_rows": int(len(detail)),
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
