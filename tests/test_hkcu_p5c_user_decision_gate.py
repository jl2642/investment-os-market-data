from pathlib import Path
import json
import pandas as pd

from pipeline.hkcu_p5c_user_decision_gate import extract_hkex_close_prices, valuation_multiple

def test_extract_hkex_table_prices():
    html = """
    <html><body><table>
    <tr><th>Stock Code</th><th>Name</th><th>Previous Close</th><th>Closing Price</th><th>Volume</th></tr>
    <tr><td>00669</td><td>TECHTRONIC IND</td><td>130.0</td><td>131.2</td><td>1000</td></tr>
    <tr><td>01308</td><td>SITC</td><td>33.0</td><td>33.5</td><td>2000</td></tr>
    <tr><td>03698</td><td>HUISHANG BANK</td><td>4.5</td><td>4.6</td><td>3000</td></tr>
    </table></body></html>
    """
    targets={"HKEX:00669":"00669","HKEX:01308":"01308","HKEX:03698":"03698"}
    prices, diag = extract_hkex_close_prices(html, targets)
    assert prices == {"HKEX:00669":131.2,"HKEX:01308":33.5,"HKEX:03698":4.6}
    assert diag["methods"]

def test_valuation_multiple_hkd_and_usd():
    hkd=pd.Series({"security_id":"HKEX:03698","basis_value":12.5,"basis_currency":"HKD","fx_anchor":""})
    usd=pd.Series({"security_id":"HKEX:01308","basis_value":0.46,"basis_currency":"USD","fx_anchor":"7.80"})
    assert abs(valuation_multiple(hkd,5.0)-0.4)<1e-12
    assert abs(valuation_multiple(usd,35.88)-10.0)<1e-12

def test_contract_preserves_user_authority():
    c=json.loads(Path("config/hkcu_p5c_user_decision_gate_contract.json").read_text())
    p=c["decision_policy"]; b=c["phase_boundary"]
    assert p["technical_pass_may_substitute_user_approval"] is False
    assert p["silence_or_continue_command_is_trade_approval"] is False
    assert p["current_next_action"]=="EXPLICIT_USER_DECISION_REQUIRED"
    assert p["next_gate_only_after_explicit_eligible_decisions"]=="P5D_MANUAL_STAGED_EXECUTION_SUPPORT"
    assert b["user_trade_confirmation_record_authorized"] is False
    assert b["manual_execution_checklist_authorized"] is False
    assert b["target_portfolio_writeback_authorized"] is False
    assert b["order_creation_authorized"] is False
    assert b["trade_authority"]=="NONE"

def test_context_registry_complete():
    df=pd.read_csv("evidence/hkcu_p5c/HKCU_P5C_VALUATION_CONTEXT_20260807.csv",dtype={"stock_code_5d":str},keep_default_na=False)
    assert set(df.security_id)=={"HKEX:00669","HKEX:01308","HKEX:03698"}
    assert (pd.to_numeric(df["history_median"])>0).all()
    assert (pd.to_numeric(df["peer_or_current_reference"])>0).all()
    assert df["context_source_url"].str.startswith("https://").all()
