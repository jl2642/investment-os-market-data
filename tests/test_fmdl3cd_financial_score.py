from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.fmdl3cd_core import (
    build_factor_contributions,
    build_family_scores,
    build_financial_scores,
    build_investment_os_evidence,
    confidence_label,
    score_band,
)


def config():
    return {
        "score": {
            "authorized_profile": "GENERAL_NON_FINANCIAL",
            "minimum_available_family_count": 3,
            "minimum_available_family_weight": 0.70,
            "minimum_global_factor_weight_coverage": 0.70,
            "ranking_minimum_global_factor_weight_coverage": 0.75,
            "minimum_family_weight_coverage": 0.50,
            "family_weights": {
                "PROFITABILITY_RETURNS": 0.25,
                "GROWTH_MOMENTUM": 0.25,
                "CASH_EARNINGS_QUALITY": 0.25,
                "BALANCE_SHEET_EFFICIENCY": 0.25,
            },
            "family_minimum_factor_count": {
                "PROFITABILITY_RETURNS": 1,
                "GROWTH_MOMENTUM": 1,
                "CASH_EARNINGS_QUALITY": 1,
                "BALANCE_SHEET_EFFICIENCY": 1,
            },
            "high_confidence": {
                "minimum_family_count": 4,
                "minimum_global_factor_weight_coverage": 0.90,
                "maximum_conditional_weight_share": 0.10,
            },
            "medium_confidence": {
                "minimum_family_count": 3,
                "minimum_global_factor_weight_coverage": 0.75,
                "maximum_conditional_weight_share": 0.30,
            },
            "score_bands": [
                {"minimum": 85.0, "band": "EXCEPTIONAL_FINANCIAL_QUALITY"},
                {"minimum": 75.0, "band": "STRONG_FINANCIAL_QUALITY"},
                {"minimum": 65.0, "band": "ABOVE_AVERAGE_FINANCIAL_QUALITY"},
                {"minimum": 50.0, "band": "NEUTRAL_FINANCIAL_QUALITY"},
                {"minimum": 35.0, "band": "WEAK_FINANCIAL_QUALITY"},
                {"minimum": 0.0, "band": "VERY_WEAK_FINANCIAL_QUALITY"},
            ],
        },
        "investment_os": {
            "strict_real_account_financial_floor": 85.0,
            "strict_real_account_required_confidence": "HIGH",
            "supportive_research_floor": 70.0,
            "candidate_positive_floor": 80.0,
            "candidate_supportive_floor": 65.0,
            "candidate_neutral_floor": 50.0,
            "simulation_quality_test_floor": 75.0,
        },
    }


def weights():
    return pd.DataFrame(
        [
            ["F1", "PROFITABILITY_RETURNS", 0.25, 1.0, 0.25, 1, "CORE_SCORE"],
            ["F2", "GROWTH_MOMENTUM", 0.25, 1.0, 0.25, 1, "CORE_SCORE"],
            ["F3", "CASH_EARNINGS_QUALITY", 0.25, 1.0, 0.25, 1, "CORE_SCORE"],
            ["F4", "BALANCE_SHEET_EFFICIENCY", 0.25, 1.0, 0.25, 1, "CORE_SCORE"],
        ],
        columns=[
            "factor_id",
            "family_id",
            "family_weight",
            "factor_weight_in_family",
            "global_weight",
            "minimum_family_factor_count",
            "evidence_role",
        ],
    )


def hardened(symbol: str, values, conditional_index=None, profile="GENERAL_NON_FINANCIAL"):
    conditional_index = conditional_index or set()
    rows = []
    for index, (factor_id, value) in enumerate(zip(["F1", "F2", "F3", "F4"], values)):
        conditional = index in conditional_index
        rows.append(
            {
                "symbol": symbol,
                "factor_id": factor_id,
                "sector_profile": profile,
                "directional_percentile": value,
                "production_eligibility": "CONDITIONAL" if conditional else "ELIGIBLE",
                "period_end": "2025-12-31",
                "as_of_timestamp": "2026-03-31T09:30:00+08:00",
                "lineage_id": f"{symbol}-{factor_id}",
            }
        )
    return pd.DataFrame(rows)


def test_score_band_and_confidence_contract():
    cfg = config()
    assert score_band(86.0, cfg["score"]["score_bands"]) == "EXCEPTIONAL_FINANCIAL_QUALITY"
    assert score_band(None, cfg["score"]["score_bands"]) == "UNAVAILABLE"
    assert confidence_label(4, 1.0, 0.0, cfg) == "HIGH"
    assert confidence_label(3, 0.80, 0.20, cfg) == "MEDIUM"
    assert confidence_label(3, 0.72, 0.20, cfg) == "LOW"


def test_score_contributions_replay_and_roles_are_separate():
    cfg = config()
    profiles = pd.DataFrame(
        [{"symbol": "000001.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"}]
    )
    family, component = build_family_scores(
        hardened("000001.SZ", [0.90, 0.80, 0.70, 0.60]),
        profiles,
        weights(),
        cfg,
    )
    scores = build_financial_scores(
        family, component, profiles, cfg, "FMDL3CC_TEST"
    )
    contributions = build_factor_contributions(component, family, scores)
    evidence = build_investment_os_evidence(scores, cfg)
    score = float(scores.iloc[0]["financial_score"])
    assert np.isclose(score, 75.0)
    assert scores.iloc[0]["score_confidence"] == "HIGH"
    assert scores.iloc[0]["ranking_eligible"]
    assert np.isclose(contributions["contribution_points"].sum(), score)
    row = evidence.iloc[0]
    assert row["simulation_lab_financial_evidence"] == "QUALITY_STRATEGY_TEST_SUPPORT"
    assert row["real_account_financial_evidence"] == "RESEARCH_ONLY_STRICT_FLOOR_NOT_MET"
    assert not row["candidate_pool_action_authorized"]
    assert not row["simulation_admission_authorized"]
    assert not row["real_account_admission_authorized"]


def test_strict_real_floor_requires_high_confidence_and_four_families():
    cfg = config()
    profiles = pd.DataFrame(
        [{"symbol": "000002.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"}]
    )
    family, component = build_family_scores(
        hardened("000002.SZ", [0.95, 0.95, 0.95, 0.95]),
        profiles,
        weights(),
        cfg,
    )
    scores = build_financial_scores(
        family, component, profiles, cfg, "FMDL3CC_TEST"
    )
    evidence = build_investment_os_evidence(scores, cfg)
    row = evidence.iloc[0]
    assert row["financial_score"] == 95.0
    assert row["score_confidence"] == "HIGH"
    assert row["real_account_financial_evidence"] == "STRICT_FINANCIAL_REVIEW_FLOOR_MET"
    assert not row["real_account_admission_authorized"]


def test_conditional_weight_reduces_confidence_without_score_penalty():
    cfg = config()
    profiles = pd.DataFrame(
        [{"symbol": "000003.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"}]
    )
    family, component = build_family_scores(
        hardened("000003.SZ", [0.80, 0.80, 0.80, 0.80], conditional_index={0, 1}),
        profiles,
        weights(),
        cfg,
    )
    scores = build_financial_scores(
        family, component, profiles, cfg, "FMDL3CC_TEST"
    )
    row = scores.iloc[0]
    assert np.isclose(row["financial_score"], 80.0)
    assert row["conditional_weight_share"] == 0.5
    assert row["score_confidence"] == "LOW"
    assert not row["ranking_eligible"]


def test_financial_profile_is_fail_closed_not_zero_scored():
    cfg = config()
    profiles = pd.DataFrame([{"symbol": "600000.SH", "sector_profile": "BANK"}])
    family, component = build_family_scores(
        hardened("600000.SH", [0.9, 0.9, 0.9, 0.9], profile="BANK"),
        profiles,
        weights(),
        cfg,
    )
    scores = build_financial_scores(
        family, component, profiles, cfg, "FMDL3CC_TEST"
    )
    row = scores.iloc[0]
    assert pd.isna(row["financial_score"])
    assert row["score_state"] == "CONTROLLED_PROFILE_EXCLUSION"
    assert row["score_band"] == "UNAVAILABLE"
    assert not row["ranking_eligible"]
