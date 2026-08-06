import pandas as pd

from pipeline.hkcu1_build_universe import build_universe


def _screening() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "security_id": "HKEX:00005",
                "stock_code_5d": "00005",
                "security_type": "COMMON_EQUITY",
                "investability_status": "ELIGIBLE_CORE",
                "avg_turnover_hkd_20d": 100_000_000,
                "active_trade_ratio_60d": 1.0,
                "zero_volume_days_20d": 0,
                "latest_close": 100.0,
                "financial_decision_grade": True,
                "profile": "BANK",
            },
            {
                "security_id": "HKEX:09999",
                "stock_code_5d": "09999",
                "security_type": "COMMON_EQUITY",
                "investability_status": "ELIGIBLE_CORE",
                "avg_turnover_hkd_20d": 80_000_000,
                "active_trade_ratio_60d": 1.0,
                "zero_volume_days_20d": 0,
                "latest_close": 200.0,
                "financial_decision_grade": True,
                "profile": "GENERAL_NON_FINANCIAL",
            },
            {
                "security_id": "HKEX:02525",
                "stock_code_5d": "02525",
                "security_type": "COMMON_EQUITY",
                "investability_status": "ELIGIBLE_CORE",
                "avg_turnover_hkd_20d": 5_000_000,
                "active_trade_ratio_60d": 0.95,
                "zero_volume_days_20d": 0,
                "latest_close": 10.0,
                "financial_decision_grade": False,
                "profile": "RECENT_LISTING",
            },
            {
                "security_id": "HKEX:00004",
                "stock_code_5d": "00004",
                "security_type": "COMMON_EQUITY",
                "investability_status": "ELIGIBLE_CORE",
                "avg_turnover_hkd_20d": 50_000_000,
                "active_trade_ratio_60d": 1.0,
                "zero_volume_days_20d": 0,
                "latest_close": 20.0,
                "financial_decision_grade": True,
                "profile": "GENERAL_NON_FINANCIAL",
            },
        ]
    )


def test_channel_status_and_fail_closed_exclusion() -> None:
    sh = pd.DataFrame({"stock_code_5d": ["00005", "09999"], "sh_buy_eligible": [True, True]})
    sz = pd.DataFrame({"stock_code_5d": ["00005", "02525"], "sz_buy_eligible": [True, True]})

    eligibility, investable, exclusions = build_universe(
        _screening(), sh, sz, "2026-08-06", "a" * 64, "b" * 64
    )

    states = eligibility.set_index("stock_code_5d")["eligibility_status"].to_dict()
    assert states["00005"] == "BUY_ELIGIBLE_BOTH"
    assert states["09999"] == "BUY_ELIGIBLE_SH_ONLY"
    assert states["02525"] == "BUY_ELIGIBLE_SZ_ONLY"
    assert states["00004"] == "NOT_ELIGIBLE"

    assert set(investable["stock_code_5d"]) == {"00005", "09999"}
    reasons = exclusions.set_index("stock_code_5d")["hkcu1_gate_reason"].to_dict()
    assert "LOW_20D_TURNOVER" in reasons["02525"]
    assert "NOT_SOUTHBOUND_BUY_ELIGIBLE" in reasons["00004"]
    assert set(eligibility["trade_authority"]) == {"NONE"}
