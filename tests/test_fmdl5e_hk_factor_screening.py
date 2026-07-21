from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_fmdl5e_hk_factor_screening import (  # noqa: E402
    convert_hkd_to_currency,
    convert_to_hkd,
    evaluate_sleeve,
    percentile_rank,
    safe_divide,
    window_return,
)


def test_safe_divide_fail_closed() -> None:
    assert safe_divide(10, 2) == 5
    assert safe_divide(10, 0) is None
    assert safe_divide(10, -2, positive_denominator=True) is None
    assert safe_divide(None, 2) is None


def test_currency_conversion_round_trip() -> None:
    hkd = convert_to_hkd(100, "CNY", 7.8, 1.08)
    assert hkd == 108
    assert convert_hkd_to_currency(hkd, "RMB", 7.8, 1.08) == 100
    assert convert_to_hkd(10, "USD", 7.8, 1.08) == 78
    assert convert_to_hkd(10, "UNKNOWN", 7.8, 1.08) is None


def test_window_return_requires_full_window() -> None:
    assert window_return(pd.Series([100, 110]), 1) == pytest.approx(0.1)
    assert window_return(pd.Series([100]), 1) is None
    assert window_return(pd.Series([0, 1]), 1) is None


def test_percentile_direction() -> None:
    values = pd.Series([1.0, 2.0, 3.0])
    high = percentile_rank(values, "HIGH")
    low = percentile_rank(values, "LOW")
    assert high.iloc[-1] == 1.0
    assert low.iloc[0] == 1.0


def test_sleeve_missing_values_require_component_gate_and_penalty() -> None:
    frame = pd.DataFrame(
        [
            {"as_of_date":"2026-07-21","security_id":"HKEX:00001","stock_code_5d":"00001","official_security_name_en":"A","official_issuer_name_en":"A","profile":"GENERAL_NON_FINANCIAL","investability_status":"ELIGIBLE_CORE","factor_record_quality":"VALID","confidence_grade":"A","avg_turnover_hkd_20d":10000000,"x__pct":1.0,"y__pct":1.0,"x":1,"y":1},
            {"as_of_date":"2026-07-21","security_id":"HKEX:00002","stock_code_5d":"00002","official_security_name_en":"B","official_issuer_name_en":"B","profile":"GENERAL_NON_FINANCIAL","investability_status":"ELIGIBLE_CORE","factor_record_quality":"VALID","confidence_grade":"A","avg_turnover_hkd_20d":9000000,"x__pct":1.0,"y__pct":None,"x":1,"y":None},
        ]
    )
    sleeve = {"route":"CORE","minimum_score":0.0,"maximum_candidates":10,"minimum_components":2,"weights":{"x":0.5,"y":0.5}}
    result = evaluate_sleeve(frame, "TEST", sleeve)
    assert result["security_id"].tolist() == ["HKEX:00001"]
    assert result.iloc[0]["sleeve_score"] == 1.0
