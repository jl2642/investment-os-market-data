#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PROGRAM_ID = "HKCU-P5C"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p5b-dir", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    root = Path(a.repo_root).resolve()
    out = Path(a.output).resolve()
    contract = read_json(root / "config/hkcu_p5c_user_decision_gate_contract.json")
    prefix = contract["output_prefix"]
    policy = contract["decision_policy"]
    acc = contract["acceptance"]
    vp = contract["valuation_policy"]

    decision = read_json(out / f"{prefix}_DECISION.json")
    quality = read_json(out / f"{prefix}_QUALITY.json")
    packet = pd.read_csv(out / f"{prefix}_DECISION_PACKET.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    prices = pd.read_csv(out / f"{prefix}_OFFICIAL_PRICE_SURFACE.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    fx = pd.read_csv(out / f"{prefix}_OFFICIAL_FX_SURFACE.csv", keep_default_na=False)
    errors: list[str] = []

    if decision.get("status") != acc["pass_status"]:
        errors.append("DECISION_STATUS")
    if decision.get("gate_state") != policy["current_gate_state_on_pass"]:
        errors.append("GATE_STATE")
    if decision.get("current_next_action") != policy["current_next_action"]:
        errors.append("NEXT_ACTION")
    if decision.get("conditional_next_gate_after_explicit_user_decisions") != policy["next_gate_only_after_explicit_eligible_decisions"]:
        errors.append("CONDITIONAL_NEXT_GATE")
    if len(packet) != acc["decision_packet_security_count"]:
        errors.append("PACKET_COUNT")

    eligible = packet[packet["decision_eligibility"].astype(str).eq(policy["eligible_state"])]
    deferred = packet[packet["decision_eligibility"].astype(str).eq(policy["deferred_state"])]
    if len(eligible) != acc["user_decision_eligible_count"]:
        errors.append("ELIGIBLE_COUNT")
    if len(deferred) != acc["deferred_not_eligible_count"]:
        errors.append("DEFERRED_COUNT")
    if set(eligible["security_id"]) != set(contract["price_surface"]["required_advanced_securities"]):
        errors.append("ELIGIBLE_SET")
    if set(deferred["security_id"]) != {"HKEX:02698"}:
        errors.append("DEFERRED_SET")
    if packet["user_decision"].astype(str).str.strip().ne("").any():
        errors.append("PREPOPULATED_USER_DECISION")
    if packet["user_modified_weight"].astype(str).str.strip().ne("").any():
        errors.append("PREPOPULATED_MODIFIED_WEIGHT")
    if truthy(packet["user_trade_confirmation_recorded"]).any():
        errors.append("USER_CONFIRMATION")
    for col in ("manual_execution_checklist_produced", "target_writeback", "portfolio_mutation"):
        if truthy(packet[col]).any():
            errors.append(col.upper())
    if pd.to_numeric(packet["orders_created"], errors="coerce").fillna(0).sum() != 0:
        errors.append("ORDERS")
    if not packet["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all():
        errors.append("AUTHORITY")

    pc = contract["price_surface"]
    if len(prices) != acc["official_price_count"]:
        errors.append("PRICE_COUNT")
    if not prices["price_source"].astype(str).eq(pc["required_source"]).all():
        errors.append("PRICE_SOURCE")
    if not prices["source_url"].astype(str).eq(pc["url"]).all():
        errors.append("PRICE_URL")
    if not prices["price_date"].astype(str).eq(pc["price_date"]).all():
        errors.append("PRICE_DATE")
    pvals = pd.to_numeric(prices["close_hkd"], errors="coerce")
    if pvals.isna().any() or (pvals <= 0).any() or (pvals > 5000).any():
        errors.append("PRICE_VALUES")

    fc = contract["fx_surface"]
    if len(fx) != acc["official_fx_series_count"]:
        errors.append("FX_COUNT")
    if set(fx["series"].astype(str)) != set(fc["required_series"]):
        errors.append("FX_SERIES")
    if not fx["fx_source"].astype(str).eq(fc["required_source"]).all():
        errors.append("FX_SOURCE")
    if not fx["source_url"].astype(str).eq(fc["url"]).all():
        errors.append("FX_URL")
    if not fx["fx_date"].astype(str).eq(fc["fx_date"]).all():
        errors.append("FX_DATE")
    fvals = pd.to_numeric(fx["hkd_per_unit_foreign_currency"], errors="coerce")
    if fvals.isna().any() or (fvals <= 0).any():
        errors.append("FX_VALUES")

    vals = pd.to_numeric(eligible["valuation_multiple"], errors="coerce")
    if vals.isna().any() or (vals <= 0).any():
        errors.append("VALUATION")
    for col in ("earnings_or_book_basis", "basis_source_url", "basis_as_of", "fx_series", "fx_source_url", "history_context", "peer_context", "context_source_url", "calculation_note"):
        if eligible[col].astype(str).str.strip().eq("").any():
            errors.append("CONTEXT_" + col.upper())
    if not eligible["basis_source_url"].astype(str).str.startswith("https://").all():
        errors.append("BASIS_SOURCE_URL")
    if not eligible["fx_source_url"].astype(str).eq(fc["url"]).all():
        errors.append("PACKET_FX_SOURCE")
    if not eligible["fx_date"].astype(str).eq(fc["fx_date"]).all():
        errors.append("PACKET_FX_DATE")
    if pd.to_numeric(eligible["fx_rate_hkd_per_unit"], errors="coerce").isna().any():
        errors.append("PACKET_FX_RATE")

    hu = eligible[eligible["security_id"].eq("HKEX:03698")]
    if len(hu) != 1 or hu.iloc[0]["valuation_metric"] != vp["huishang_primary_metric"]:
        errors.append("HUISHANG_METRIC")
    if len(hu) == 1:
        h = hu.iloc[0]
        if str(h["basis_currency"]).upper() != "CNY" or str(h["fx_series"]).lower() != "cny":
            errors.append("HUISHANG_CURRENCY")
        if "2026042801350.pdf" not in str(h["basis_source_url"]):
            errors.append("HUISHANG_Q1_LINEAGE")
        if not (0.1 < float(h["valuation_multiple"]) < 1.5):
            errors.append("HUISHANG_PB_SANITY")

    expected_choices = "|".join(policy["allowed_user_choices"])
    if not eligible["available_user_choices"].astype(str).eq(expected_choices).all():
        errors.append("USER_CHOICES")
    if quality.get("technical_pass_substitutes_user_approval") is not False:
        errors.append("TECH_PASS_POLICY")
    if quality.get("third_party_price_fallback_used") is not False:
        errors.append("THIRD_PARTY_PRICE")
    if quality.get("third_party_fx_fallback_used") is not False:
        errors.append("THIRD_PARTY_FX")
    if quality.get("stale_fx_used") is not False:
        errors.append("STALE_FX")
    if quality.get("third_party_history_context_replaces_official_current_denominator") is not False:
        errors.append("CURRENT_DENOMINATOR_POLICY")
    if quality.get("fixed_valuation_ceiling_used") is not False:
        errors.append("FIXED_CEILING")
    if decision.get("user_decision_recorded_count") != 0:
        errors.append("DECISION_RECORDED")
    if decision.get("user_trade_confirmation_recorded") is not False:
        errors.append("CONFIRMATION_RECORDED")
    if decision.get("manual_execution_checklist_produced") is not False:
        errors.append("CHECKLIST")
    if decision.get("target_portfolio_writeback") is not False:
        errors.append("WRITEBACK")
    if decision.get("orders_created") != 0:
        errors.append("DECISION_ORDERS")
    if decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("DECISION_AUTHORITY")

    result = {
        "program_id": PROGRAM_ID,
        "status": "PASS" if not errors else "FAIL",
        "operational_status": decision.get("status"),
        "gate_state": decision.get("gate_state"),
        "decision_packet_security_count": len(packet),
        "user_decision_eligible_count": len(eligible),
        "deferred_not_eligible_count": len(deferred),
        "user_decision_recorded_count": 0,
        "price_source": decision.get("price_source"),
        "fx_source": decision.get("fx_source"),
        "errors": errors,
        "trade_authority": TRADE_AUTHORITY,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
