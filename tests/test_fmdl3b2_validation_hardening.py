import pandas as pd

from scripts import fmdl3b2_validation_hardening as hardening


def normalized_frame(symbol, period, values):
    rows = []
    for line_item_id, value in values.items():
        rows.append({
            "symbol": symbol,
            "period_end": period,
            "line_item_id": line_item_id,
            "normalized_value": value,
            "decision_grade_eligible": True,
            "record_quality": "VALIDATED",
            "comparison_status": "comparable",
            "model_treatment": "USE",
            "normalization_note": "",
        })
    return pd.DataFrame(rows)


def empty_flags():
    return pd.DataFrame(columns=["flag_id", "severity", "entity", "period", "area", "issue", "impact", "recommended_fix", "source_id", "status"])


def test_cash_flow_no_fx_variant_becomes_controlled_and_downgrades_facts():
    symbol = "002211.SZ"
    period = "2024-09-30"
    values = {"cfo": -14_248_745.31, "cfi": -3_016_769.54, "cff": -2_683_068.38, "fx_cash_effect": 29_773.62, "net_change_cash": -19_948_583.23, "beginning_cash": 50_439_526.17, "ending_cash": 30_490_942.94}
    normalized = normalized_frame(symbol, period, values)
    checks = pd.DataFrame([
        {"area": "cash_flow", "period": period, "test": f"{symbol}: CFO+CFI+CFF+FX = net change cash", "expected_value": values["net_change_cash"], "observed_value": values["cfo"] + values["cfi"] + values["cff"] + values["fx_cash_effect"], "variance": values["fx_cash_effect"], "result": "FAIL", "source_id": "MULTI_SOURCE", "notes": ""},
        {"area": "cash_flow", "period": period, "test": f"{symbol}: beginning cash + net change = ending cash", "expected_value": values["ending_cash"], "observed_value": values["beginning_cash"] + values["net_change_cash"], "variance": 0, "result": "PASS", "source_id": "MULTI_SOURCE", "notes": ""},
    ])
    normalized, checks, flags, evidence = hardening.harden_statement_validation(normalized, checks, empty_flags(), balance_relative_tolerance=1e-6, cash_relative_tolerance=1e-6)
    assert checks.iloc[0]["result"] == hardening.CONTROLLED_RESULT
    assert evidence[0]["reason"] == "NET_CHANGE_MATCHES_CFO_CFI_CFF_WITH_SEPARATELY_REPORTED_FX"
    affected = normalized[normalized.line_item_id.isin(["fx_cash_effect", "net_change_cash"])]
    assert not affected.decision_grade_eligible.any()
    assert set(affected.record_quality) == {hardening.CONTROLLED_FLAG_STATUS}
    assert len(flags) == 1


def test_cash_flow_no_cff_variant_becomes_controlled():
    symbol = "002052.SZ"
    period = "2025-03-31"
    values = {"cfo": -230_643_912.19, "cfi": -389_083.60, "cff": 1_151_765.30, "fx_cash_effect": 3_286_813.65, "net_change_cash": -227_746_182.14, "beginning_cash": 327_390_203.04, "ending_cash": 99_644_020.90}
    normalized = normalized_frame(symbol, period, values)
    checks = pd.DataFrame([
        {"area": "cash_flow", "period": period, "test": f"{symbol}: CFO+CFI+CFF+FX = net change cash", "expected_value": values["net_change_cash"], "observed_value": values["cfo"] + values["cfi"] + values["cff"] + values["fx_cash_effect"], "variance": values["cff"], "result": "FAIL", "source_id": "MULTI_SOURCE", "notes": ""},
        {"area": "cash_flow", "period": period, "test": f"{symbol}: beginning cash + net change = ending cash", "expected_value": values["ending_cash"], "observed_value": values["beginning_cash"] + values["net_change_cash"], "variance": 0, "result": "PASS", "source_id": "MULTI_SOURCE", "notes": ""},
    ])
    normalized, checks, flags, evidence = hardening.harden_statement_validation(normalized, checks, empty_flags(), balance_relative_tolerance=1e-6, cash_relative_tolerance=1e-6)
    assert checks.iloc[0]["result"] == hardening.CONTROLLED_RESULT
    assert evidence[0]["reason"] == "NET_CHANGE_MATCHES_CFO_CFI_FX_BUT_REPORTED_CFF_IS_INCONSISTENT"
    assert not normalized[normalized.line_item_id.isin(["cff", "net_change_cash"])].decision_grade_eligible.any()


def test_balance_direct_total_cross_check_becomes_controlled():
    symbol = "603189.SH"
    period = "2025-06-30"
    values = {"total_assets": 1_606_117_392.07, "total_liabilities": 102_117_800.00, "total_equity": 1_540_471_404.46, "liabilities_equity": 1_642_589_204.46}
    normalized = normalized_frame(symbol, period, values)
    checks = pd.DataFrame([{"area": "balance_sheet", "period": period, "test": f"{symbol}: assets = liabilities + equity", "expected_value": values["total_assets"], "observed_value": values["total_liabilities"] + values["total_equity"], "variance": 36_471_812.39, "result": "FAIL", "source_id": "MULTI_SOURCE", "notes": ""}])
    normalized, checks, flags, evidence = hardening.harden_statement_validation(normalized, checks, empty_flags(), balance_relative_tolerance=1e-6, cash_relative_tolerance=1e-6)
    assert checks.iloc[0]["result"] == hardening.CONTROLLED_RESULT
    assert evidence[0]["reason"] == "LIABILITIES_PLUS_EQUITY_MATCH_DIRECT_TOTAL_BUT_CONFLICT_WITH_TOTAL_ASSETS"
    assert not normalized.decision_grade_eligible.any()


def test_unexplained_failure_remains_fail():
    symbol = "600000.SH"
    period = "2025-06-30"
    values = {"total_assets": 100.0, "total_liabilities": 30.0, "total_equity": 40.0, "liabilities_equity": 90.0}
    normalized = normalized_frame(symbol, period, values)
    checks = pd.DataFrame([{"area": "balance_sheet", "period": period, "test": f"{symbol}: assets = liabilities + equity", "expected_value": 100.0, "observed_value": 70.0, "variance": -30.0, "result": "FAIL", "source_id": "MULTI_SOURCE", "notes": ""}])
    normalized, checks, flags, evidence = hardening.harden_statement_validation(normalized, checks, empty_flags(), balance_relative_tolerance=1e-6, cash_relative_tolerance=1e-6)
    assert checks.iloc[0]["result"] == "FAIL"
    assert evidence == []
    assert normalized.decision_grade_eligible.all()
