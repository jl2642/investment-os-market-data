#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

PROGRAM_ID="HKCU-P5C"
TRADE_AUTHORITY="NONE"

def read_json(p:Path): return json.loads(p.read_text(encoding="utf-8"))

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",default=".")
    ap.add_argument("--p5b-dir",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    root=Path(a.repo_root).resolve(); out=Path(a.output).resolve()
    contract=read_json(root/"config/hkcu_p5c_user_decision_gate_contract.json")
    prefix=contract["output_prefix"]; policy=contract["decision_policy"]; acc=contract["acceptance"]
    decision=read_json(out/f"{prefix}_DECISION.json")
    quality=read_json(out/f"{prefix}_QUALITY.json")
    packet=pd.read_csv(out/f"{prefix}_DECISION_PACKET.csv",dtype={"stock_code_5d":str},keep_default_na=False)
    prices=pd.read_csv(out/f"{prefix}_OFFICIAL_PRICE_SURFACE.csv",dtype={"stock_code_5d":str},keep_default_na=False)
    errors=[]
    if decision.get("status")!=acc["pass_status"]: errors.append("DECISION_STATUS")
    if decision.get("gate_state")!=policy["current_gate_state_on_pass"]: errors.append("GATE_STATE")
    if decision.get("current_next_action")!=policy["current_next_action"]: errors.append("NEXT_ACTION")
    if decision.get("conditional_next_gate_after_explicit_user_decisions")!=policy["next_gate_only_after_explicit_eligible_decisions"]: errors.append("CONDITIONAL_NEXT_GATE")
    if len(packet)!=acc["decision_packet_security_count"]: errors.append("PACKET_COUNT")
    eligible=packet[packet["decision_eligibility"].astype(str).eq(policy["eligible_state"])]
    deferred=packet[packet["decision_eligibility"].astype(str).eq(policy["deferred_state"])]
    if len(eligible)!=acc["user_decision_eligible_count"]: errors.append("ELIGIBLE_COUNT")
    if len(deferred)!=acc["deferred_not_eligible_count"]: errors.append("DEFERRED_COUNT")
    if set(eligible["security_id"])!=set(contract["price_surface"]["required_advanced_securities"]): errors.append("ELIGIBLE_SET")
    if set(deferred["security_id"])!={"HKEX:02698"}: errors.append("DEFERRED_SET")
    if packet["user_decision"].astype(str).str.strip().ne("").any(): errors.append("PREPOPULATED_USER_DECISION")
    if packet["user_modified_weight"].astype(str).str.strip().ne("").any(): errors.append("PREPOPULATED_MODIFIED_WEIGHT")
    if packet["user_trade_confirmation_recorded"].astype(str).str.lower().isin(["true","1","yes"]).any(): errors.append("USER_CONFIRMATION")
    for col in ("manual_execution_checklist_produced","target_writeback","portfolio_mutation"):
        if packet[col].astype(str).str.lower().isin(["true","1","yes"]).any(): errors.append(col.upper())
    if pd.to_numeric(packet["orders_created"],errors="coerce").fillna(0).sum()!=0: errors.append("ORDERS")
    if not packet["trade_authority"].astype(str).eq(TRADE_AUTHORITY).all(): errors.append("AUTHORITY")
    if len(prices)!=3 or not prices["price_source"].astype(str).eq(contract["price_surface"]["required_source"]).all(): errors.append("PRICE_SOURCE")
    if not prices["source_url"].astype(str).eq(contract["price_surface"]["url"]).all(): errors.append("PRICE_URL")
    if not prices["price_date"].astype(str).eq(contract["price_surface"]["price_date"]).all(): errors.append("PRICE_DATE")
    if pd.to_numeric(prices["close_hkd"],errors="coerce").isna().any(): errors.append("PRICE_MISSING")
    if (pd.to_numeric(prices["close_hkd"],errors="coerce")<=0).any(): errors.append("PRICE_NONPOSITIVE")
    vals=pd.to_numeric(eligible["valuation_multiple"],errors="coerce")
    if vals.isna().any() or (vals<=0).any(): errors.append("VALUATION")
    for c in ("history_context","peer_context","context_source_url","calculation_note"):
        if eligible[c].astype(str).str.strip().eq("").any(): errors.append("CONTEXT_"+c.upper())
    expected_choices="|".join(policy["allowed_user_choices"])
    if not eligible["available_user_choices"].astype(str).eq(expected_choices).all(): errors.append("USER_CHOICES")
    if quality.get("technical_pass_substitutes_user_approval") is not False: errors.append("TECH_PASS_POLICY")
    if quality.get("third_party_price_fallback_used") is not False: errors.append("THIRD_PARTY_PRICE")
    if quality.get("ambiguous_date_price_used") is not False: errors.append("AMBIGUOUS_PRICE")
    if decision.get("user_decision_recorded_count")!=0: errors.append("DECISION_RECORDED")
    if decision.get("user_trade_confirmation_recorded") is not False: errors.append("CONFIRMATION_RECORDED")
    if decision.get("manual_execution_checklist_produced") is not False: errors.append("CHECKLIST")
    if decision.get("target_portfolio_writeback") is not False: errors.append("WRITEBACK")
    if decision.get("orders_created")!=0: errors.append("DECISION_ORDERS")
    if decision.get("trade_authority")!=TRADE_AUTHORITY: errors.append("DECISION_AUTHORITY")
    result={"program_id":PROGRAM_ID,"status":"PASS" if not errors else "FAIL","operational_status":decision.get("status"),"gate_state":decision.get("gate_state"),"decision_packet_security_count":len(packet),"user_decision_eligible_count":len(eligible),"deferred_not_eligible_count":len(deferred),"user_decision_recorded_count":0,"price_source":decision.get("price_source"),"errors":errors,"trade_authority":TRADE_AUTHORITY}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if not errors else 2
if __name__=="__main__": raise SystemExit(main())
