#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ACCEPTED_FMDL5E = "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _code(value: object) -> str | None:
    if pd.isna(value):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[-5:].zfill(5) if digits else None


def _bool(value: object) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "y"}


def service_day_age(start: str, end: str, calendar: dict) -> int:
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if e < s:
        return -1
    blocked = {date.fromisoformat(x) for x in calendar.get("full_day_non_service_dates", [])}
    count = 0
    d = s + timedelta(days=1)
    while d <= e:
        if d.weekday() < 5 and d not in blocked:
            count += 1
        d += timedelta(days=1)
    return count


def build(
    eligibility: pd.DataFrame,
    screening: pd.DataFrame,
    fmdl5e_decision: dict,
    calendar: dict,
    contract: dict,
    eligibility_as_of: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    failures: list[str] = []
    if fmdl5e_decision.get("status") != contract["accepted_fmdl5e_status"]:
        failures.append("FMDL5E_NOT_ACCEPTED")
    if fmdl5e_decision.get("hard_failures"):
        failures.append("FMDL5E_HARD_FAILURE")
    if fmdl5e_decision.get("trade_authority") != "NONE":
        failures.append("FMDL5E_TRADE_AUTHORITY")

    fmdl_as_of = str(fmdl5e_decision.get("as_of_date") or "")
    try:
        age = service_day_age(fmdl_as_of, eligibility_as_of, calendar)
    except Exception:
        age = -999
        failures.append("FRESHNESS_DATE_PARSE")
    if age < 0:
        failures.append("FMDL5E_FUTURE_VS_ELIGIBILITY")
    max_age = int(contract["freshness"]["maximum_fmdl5e_age_stock_connect_service_days"])
    stale = age > max_age

    e_required = {"security_code", "combined_status", "buy_eligible", "sell_only", "as_of_date"}
    s_required = {
        "security_id", "stock_code_5d", "security_type", "investability_status",
        "avg_turnover_hkd_20d", "active_trade_ratio_60d", "zero_volume_days_20d",
        "latest_close", "financial_decision_grade", "market_latest_date", "as_of_date",
    }
    if not e_required.issubset(eligibility.columns):
        failures.append("ELIGIBILITY_FIELDS_MISSING:" + ",".join(sorted(e_required - set(eligibility.columns))))
    if not s_required.issubset(screening.columns):
        failures.append("FMDL5E_FIELDS_MISSING:" + ",".join(sorted(s_required - set(screening.columns))))
    if failures and any(x.startswith(("ELIGIBILITY_FIELDS", "FMDL5E_FIELDS")) for x in failures):
        raise ValueError(";".join(failures))

    e = eligibility.copy()
    e["stock_code_5d"] = e["security_code"].map(_code)
    e = e.drop_duplicates("stock_code_5d")
    s = screening.copy()
    s["stock_code_5d"] = s["stock_code_5d"].map(_code)
    s = s.drop_duplicates("stock_code_5d")

    merged = e.merge(s, on="stock_code_5d", how="outer", suffixes=("_eligibility", "_fmdl5e"), indicator=True)
    merged["security_id"] = merged.get("security_id", pd.Series(index=merged.index, dtype=object))
    merged["security_id"] = merged["security_id"].fillna("HKEX:" + merged["stock_code_5d"].astype(str))
    merged["combined_status"] = merged["combined_status"].fillna("UNKNOWN_BLOCKED")
    merged["buy_eligible"] = merged["buy_eligible"].map(_bool)
    merged.loc[merged["_merge"] == "right_only", "buy_eligible"] = False
    merged["sell_only"] = merged["sell_only"].map(_bool)
    merged.loc[merged["_merge"] == "right_only", "sell_only"] = False

    for col in ("avg_turnover_hkd_20d", "active_trade_ratio_60d", "zero_volume_days_20d", "latest_close"):
        merged[col] = pd.to_numeric(merged.get(col), errors="coerce")

    gate = contract["investable_gate"]
    financial_ok = merged["financial_decision_grade"].map(_bool)
    checks = {
        "MISSING_FMDL5E_COVERAGE": merged["_merge"].eq("left_only"),
        "NOT_SOUTHBOUND_BUY_ELIGIBLE": ~merged["combined_status"].astype(str).str.startswith(gate["required_eligibility_prefix"]),
        "FMDL5E_NOT_INVESTABLE": ~merged["investability_status"].isin(gate["allowed_fmdl5e_investability_status"]),
        "NON_COMMON_EQUITY": ~merged["security_type"].isin(gate["allowed_security_types"]),
        "LOW_20D_TURNOVER": merged["avg_turnover_hkd_20d"].lt(float(gate["minimum_avg_turnover_hkd_20d"])) | merged["avg_turnover_hkd_20d"].isna(),
        "LOW_ACTIVE_TRADE_RATIO": merged["active_trade_ratio_60d"].lt(float(gate["minimum_active_trade_ratio_60d"])) | merged["active_trade_ratio_60d"].isna(),
        "EXCESS_ZERO_VOLUME_DAYS": merged["zero_volume_days_20d"].gt(int(gate["maximum_zero_volume_days_20d"])) | merged["zero_volume_days_20d"].isna(),
        "MISSING_VALID_PRICE": merged["latest_close"].le(0) | merged["latest_close"].isna(),
        "FINANCIAL_EVIDENCE_INCOMPLETE": ~financial_ok if gate["require_decision_grade_financials"] else pd.Series(False, index=merged.index),
    }
    reasons: list[str] = []
    for idx in merged.index:
        failed = [name for name, mask in checks.items() if bool(mask.loc[idx])]
        reasons.append("|".join(failed) if failed else "PASS")
    merged["r2e_gate_reason"] = reasons
    merged["r2e_gate_pass"] = merged["r2e_gate_reason"].eq("PASS")
    merged["eligibility_as_of_date"] = eligibility_as_of
    merged["fmdl5e_as_of_date"] = fmdl_as_of
    merged["fmdl5e_age_service_days"] = age
    merged["freshness_status"] = "STALE_BLOCKED" if stale else "CURRENT"
    merged["publication_eligible"] = merged["r2e_gate_pass"] & (not stale) & (not failures)
    merged["trade_authority"] = "NONE"

    future_market = int((pd.to_datetime(merged["market_latest_date"], errors="coerce") > pd.Timestamp(eligibility_as_of)).sum())
    future_fmdl = int((pd.to_datetime(merged["as_of_date_fmdl5e"], errors="coerce") > pd.Timestamp(eligibility_as_of)).sum()) if "as_of_date_fmdl5e" in merged else 0
    if future_market + future_fmdl:
        failures.append("FUTURE_FMDL5E_INFORMATION")

    universe = merged.loc[merged["r2e_gate_pass"]].copy().sort_values(
        ["avg_turnover_hkd_20d", "stock_code_5d"], ascending=[False, True]
    )
    exclusions = merged.loc[~merged["r2e_gate_pass"]].copy().sort_values("stock_code_5d")

    buy_eligible_count = int(merged["combined_status"].astype(str).str.startswith("BUY_ELIGIBLE").sum())
    sell_only_in_universe = int((universe["combined_status"] == "SELL_ONLY").sum())
    unknown_in_universe = int((universe["combined_status"] == "UNKNOWN_BLOCKED").sum())
    duplicate_count = int(merged["stock_code_5d"].duplicated().sum())
    reason_counts: dict[str, int] = {}
    for text in exclusions["r2e_gate_reason"].astype(str):
        for reason in text.split("|"):
            if reason and reason != "PASS":
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    quality = {
        "program_id": "HKCU-1",
        "phase": "R2E",
        "eligibility_as_of_date": eligibility_as_of,
        "fmdl5e_release_id": fmdl5e_decision.get("release_id"),
        "fmdl5e_as_of_date": fmdl_as_of,
        "fmdl5e_age_stock_connect_service_days": age,
        "maximum_allowed_fmdl5e_age_service_days": max_age,
        "fmdl5e_stale": stale,
        "eligibility_rows": int(len(e)),
        "fmdl5e_rows": int(len(s)),
        "union_rows": int(len(merged)),
        "buy_eligible_rows": buy_eligible_count,
        "missing_fmdl5e_coverage_count": int((merged["_merge"] == "left_only").sum()),
        "fmdl5e_without_current_eligibility_record_count": int((merged["_merge"] == "right_only").sum()),
        "provisional_investable_count": int(len(universe)),
        "excluded_count": int(len(exclusions)),
        "exclusion_reason_counts": reason_counts,
        "duplicate_security_count": duplicate_count,
        "sell_only_in_investable_count": sell_only_in_universe,
        "unknown_in_investable_count": unknown_in_universe,
        "future_information_count": future_market + future_fmdl,
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": "NONE",
    }
    zero_fail = duplicate_count or sell_only_in_universe or unknown_in_universe or quality["future_information_count"]
    if zero_fail:
        failures.append("ZERO_TOLERANCE_QUALITY_GATE")
    quality["hard_failures"] = sorted(set(failures))
    quality["status"] = "PASS" if not failures else "FAIL"

    if failures:
        status = "BLOCKED_SOURCE_OR_QUALITY"
    elif stale:
        status = "BLOCKED_STALE_FMDL5E"
    else:
        status = "PASS_CURRENT"
    decision = {
        "program_id": "HKCU-1",
        "phase": "R2E",
        "status": status,
        "publication_allowed": status == "PASS_CURRENT",
        "canonical_action": "ELIGIBLE_FOR_R2F" if status == "PASS_CURRENT" else "KEEP_PREVIOUS_CANONICAL_UNCHANGED",
        "eligibility_as_of_date": eligibility_as_of,
        "fmdl5e_as_of_date": fmdl_as_of,
        "fmdl5e_age_stock_connect_service_days": age,
        "provisional_investable_count": int(len(universe)),
        "hard_failures": sorted(set(failures)),
        "next_gate": contract["next_gate"] if status == "PASS_CURRENT" else "REFRESH_FMDL5E_THEN_RERUN_R2E",
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": "NONE",
    }
    return universe, exclusions, quality, decision


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--fmdl5e-screening", type=Path, required=True)
    p.add_argument("--fmdl5e-decision", type=Path, required=True)
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--as-of-date", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    eligibility = pd.read_csv(a.eligibility, dtype=str)
    screening = pd.read_csv(a.fmdl5e_screening, dtype={"stock_code_5d": str}, encoding="utf-8-sig")
    contract = _read_json(a.contract)
    universe, exclusions, quality, decision = build(
        eligibility, screening, _read_json(a.fmdl5e_decision), _read_json(a.calendar), contract, a.as_of_date
    )
    a.output_dir.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(a.output_dir / "HKCU1_POINT_IN_TIME_ELIGIBILITY.csv", index=False)
    universe.to_csv(a.output_dir / "HKCU1_R2E_INVESTABLE_UNIVERSE.csv", index=False, encoding="utf-8-sig")
    exclusions.to_csv(a.output_dir / "HKCU1_R2E_EXCLUSIONS.csv", index=False, encoding="utf-8-sig")
    (a.output_dir / "HKCU1_R2E_QUALITY_REPORT.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (a.output_dir / "HKCU1_R2E_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = [p for p in a.output_dir.iterdir() if p.is_file()]
    manifest = {
        "program_id": "HKCU-1", "phase": "R2E", "as_of_date": a.as_of_date,
        "files": {p.name: _hash(p) for p in files}, "trade_authority": "NONE"
    }
    (a.output_dir / "HKCU1_R2E_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["status"] in {"PASS_CURRENT", "BLOCKED_STALE_FMDL5E"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
