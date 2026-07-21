from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_fmdl5e_hk_factor_screening_r1 import (  # noqa: E402
    build_longlist,
    derive_screening_profile,
)


def profile_row(code: str, security: str, issuer: str, decision_grade: bool = True) -> dict[str, object]:
    return {
        "stock_code_5d": code,
        "security_type": "COMMON_EQUITY",
        "official_security_name_en": security,
        "official_issuer_name_en": issuer,
        "financial_decision_grade": decision_grade,
    }


def test_profile_semantic_anchors() -> None:
    assert derive_screening_profile(profile_row("00005", "HSBC HOLDINGS", "HSBC Holdings plc"))[0] == "BANK"
    assert derive_screening_profile(profile_row("00300", "MIDEA GROUP", "Midea Group Co., Ltd. - H Shares"))[0] == "GENERAL_NON_FINANCIAL"
    assert derive_screening_profile(profile_row("00038", "FIRST TRACTOR", "First Tractor Co Ltd. - H Shares"))[0] == "GENERAL_NON_FINANCIAL"
    assert derive_screening_profile(profile_row("06030", "CITIC SEC", "CITIC Securities Co. Ltd. - H Shares"))[0] == "SECURITIES_AND_BROKERAGE"
    assert derive_screening_profile(profile_row("03908", "CICC", "China International Capital Corporation Ltd. - H Shares"))[0] == "SECURITIES_AND_BROKERAGE"
    assert derive_screening_profile(profile_row("02318", "PING AN", "Ping An Insurance (Group) Co. of China, Ltd. - H Shares"))[0] == "INSURANCE"


def test_profile_fails_closed_without_decision_grade_financials() -> None:
    profile, basis = derive_screening_profile(profile_row("02983", "HESAI-W", "HESAI-W", False))
    assert profile == "CONTROLLED_NON_FINANCIAL"
    assert basis == "NO_DECISION_GRADE_FINANCIAL_CURRENT"


def test_formal_sleeve_longlist_contains_no_fallback() -> None:
    frame = pd.DataFrame(
        [
            {
                "as_of_date": "2026-07-21",
                "security_id": f"HKEX:{code}",
                "stock_code_5d": code,
                "official_security_name_en": f"NAME {code}",
                "official_issuer_name_en": f"ISSUER {code}",
                "investability_status": "ELIGIBLE_CORE",
                "factor_record_quality": "VALID",
                "confidence_grade": "A",
                "profile": "GENERAL_NON_FINANCIAL",
                "source_profile": "GENERAL_NON_FINANCIAL",
                "profile_basis": "DEFAULT_GENERAL_NON_FINANCIAL",
                "profile_override_applied": False,
                "avg_turnover_hkd_20d": 10_000_000 - index,
            }
            for index, code in enumerate(["00001", "00002", "00003", "00004"])
        ]
    )
    detail = pd.DataFrame(
        [
            {"security_id": "HKEX:00001", "sleeve_id": "QUALITY_COMPOUNDER", "sleeve_rank_percentile": 1.0, "sleeve_score": 0.9},
            {"security_id": "HKEX:00002", "sleeve_id": "HIGH_DIVIDEND_VALUE", "sleeve_rank_percentile": 1.0, "sleeve_score": 0.8},
            {"security_id": "HKEX:00003", "sleeve_id": "TREND_LIQUIDITY", "sleeve_rank_percentile": 1.0, "sleeve_score": 0.7},
            {"security_id": "HKEX:00004", "sleeve_id": "DEFENSIVE_STABILITY", "sleeve_rank_percentile": 1.0, "sleeve_score": 0.6},
        ]
    )
    contract = {
        "authority": "HK_FACTOR_AND_RESEARCH_PRIORITY_SCREEN_ONLY",
        "funnel": {
            "longlist_count": 3,
            "priority_bucket_counts": {
                "A_IMMEDIATE_RESEARCH": 1,
                "B_WATCH_OR_TRIGGER": 1,
                "C_SCREEN_FLAG_ONLY": 1,
            },
            "cross_sleeve_bonus_per_extra_sleeve": 0.015,
            "cross_sleeve_bonus_maximum": 0.06,
            "next_workflow": "FMDL-5F_PUBLIC_EQUITY_RESEARCH_ADAPTER",
        },
    }
    result = build_longlist(frame, detail, contract)
    assert len(result) == 3
    assert set(result["screening_basis"]) == {"FORMAL_SLEEVE_ONLY"}
    assert not result["primary_sleeve"].str.contains("FALLBACK").any()


def test_formal_sleeve_longlist_rejects_insufficient_distinct_coverage() -> None:
    frame = pd.DataFrame(
        [{"security_id": "HKEX:00001", "investability_status": "ELIGIBLE_CORE", "avg_turnover_hkd_20d": 1.0}]
    )
    detail = pd.DataFrame(
        [{"security_id": "HKEX:00001", "sleeve_id": "QUALITY_COMPOUNDER", "sleeve_rank_percentile": 1.0, "sleeve_score": 0.9}]
    )
    contract = {
        "authority": "HK_FACTOR_AND_RESEARCH_PRIORITY_SCREEN_ONLY",
        "funnel": {
            "longlist_count": 2,
            "priority_bucket_counts": {"A_IMMEDIATE_RESEARCH": 1, "B_WATCH_OR_TRIGGER": 1, "C_SCREEN_FLAG_ONLY": 0},
            "cross_sleeve_bonus_per_extra_sleeve": 0.015,
            "cross_sleeve_bonus_maximum": 0.06,
            "next_workflow": "FMDL-5F_PUBLIC_EQUITY_RESEARCH_ADAPTER",
        },
    }
    with pytest.raises(RuntimeError, match="INSUFFICIENT_FORMAL_SLEEVE_COVERAGE"):
        build_longlist(frame, detail, contract)
