from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.hkcu_p2b_build_research_baseline import build_dimension_matrix, build_security_matrix


def contract() -> dict:
    return {
        "security_type_map": {
            "BANK": "BANK",
            "INSURANCE": "INSURANCE",
            "SECURITIES_AND_BROKERAGE": "SECURITIES_AND_BROKERAGE",
            "GENERAL_NON_FINANCIAL": "GENERAL_NON_FINANCIAL",
        },
        "dimensions": [
            {"dimension_id": "GOVERNANCE_VALUE_TRAP", "minimum_evidence_standard": "g"},
            {"dimension_id": "EARNINGS_EXPECTATION_REVISION", "minimum_evidence_standard": "e"},
            {"dimension_id": "CATALYST", "minimum_evidence_standard": "c"},
            {"dimension_id": "TRANSACTION_COST_TAX", "minimum_evidence_standard": "t"},
            {"dimension_id": "A_H_RELATIVE_VALUATION", "minimum_evidence_standard": "a"},
        ],
    }


def longlist_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "overall_rank": 1,
            "security_id": "HK0001",
            "stock_code_5d": "00001",
            "official_security_name_en": "A",
            "official_issuer_name_en": "Issuer A",
            "primary_sleeve": "QUALITY_COMPOUNDER",
            "aggregate_score": 1.2,
            "profile": "GENERAL_NON_FINANCIAL",
            "a_share_class_exists": True,
            "h_share_flag": True,
            "research_readiness": "READY_HIGH",
        },
        {
            "overall_rank": 2,
            "security_id": "HK0002",
            "stock_code_5d": "00002",
            "official_security_name_en": "B",
            "official_issuer_name_en": "Issuer B",
            "primary_sleeve": "DEFENSIVE_STABILITY",
            "aggregate_score": 1.1,
            "profile": "BANK",
            "a_share_class_exists": False,
            "h_share_flag": True,
            "research_readiness": "READY_HIGH",
        },
    ])


def test_h_share_flag_alone_does_not_make_ah_valuation_applicable() -> None:
    security = build_security_matrix(longlist_rows(), contract())
    dimensions = build_dimension_matrix(security, contract())
    ah = dimensions[dimensions["research_dimension"] == "A_H_RELATIVE_VALUATION"].set_index("security_id")
    assert ah.loc["HK0001", "evidence_status"] == "RESEARCH_REQUIRED"
    assert ah.loc["HK0001", "applicability"] == "POTENTIALLY_APPLICABLE"
    assert ah.loc["HK0002", "evidence_status"] == "NOT_APPLICABLE"
    assert ah.loc["HK0002", "applicability"] == "NOT_APPLICABLE"


def test_all_other_dimensions_remain_evidence_required_without_scores() -> None:
    security = build_security_matrix(longlist_rows(), contract())
    dimensions = build_dimension_matrix(security, contract())
    other = dimensions[dimensions["research_dimension"] != "A_H_RELATIVE_VALUATION"]
    assert len(other) == 8
    assert (other["evidence_status"] == "RESEARCH_REQUIRED").all()
    assert other["score"].isna().all()
    assert (other["score_status"] == "NO_SCORE_BEFORE_EVIDENCE").all()


def test_security_type_is_profile_aware() -> None:
    security = build_security_matrix(longlist_rows(), contract()).set_index("security_id")
    assert security.loc["HK0001", "p2b_security_type"] == "GENERAL_NON_FINANCIAL"
    assert security.loc["HK0002", "p2b_security_type"] == "BANK"


def test_unknown_profile_fails_safe_to_research_required_type() -> None:
    rows = longlist_rows().copy()
    rows.loc[0, "profile"] = "UNMAPPED"
    security = build_security_matrix(rows, contract()).set_index("security_id")
    assert security.loc["HK0001", "p2b_security_type"] == "UNKNOWN_RESEARCH_REQUIRED"
