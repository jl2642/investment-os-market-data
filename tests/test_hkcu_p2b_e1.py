from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def test_e1_evidence_contract_counts():
    c=json.loads((ROOT/"config/hkcu_p2b_e1_evidence_contract.json").read_text())
    assert c["expected_counts"]["accepted_security_count"]==77
    assert c["expected_counts"]["transaction_tax_rows_to_close"]==77
    assert c["expected_counts"]["ah_leads_to_resolve"]==15
    assert c["expected_counts"]["expected_true_ah_pairs"]==13
    assert c["expected_counts"]["expected_not_applicable_ah_leads"]==2
    assert c["trade_authority"]=="NONE"

def test_ah_registry_is_explicit_and_primary():
    x=pd.read_csv(ROOT/"evidence/hkcu_p2b/HKCU_P2B_AH_PAIR_REGISTRY_20260807.csv",dtype={"a_code":str,"h_code":str})
    assert len(x)==15
    assert x["security_id"].is_unique
    assert (x["pair_status"]=="TRUE_AH_PAIR").sum()==13
    assert (x["pair_status"]!="TRUE_AH_PAIR").sum()==2
    assert x["source_url"].str.startswith("https://").all()
    assert "HKEX:06990" in set(x.loc[x["pair_status"]!="TRUE_AH_PAIR","security_id"])
    assert "HKEX:02799" in set(x.loc[x["pair_status"]!="TRUE_AH_PAIR","security_id"])

def test_common_market_rules_no_invented_brokerage():
    x=json.loads((ROOT/"evidence/hkcu_p2b/HKCU_P2B_COMMON_MARKET_RULES_20260807.json").read_text())
    assert x["status"]=="PRIMARY_EVIDENCE_COMPLETE_WITH_VARIABLE_BROKERAGE"
    assert x["execution_model"]["brokerage_component"]=="VARIABLE_UNKNOWN_UNTIL_BROKER_TARIFF_IS_SUPPLIED"
    assert x["execution_model"]["capital_gains_iit_current_profile"]=="EXEMPT_THROUGH_2027-12-31"
    assert x["trade_authority"]=="NONE"
