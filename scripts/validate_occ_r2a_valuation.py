from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/occ_r2/valuation/candidate"


def main() -> int:
    decision = json.loads((CANDIDATE / "VALUATION_CONTEXT_DECISION.json").read_text(encoding="utf-8"))
    validation = json.loads((CANDIDATE / "VALUATION_CONTEXT_VALIDATION.json").read_text(encoding="utf-8"))
    current = pd.read_parquet(CANDIDATE / "VALUATION_CONTEXT_CURRENT.parquet")
    audit = pd.read_csv(CANDIDATE / "FULL_REBUILD_AUDIT.csv")

    errors: list[str] = []
    if decision.get("status") != "PASS" or decision.get("hard_failures") != []:
        errors.append("DECISION_NOT_PASS")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        errors.append("VALIDATION_NOT_PASS")
    if int(audit["mismatch_count"].sum()) != 0:
        errors.append("FULL_REBUILD_MISMATCH")
    if int(len(current)) != int(decision["universe"]["required_financial_baseline_symbol_count"]):
        errors.append("UNIVERSE_COUNT_MISMATCH")
    if current["symbol"].duplicated().any():
        errors.append("DUPLICATE_SYMBOL")
    if set(current["trade_authority"].dropna().astype(str)) != {"NONE"}:
        errors.append("TRADE_AUTHORITY_PRESENT")
    if set(current["market_as_of_date"].dropna().astype(str)) != {str(decision["market_as_of_date"])}:
        errors.append("MARKET_AS_OF_MISMATCH")
    if decision["financial_denominator"]["status"] != "LKG_NOT_REFRESHED_BY_R2A":
        errors.append("FINANCIAL_DENOMINATOR_STATUS_NOT_EXPLICIT")
    if decision["financial_denominator"]["financial_event_propagation"] != "PENDING_OCC_R2B":
        errors.append("R2B_BOUNDARY_NOT_EXPLICIT")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": errors,
        "market_as_of_date": decision.get("market_as_of_date"),
        "row_count": int(len(current)),
        "financial_denominator_status": decision["financial_denominator"]["status"],
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
