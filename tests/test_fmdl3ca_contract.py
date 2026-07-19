import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "config/fmdl3c_factor_contract.json").read_text(encoding="utf-8"))
with (ROOT / "config/fmdl3c_factor_dictionary.csv").open(encoding="utf-8-sig", newline="") as handle:
    ROWS = list(csv.DictReader(handle))
FACTORS = {item["factor_id"]: item for item in ROWS}


def profiles(factor_id):
    return FACTORS[factor_id]["applicable_sector_profiles"].split("|")


def test_factor_set_is_frozen_and_unique():
    assert len(FACTORS) == 29
    assert len(ROWS) == len(FACTORS)
    assert CONTRACT["factor_dictionary"]["factor_count"] == 29
    assert CONTRACT["architecture_state"] == "FROZEN_FOR_FMDL3C_B_EXECUTION"


def test_dictionary_contract_columns_and_authority():
    assert list(ROWS[0]) == CONTRACT["factor_dictionary"]["required_columns"]
    assert all(row["trade_authority"] == "NONE" for row in ROWS)


def test_financial_sector_routing_is_not_industrial_fallback():
    assert profiles("FIN_ROE_AVG_PARENT_EQUITY_TTM") == ["GENERAL_NON_FINANCIAL", "BANK", "INSURANCE", "SECURITIES_AND_BROKERAGE"]
    assert profiles("FIN_CURRENT_RATIO") == ["GENERAL_NON_FINANCIAL"]
    assert profiles("FIN_CFO_TO_PARENT_NI_TTM") == ["GENERAL_NON_FINANCIAL"]
    assert "UNRESOLVED" not in profiles("FIN_GROSS_MARGIN_TTM")


def test_growth_sign_and_comparability_controls_are_explicit():
    assert FACTORS["FIN_PARENT_NI_YOY"]["denominator_rule"] == "SAME_SIGN_POSITIVE_BASE"
    assert FACTORS["FIN_PARENT_NI_YOY"]["comparability_requirement"] == "REQUIRED"
    assert FACTORS["FIN_PARENT_NI_CAGR_3Y"]["denominator_rule"] == "POSITIVE_START_AND_END"


def test_deferred_inputs_are_not_faked_in_mvp():
    deferred = {item["factor_id"] for item in CONTRACT["deferred_factor_policy"]["deferred_factors"]}
    assert {"FIN_ROIC_TTM", "FIN_NET_DEBT_EBITDA", "FIN_INTEREST_COVERAGE", "FIN_ROIC_WACC_SPREAD", "FIN_DIVIDEND_STABILITY"}.issubset(deferred)
    assert deferred.isdisjoint(FACTORS)


def test_no_score_or_trade_authority():
    assert "CROSS_SECTIONAL_SCORE" in CONTRACT["scope"]["excluded_domains"]
    assert CONTRACT["trade_authority"] == "NONE"
    assert all(item["trade_authority"] == "NONE" for item in ROWS)
