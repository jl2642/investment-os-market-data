from __future__ import annotations

import json

import pandas as pd

from scripts.fmdl3cb_core import (
    FormulaParser,
    build_period_inputs,
    evaluate_factors_for_period,
    evaluate_formula,
    infer_sector_profile,
)


def fact(symbol, line, period, value, fiscal, available, eligible=True, quality="VALID"):
    return {
        "symbol": symbol,
        "line_item_id": line,
        "period_end": period,
        "normalized_value": value,
        "fiscal_period_type": fiscal,
        "available_from": available,
        "record_quality": quality,
        "decision_grade_eligible": eligible,
        "normalized_fact_id": f"{symbol}-{line}-{period}",
    }


def status(symbol, period, available, restatement="ORIGINAL_ONLY"):
    return {
        "symbol": symbol,
        "report_period_end": period,
        "restatement_status": restatement,
        "authoritative_available_from": available,
    }


def test_formula_parser_nested_expression():
    tree = FormulaParser.from_text("DIVIDE(SUBTRACT(revenue_ttm,cogs_ttm),revenue_ttm)").parse()
    assert evaluate_formula(tree, {"revenue_ttm": 100.0, "cogs_ttm": 60.0}) == 0.4


def test_ttm_and_average_balance_are_pit_constructed():
    symbol = "600000.SH"
    rows = [
        fact(symbol, "revenue", "2024-03-31", 20, "Q1", "2024-04-30T09:30:00+08:00"),
        fact(symbol, "revenue", "2024-12-31", 100, "FY", "2025-03-31T09:30:00+08:00"),
        fact(symbol, "revenue", "2025-03-31", 30, "Q1", "2025-04-30T09:30:00+08:00"),
        fact(symbol, "total_assets", "2024-03-31", 200, "Q1", "2024-04-30T09:30:00+08:00"),
        fact(symbol, "total_assets", "2025-03-31", 240, "Q1", "2025-04-30T09:30:00+08:00"),
    ]
    facts = pd.DataFrame(rows)
    statuses = pd.DataFrame([
        status(symbol, "2024-03-31", "2024-04-30T09:30:00+08:00"),
        status(symbol, "2024-12-31", "2025-03-31T09:30:00+08:00"),
        status(symbol, "2025-03-31", "2025-04-30T09:30:00+08:00"),
    ])
    out = build_period_inputs(facts, statuses, {"revenue_ttm": "revenue"}, {"total_assets": "total_assets"})
    q1 = out[out["period_end"].eq("2025-03-31")].iloc[0]
    assert q1["revenue_ttm"] == 110.0
    assert q1["avg_total_assets"] == 220.0
    available = json.loads(q1["input_available_from_json"])
    assert available["revenue_ttm"].startswith("2025-04-30")


def test_sector_profile_requires_strict_financial_signature():
    bank = pd.DataFrame([
        fact("600000.SH", "net_interest_income", "2024-12-31", 10, "FY", "2025-03-31T09:30:00+08:00"),
        fact("600000.SH", "loans_advances", "2024-12-31", 100, "FY", "2025-03-31T09:30:00+08:00"),
    ])
    industrial_with_loans = pd.DataFrame([
        fact("000333.SZ", "revenue", "2024-12-31", 100, "FY", "2025-03-31T09:30:00+08:00"),
        fact("000333.SZ", "cogs", "2024-12-31", 60, "FY", "2025-03-31T09:30:00+08:00"),
        fact("000333.SZ", "loans_advances", "2024-12-31", 2, "FY", "2025-03-31T09:30:00+08:00"),
    ])
    insurer_override = pd.DataFrame([
        fact("601318.SH", "revenue", "2024-12-31", 100, "FY", "2025-03-31T09:30:00+08:00")
    ])
    unknown = pd.DataFrame([fact("430000.BJ", "unmapped", "2024-12-31", 10, "FY", "2025-03-31T09:30:00+08:00")])
    assert infer_sector_profile(bank) == "BANK"
    assert infer_sector_profile(industrial_with_loans) == "GENERAL_NON_FINANCIAL"
    assert infer_sector_profile(insurer_override) == "INSURANCE"
    assert infer_sector_profile(unknown) == "UNRESOLVED"


def test_missing_debt_component_is_not_zero_filled():
    period = pd.Series({
        "symbol": "000001.SZ",
        "period_end": "2024-12-31",
        "fiscal_period_type": "FY",
        "parent_equity": 100.0,
        "short_term_debt": 10.0,
        "long_term_debt": None,
        "bonds_payable": 5.0,
        "input_states_json": json.dumps({
            "parent_equity": "VALID",
            "short_term_debt": "VALID",
            "long_term_debt": "MISSING_REQUIRED_INPUT",
            "bonds_payable": "VALID",
        }),
        "input_available_from_json": json.dumps({
            "parent_equity": "2025-03-31T09:30:00+08:00",
            "short_term_debt": "2025-03-31T09:30:00+08:00",
            "long_term_debt": None,
            "bonds_payable": "2025-03-31T09:30:00+08:00",
        }),
        "input_fact_ids_json": json.dumps({
            "parent_equity": ["eq"], "short_term_debt": ["sd"], "long_term_debt": [], "bonds_payable": ["bd"]
        }),
    })
    dictionary = pd.DataFrame([{
        "factor_id": "FIN_INTEREST_BEARING_DEBT_TO_EQUITY",
        "factor_name": "Debt to equity",
        "family_id": "BALANCE_SHEET",
        "formula": "DIVIDE(ADD(ADD(short_term_debt,long_term_debt),bonds_payable),parent_equity)",
        "required_inputs": "short_term_debt|long_term_debt|bonds_payable|parent_equity",
        "output_unit": "RATIO",
        "economic_direction": "LOWER_BETTER",
        "applicable_sector_profiles": "GENERAL_NON_FINANCIAL",
        "period_basis": "POINT_IN_TIME",
        "build_state": "MVP_REQUIRED",
        "denominator_rule": "POSITIVE_PARENT_EQUITY",
        "comparability_requirement": "NOT_REQUIRED",
        "warning_policy": "NONE",
        "ranking_posture": "ELIGIBLE_WHEN_VALID",
        "trade_authority": "NONE",
    }])
    result = evaluate_factors_for_period(period, dictionary, "GENERAL_NON_FINANCIAL").iloc[0]
    assert result["quality_state"] == "MISSING_REQUIRED_INPUT"
    assert pd.isna(result["factor_value"])


def test_bank_does_not_receive_industrial_gross_margin():
    period = pd.Series({
        "symbol": "600000.SH", "period_end": "2024-12-31", "fiscal_period_type": "FY",
        "revenue_ttm": 100.0, "cogs_ttm": 60.0,
        "input_states_json": json.dumps({"revenue_ttm": "VALID", "cogs_ttm": "VALID"}),
        "input_available_from_json": json.dumps({"revenue_ttm": "2025-03-31T09:30:00+08:00", "cogs_ttm": "2025-03-31T09:30:00+08:00"}),
        "input_fact_ids_json": json.dumps({"revenue_ttm": ["r"], "cogs_ttm": ["c"]}),
    })
    dictionary = pd.DataFrame([{
        "factor_id": "FIN_GROSS_MARGIN_TTM", "factor_name": "Gross margin", "family_id": "PROFITABILITY",
        "formula": "DIVIDE(SUBTRACT(revenue_ttm,cogs_ttm),revenue_ttm)", "required_inputs": "revenue_ttm|cogs_ttm",
        "output_unit": "RATIO", "economic_direction": "HIGHER_BETTER", "applicable_sector_profiles": "GENERAL_NON_FINANCIAL",
        "period_basis": "TTM", "build_state": "MVP_REQUIRED", "denominator_rule": "POSITIVE_REVENUE",
        "comparability_requirement": "REQUIRED", "warning_policy": "NONE", "ranking_posture": "ELIGIBLE_WHEN_VALID", "trade_authority": "NONE"
    }])
    result = evaluate_factors_for_period(period, dictionary, "BANK").iloc[0]
    assert result["quality_state"] == "NOT_APPLICABLE_SECTOR"
    assert pd.isna(result["factor_value"])


def test_comparability_bridge_blocks_growth_input():
    symbol = "000001.SZ"
    facts = pd.DataFrame([
        fact(symbol, "revenue", "2023-12-31", 100, "FY", "2024-03-31T09:30:00+08:00"),
        fact(symbol, "revenue", "2024-12-31", 120, "FY", "2025-03-31T09:30:00+08:00"),
    ])
    statuses = pd.DataFrame([
        status(symbol, "2023-12-31", "2024-03-31T09:30:00+08:00"),
        status(symbol, "2024-12-31", "2025-03-31T09:30:00+08:00"),
    ])
    bridge = pd.DataFrame([{
        "symbol": symbol, "line_item_id": "revenue", "fiscal_period_type": "FY",
        "current_period": "2024-12-31", "prior_period": "2023-12-31",
        "comparison_status": "NOT_COMPARABLE"
    }])
    out = build_period_inputs(facts, statuses, {"revenue_ttm": "revenue"}, {}, bridge)
    current = out[out["period_end"].eq("2024-12-31")].iloc[0]
    states = json.loads(current["input_states_json"])
    assert states["prior_revenue_same_period"] == "NON_COMPARABLE_INPUT"
