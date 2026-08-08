from pathlib import Path
import json
import pandas as pd

from pipeline.hkcu_p5c_user_decision_gate import extract_hkex_close_prices, extract_hkma_fx, valuation_multiple


def test_extract_hkex_two_line_daily_quotation_prices_and_ignore_short_sell_rows():
    html = """
    <html><body><pre>
                                      QUOTATIONS
     CODE  NAME OF STOCK    CUR PRV.CLO./    ASK/    HIGH/      SHARES TRADED/
                                CLOSING      BID     LOW        TURNOVER ($)
       669 TECHTRONIC IND   HKD  130.00   132.00   133.00            6,222,546
                                 131.20   131.10   129.00          910,771,539
      1308 SITC             HKD   33.00    33.70    34.00              511,000
                                  33.50    33.45    32.80           19,631,120
      3698 HUISHANG BANK    HKD    4.50     4.65     4.70              350,000
                                   4.60     4.58     4.45            1,687,900
    SALES RECORDS FOR ALL STOCKS
      CODE  NAME OF STOCK         (SH)              ($)
       669 TECHTRONIC IND        1,000,000         146,453,000
      1308 SITC                    511,000          19,631,120
      3698 HUISHANG BANK           350,000           1,687,900
    </pre></body></html>
    """
    targets = {"HKEX:00669": "00669", "HKEX:01308": "01308", "HKEX:03698": "03698"}
    prices, diag = extract_hkex_close_prices(html, targets)
    assert prices == {"HKEX:00669": 131.2, "HKEX:01308": 33.5, "HKEX:03698": 4.6}
    first = diag["methods"][0]
    assert first["method"] == "_quotation_two_line_close_candidates"
    assert first["diagnostics"]["matching_quote_pairs"]["HKEX:00669"]["parsed_close"] == 131.2
    assert len(first["diagnostics"]["all_code_occurrences"]["HKEX:00669"]) == 2


def test_extract_hkex_table_prices_fallback():
    html = """
    <html><body><table>
    <tr><th>Stock Code</th><th>Name</th><th>Previous Close</th><th>Closing Price</th><th>Volume</th></tr>
    <tr><td>00669</td><td>TECHTRONIC IND</td><td>130.0</td><td>131.2</td><td>1000</td></tr>
    <tr><td>01308</td><td>SITC</td><td>33.0</td><td>33.5</td><td>2000</td></tr>
    <tr><td>03698</td><td>HUISHANG BANK</td><td>4.5</td><td>4.6</td><td>3000</td></tr>
    </table></body></html>
    """
    targets = {"HKEX:00669": "00669", "HKEX:01308": "01308", "HKEX:03698": "03698"}
    prices, _ = extract_hkex_close_prices(html, targets)
    assert prices == {"HKEX:00669": 131.2, "HKEX:01308": 33.5, "HKEX:03698": 4.6}


def test_extract_hkma_same_date_fx():
    payload = {"result": {"records": [
        {"end_of_day": "2026-08-07", "usd": 7.81, "cny": 1.155},
        {"end_of_day": "2026-08-06", "usd": 7.80, "cny": 1.154},
    ]}}
    assert extract_hkma_fx(payload, "2026-08-07", ["usd", "cny"]) == {"usd": 7.81, "cny": 1.155}
    assert extract_hkma_fx(payload, "2026-08-08", ["usd", "cny"]) == {}


def test_valuation_multiple_uses_official_fx_series():
    hkd = pd.Series({"security_id": "X", "basis_value": 12.5, "basis_currency": "HKD", "fx_series": ""})
    usd = pd.Series({"security_id": "Y", "basis_value": 0.46, "basis_currency": "USD", "fx_series": "usd"})
    cny = pd.Series({"security_id": "Z", "basis_value": 11.2, "basis_currency": "CNY", "fx_series": "cny"})
    rates = {"usd": 7.8, "cny": 1.15}
    assert abs(valuation_multiple(hkd, 5.0, rates) - 0.4) < 1e-12
    assert abs(valuation_multiple(usd, 35.88, rates) - 10.0) < 1e-12
    assert abs(valuation_multiple(cny, 5.152, rates) - 0.4) < 1e-12


def test_contract_preserves_user_authority_and_current_basis_policy():
    c = json.loads(Path("config/hkcu_p5c_user_decision_gate_contract.json").read_text())
    p = c["decision_policy"]
    b = c["phase_boundary"]
    v = c["valuation_policy"]
    fx = c["fx_surface"]
    assert p["technical_pass_may_substitute_user_approval"] is False
    assert p["silence_or_continue_command_is_trade_approval"] is False
    assert p["current_next_action"] == "EXPLICIT_USER_DECISION_REQUIRED"
    assert p["next_gate_only_after_explicit_eligible_decisions"] == "P5D_MANUAL_STAGED_EXECUTION_SUPPORT"
    assert b["user_trade_confirmation_record_authorized"] is False
    assert b["manual_execution_checklist_authorized"] is False
    assert b["target_portfolio_writeback_authorized"] is False
    assert b["order_creation_authorized"] is False
    assert b["trade_authority"] == "NONE"
    assert v["huishang_primary_metric"] == "P_B_Q1_COMMON_EQUITY_PROXY"
    assert v["third_party_history_context_may_replace_official_current_denominator"] is False
    assert v["fixed_valuation_ceiling_authorized"] is False
    assert fx["required_series"] == ["usd", "cny"]
    assert fx["stale_fx_allowed"] is False


def test_context_registry_pins_official_current_denominators():
    df = pd.read_csv("evidence/hkcu_p5c/HKCU_P5C_VALUATION_CONTEXT_20260807.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    assert set(df.security_id) == {"HKEX:00669", "HKEX:01308", "HKEX:03698"}
    assert (pd.to_numeric(df["history_median"]) > 0).all()
    assert (pd.to_numeric(df["peer_or_current_reference"]) > 0).all()
    assert df["basis_source_url"].str.startswith("https://").all()
    assert df["fx_source_url"].str.contains("api.hkma.gov.hk", regex=False).all()
    hu = df[df.security_id.eq("HKEX:03698")].iloc[0]
    assert hu.valuation_metric == "P_B_Q1_COMMON_EQUITY_PROXY"
    assert hu.basis_currency == "CNY"
    assert hu.fx_series == "cny"
    assert "2026042801350.pdf" in hu.basis_source_url
    assert abs(float(hu.basis_value) - ((178017 - 20000 - 2760) / 13890)) < 1e-10
