from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FAMILY_ORDER = [
    "PROFITABILITY_RETURNS",
    "GROWTH_MOMENTUM",
    "CASH_EARNINGS_QUALITY",
    "BALANCE_SHEET_EFFICIENCY",
]


def validate_weight_table(weights: pd.DataFrame, config: dict[str, Any]) -> None:
    required = {
        "factor_id",
        "family_id",
        "family_weight",
        "factor_weight_in_family",
        "global_weight",
        "minimum_family_factor_count",
        "evidence_role",
    }
    missing = required - set(weights.columns)
    if missing:
        raise ValueError(f"score weight columns missing: {sorted(missing)}")
    if len(weights) != 18 or weights["factor_id"].duplicated().any():
        raise ValueError("score weight table must contain exactly 18 unique factors")
    if set(weights["family_id"]) != set(FAMILY_ORDER):
        raise ValueError("score family set does not match frozen contract")
    family_cfg = config["score"]["family_weights"]
    for family_id, group in weights.groupby("family_id"):
        local_sum = float(pd.to_numeric(group["factor_weight_in_family"]).sum())
        family_weight = float(pd.to_numeric(group["family_weight"]).iloc[0])
        if not np.isclose(local_sum, 1.0, atol=1e-10):
            raise ValueError(f"factor weights do not sum to one for {family_id}")
        if not np.isclose(family_weight, float(family_cfg[family_id]), atol=1e-10):
            raise ValueError(f"family weight mismatch for {family_id}")
        expected_global = (
            pd.to_numeric(group["factor_weight_in_family"]) * family_weight
        )
        if not np.allclose(
            expected_global,
            pd.to_numeric(group["global_weight"]),
            atol=1e-10,
        ):
            raise ValueError(f"global factor weight mismatch for {family_id}")
    if not np.isclose(pd.to_numeric(weights["global_weight"]).sum(), 1.0, atol=1e-10):
        raise ValueError("global factor weights do not sum to one")


def score_band(score: float | None, bands: list[dict[str, Any]]) -> str:
    if score is None or pd.isna(score):
        return "UNAVAILABLE"
    for row in sorted(bands, key=lambda item: float(item["minimum"]), reverse=True):
        if float(score) >= float(row["minimum"]):
            return str(row["band"])
    return "UNAVAILABLE"


def confidence_label(
    family_count: int,
    factor_weight_coverage: float,
    conditional_weight_share: float,
    config: dict[str, Any],
) -> str:
    high = config["score"]["high_confidence"]
    medium = config["score"]["medium_confidence"]
    if (
        family_count >= int(high["minimum_family_count"])
        and factor_weight_coverage
        >= float(high["minimum_global_factor_weight_coverage"])
        and conditional_weight_share
        <= float(high["maximum_conditional_weight_share"])
    ):
        return "HIGH"
    if (
        family_count >= int(medium["minimum_family_count"])
        and factor_weight_coverage
        >= float(medium["minimum_global_factor_weight_coverage"])
        and conditional_weight_share
        <= float(medium["maximum_conditional_weight_share"])
    ):
        return "MEDIUM"
    return "LOW"


def confidence_numeric(
    family_weight_coverage: float,
    factor_weight_coverage: float,
    conditional_weight_share: float,
) -> float:
    base = 100.0 * (
        0.55 * float(factor_weight_coverage)
        + 0.45 * float(family_weight_coverage)
    )
    adjusted = base * (1.0 - 0.25 * float(conditional_weight_share))
    return float(np.clip(adjusted, 0.0, 100.0))


def build_family_scores(
    hardened: pd.DataFrame,
    profiles: pd.DataFrame,
    weights: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    authorized_profile = str(config["score"]["authorized_profile"])
    min_weight_coverage = float(config["score"]["minimum_family_weight_coverage"])
    weight_columns = [
        "factor_id",
        "family_id",
        "family_weight",
        "factor_weight_in_family",
        "global_weight",
        "minimum_family_factor_count",
        "evidence_role",
    ]
    component = hardened.merge(
        weights[weight_columns],
        on="factor_id",
        how="inner",
        validate="many_to_one",
    ).copy()
    component["component_eligible"] = (
        component["sector_profile"].eq(authorized_profile)
        & component["production_eligibility"].isin(["ELIGIBLE", "CONDITIONAL"])
        & pd.to_numeric(component["directional_percentile"], errors="coerce").notna()
    )
    component["component_conditional"] = (
        component["component_eligible"]
        & component["production_eligibility"].eq("CONDITIONAL")
    )

    profile_index = profiles[["symbol", "sector_profile"]].copy()
    profile_index["symbol"] = profile_index["symbol"].astype(str)
    if profile_index["symbol"].duplicated().any():
        raise ValueError("profile reconciliation contains duplicate symbols")

    rows: list[dict[str, Any]] = []
    component_groups = {
        (str(symbol), str(family)): group
        for (symbol, family), group in component.groupby(["symbol", "family_id"])
    }
    weight_groups = {
        str(family): group for family, group in weights.groupby("family_id")
    }
    for profile in profile_index.itertuples(index=False):
        symbol = str(profile.symbol)
        sector_profile = str(profile.sector_profile)
        for family_id in FAMILY_ORDER:
            family_weights = weight_groups[family_id]
            family_weight = float(family_weights["family_weight"].iloc[0])
            expected_count = int(len(family_weights))
            minimum_count = int(
                config["score"]["family_minimum_factor_count"][family_id]
            )
            group = component_groups.get((symbol, family_id), pd.DataFrame())
            if group.empty:
                available = group
            else:
                available = group[group["component_eligible"]].copy()
            available_count = int(len(available))
            available_local_weight = float(
                pd.to_numeric(
                    available.get("factor_weight_in_family", pd.Series(dtype=float)),
                    errors="coerce",
                ).sum()
            )
            conditional_local_weight = float(
                pd.to_numeric(
                    available.loc[
                        available.get("component_conditional", pd.Series(False, index=available.index)),
                        "factor_weight_in_family",
                    ]
                    if len(available)
                    else pd.Series(dtype=float),
                    errors="coerce",
                ).sum()
            )
            profile_authorized = sector_profile == authorized_profile
            family_available = (
                profile_authorized
                and available_count >= minimum_count
                and available_local_weight >= min_weight_coverage
            )
            family_score = None
            if family_available:
                values = pd.to_numeric(
                    available["directional_percentile"], errors="coerce"
                )
                local_weights = pd.to_numeric(
                    available["factor_weight_in_family"], errors="coerce"
                )
                family_score = float(
                    100.0 * (values * local_weights).sum() / local_weights.sum()
                )
            if not profile_authorized:
                family_state = "CONTROLLED_PROFILE_EXCLUSION"
            elif family_available:
                family_state = "FAMILY_SCORE_AVAILABLE"
            elif available_count < minimum_count:
                family_state = "INSUFFICIENT_FACTOR_COUNT"
            else:
                family_state = "INSUFFICIENT_FACTOR_WEIGHT_COVERAGE"
            as_of_values = (
                available.get("as_of_timestamp", pd.Series(dtype=str))
                .dropna()
                .astype(str)
            )
            period_values = (
                available.get("period_end", pd.Series(dtype=str)).dropna().astype(str)
            )
            rows.append(
                {
                    "symbol": symbol,
                    "sector_profile": sector_profile,
                    "family_id": family_id,
                    "family_weight": family_weight,
                    "expected_factor_count": expected_count,
                    "minimum_factor_count": minimum_count,
                    "available_factor_count": available_count,
                    "available_factor_weight": available_local_weight,
                    "conditional_factor_weight": conditional_local_weight,
                    "family_score": family_score,
                    "family_state": family_state,
                    "family_as_of_timestamp": as_of_values.max()
                    if len(as_of_values)
                    else None,
                    "family_period_min": period_values.min()
                    if len(period_values)
                    else None,
                    "family_period_max": period_values.max()
                    if len(period_values)
                    else None,
                    "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                    "trade_authority": "NONE",
                }
            )
    return pd.DataFrame(rows), component


def build_financial_scores(
    family_scores: pd.DataFrame,
    component: pd.DataFrame,
    profiles: pd.DataFrame,
    config: dict[str, Any],
    source_release_id: str,
) -> pd.DataFrame:
    authorized_profile = str(config["score"]["authorized_profile"])
    minimum_family_count = int(config["score"]["minimum_available_family_count"])
    minimum_family_weight = float(config["score"]["minimum_available_family_weight"])
    minimum_factor_coverage = float(
        config["score"]["minimum_global_factor_weight_coverage"]
    )
    ranking_coverage = float(
        config["score"]["ranking_minimum_global_factor_weight_coverage"]
    )
    component_by_symbol = {str(k): v for k, v in component.groupby("symbol")}
    family_by_symbol = {str(k): v for k, v in family_scores.groupby("symbol")}
    rows: list[dict[str, Any]] = []

    for profile in profiles[["symbol", "sector_profile"]].itertuples(index=False):
        symbol = str(profile.symbol)
        sector_profile = str(profile.sector_profile)
        families = family_by_symbol[symbol]
        available_families = families[
            families["family_state"].eq("FAMILY_SCORE_AVAILABLE")
        ].copy()
        available_family_count = int(len(available_families))
        available_family_weight = float(
            pd.to_numeric(available_families["family_weight"], errors="coerce").sum()
        )
        components = component_by_symbol.get(symbol, pd.DataFrame())
        eligible_components = (
            components[components["component_eligible"]].copy()
            if len(components)
            else components
        )
        factor_weight_coverage = float(
            pd.to_numeric(
                eligible_components.get("global_weight", pd.Series(dtype=float)),
                errors="coerce",
            ).sum()
        )
        conditional_global_weight = float(
            pd.to_numeric(
                eligible_components.loc[
                    eligible_components.get(
                        "component_conditional",
                        pd.Series(False, index=eligible_components.index),
                    ),
                    "global_weight",
                ]
                if len(eligible_components)
                else pd.Series(dtype=float),
                errors="coerce",
            ).sum()
        )
        conditional_weight_share = (
            conditional_global_weight / factor_weight_coverage
            if factor_weight_coverage > 0
            else 0.0
        )
        score_value: float | None = None
        if sector_profile != authorized_profile:
            score_state = "CONTROLLED_PROFILE_EXCLUSION"
        elif available_family_count < minimum_family_count or available_family_weight < minimum_family_weight:
            score_state = "INSUFFICIENT_FAMILY_COVERAGE"
        elif factor_weight_coverage < minimum_factor_coverage:
            score_state = "INSUFFICIENT_FACTOR_COVERAGE"
        else:
            score_value = float(
                (
                    pd.to_numeric(available_families["family_score"], errors="coerce")
                    * pd.to_numeric(available_families["family_weight"], errors="coerce")
                ).sum()
                / available_family_weight
            )
            score_state = "SCORE_ACCEPTED"
        if score_value is None:
            confidence = "UNAVAILABLE"
            confidence_value = 0.0
            ranking_eligible = False
        else:
            confidence = confidence_label(
                available_family_count,
                factor_weight_coverage,
                conditional_weight_share,
                config,
            )
            confidence_value = confidence_numeric(
                available_family_weight,
                factor_weight_coverage,
                conditional_weight_share,
            )
            if confidence == "LOW":
                score_state = "SCORE_ACCEPTED_WITH_LIMITED_CONFIDENCE"
            ranking_eligible = bool(
                confidence in {"HIGH", "MEDIUM"}
                and factor_weight_coverage >= ranking_coverage
            )
        as_of_values = (
            eligible_components.get("as_of_timestamp", pd.Series(dtype=str))
            .dropna()
            .astype(str)
        )
        period_values = (
            eligible_components.get("period_end", pd.Series(dtype=str))
            .dropna()
            .astype(str)
        )
        row: dict[str, Any] = {
            "symbol": symbol,
            "sector_profile": sector_profile,
            "financial_score": score_value,
            "score_band": score_band(score_value, config["score"]["score_bands"]),
            "score_confidence": confidence,
            "score_confidence_numeric": confidence_value,
            "available_family_count": available_family_count,
            "available_family_weight": available_family_weight,
            "global_factor_weight_coverage": factor_weight_coverage,
            "conditional_weight_share": conditional_weight_share,
            "eligible_factor_count": int(len(eligible_components)),
            "conditional_factor_count": int(
                eligible_components.get(
                    "component_conditional",
                    pd.Series(False, index=eligible_components.index),
                ).sum()
            )
            if len(eligible_components)
            else 0,
            "ranking_eligible": ranking_eligible,
            "score_state": score_state,
            "score_as_of_timestamp": as_of_values.max()
            if len(as_of_values)
            else None,
            "component_period_min": period_values.min()
            if len(period_values)
            else None,
            "component_period_max": period_values.max()
            if len(period_values)
            else None,
            "source_hardening_release_id": source_release_id,
            "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
            "trade_authority": "NONE",
        }
        for family_id in FAMILY_ORDER:
            family_row = families[families["family_id"].eq(family_id)].iloc[0]
            prefix = family_id.lower()
            row[f"{prefix}_score"] = family_row["family_score"]
            row[f"{prefix}_state"] = family_row["family_state"]
        rows.append(row)
    return pd.DataFrame(rows)


def build_factor_contributions(
    component: pd.DataFrame,
    family_scores: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    families = family_scores[
        [
            "symbol",
            "family_id",
            "family_state",
            "available_factor_weight",
            "family_weight",
        ]
    ]
    score_context = scores[
        [
            "symbol",
            "financial_score",
            "available_family_weight",
            "score_state",
        ]
    ]
    out = component.merge(
        families,
        on=["symbol", "family_id"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_family"),
    ).merge(score_context, on="symbol", how="left", validate="many_to_one")
    include = (
        out["component_eligible"]
        & out["family_state"].eq("FAMILY_SCORE_AVAILABLE")
        & out["financial_score"].notna()
    )
    out["effective_family_weight"] = np.nan
    out["effective_factor_weight_in_family"] = np.nan
    out["effective_score_weight"] = np.nan
    out["contribution_points"] = np.nan
    out.loc[include, "effective_family_weight"] = (
        pd.to_numeric(out.loc[include, "family_weight"], errors="coerce")
        / pd.to_numeric(out.loc[include, "available_family_weight"], errors="coerce")
    )
    out.loc[include, "effective_factor_weight_in_family"] = (
        pd.to_numeric(out.loc[include, "factor_weight_in_family"], errors="coerce")
        / pd.to_numeric(out.loc[include, "available_factor_weight"], errors="coerce")
    )
    out.loc[include, "effective_score_weight"] = (
        out.loc[include, "effective_family_weight"]
        * out.loc[include, "effective_factor_weight_in_family"]
    )
    out.loc[include, "contribution_points"] = (
        pd.to_numeric(out.loc[include, "directional_percentile"], errors="coerce")
        * 100.0
        * out.loc[include, "effective_score_weight"]
    )
    out["component_state"] = "FACTOR_INELIGIBLE"
    out.loc[
        out["sector_profile"].ne("GENERAL_NON_FINANCIAL"), "component_state"
    ] = "CONTROLLED_PROFILE_EXCLUSION"
    out.loc[
        out["component_eligible"] & out["family_state"].ne("FAMILY_SCORE_AVAILABLE"),
        "component_state",
    ] = "FAMILY_INSUFFICIENT"
    out.loc[
        out["component_eligible"]
        & out["family_state"].eq("FAMILY_SCORE_AVAILABLE")
        & out["financial_score"].isna(),
        "component_state",
    ] = "OVERALL_SCORE_UNAVAILABLE"
    out.loc[include, "component_state"] = "INCLUDED"
    out.loc[include & out["component_conditional"], "component_state"] = (
        "INCLUDED_WITH_WARNING"
    )
    out["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    out["trade_authority"] = "NONE"
    columns = [
        "symbol",
        "factor_id",
        "family_id",
        "sector_profile",
        "directional_percentile",
        "production_eligibility",
        "component_state",
        "factor_weight_in_family",
        "global_weight",
        "effective_family_weight",
        "effective_factor_weight_in_family",
        "effective_score_weight",
        "contribution_points",
        "period_end",
        "as_of_timestamp",
        "lineage_id",
        "authority",
        "trade_authority",
    ]
    return out[columns].sort_values(["symbol", "family_id", "factor_id"]).reset_index(drop=True)


def candidate_evidence(score: float | None, confidence: str, config: dict[str, Any]) -> str:
    if score is None or pd.isna(score):
        return "OBSERVATION_ONLY_INSUFFICIENT_FINANCIAL_EVIDENCE"
    if score >= float(config["investment_os"]["candidate_positive_floor"]) and confidence in {"HIGH", "MEDIUM"}:
        return "POSITIVE_FINANCIAL_QUALITY_EVIDENCE"
    if score >= float(config["investment_os"]["candidate_supportive_floor"]):
        return "SUPPORTIVE_FINANCIAL_QUALITY_EVIDENCE"
    if score >= float(config["investment_os"]["candidate_neutral_floor"]):
        return "NEUTRAL_FINANCIAL_QUALITY_EVIDENCE"
    return "FINANCIAL_QUALITY_CAUTION"


def simulation_evidence(score: float | None, config: dict[str, Any]) -> str:
    if score is None or pd.isna(score):
        return "DIAGNOSTIC_OBSERVATION_ONLY"
    if score >= float(config["investment_os"]["simulation_quality_test_floor"]):
        return "QUALITY_STRATEGY_TEST_SUPPORT"
    return "CONTRARIAN_OR_RISK_TEST_CONTEXT"


def real_account_evidence(
    score: float | None,
    confidence: str,
    family_count: int,
    config: dict[str, Any],
) -> str:
    if score is None or pd.isna(score):
        return "INSUFFICIENT_FINANCIAL_EVIDENCE"
    if (
        score >= float(config["investment_os"]["strict_real_account_financial_floor"])
        and confidence
        == str(config["investment_os"]["strict_real_account_required_confidence"])
        and family_count == len(FAMILY_ORDER)
    ):
        return "STRICT_FINANCIAL_REVIEW_FLOOR_MET"
    if score >= float(config["investment_os"]["supportive_research_floor"]) and confidence in {"HIGH", "MEDIUM"}:
        return "RESEARCH_ONLY_STRICT_FLOOR_NOT_MET"
    return "BELOW_STRICT_FINANCIAL_REVIEW_FLOOR"


def build_investment_os_evidence(
    scores: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    out = scores.copy()
    out["candidate_pool_financial_evidence"] = [
        candidate_evidence(score, confidence, config)
        for score, confidence in zip(out["financial_score"], out["score_confidence"])
    ]
    out["simulation_lab_financial_evidence"] = [
        simulation_evidence(score, config) for score in out["financial_score"]
    ]
    out["real_account_financial_evidence"] = [
        real_account_evidence(score, confidence, int(family_count), config)
        for score, confidence, family_count in zip(
            out["financial_score"],
            out["score_confidence"],
            out["available_family_count"],
        )
    ]
    out["candidate_pool_action_authorized"] = False
    out["simulation_admission_authorized"] = False
    out["real_account_admission_authorized"] = False
    out["portfolio_action_authorized"] = False
    out["order_execution_authorized"] = False
    out["required_downstream_gates"] = (
        "PUBLIC_EQUITY_RESEARCH|OWNER_QUALITY|INVESTMENT_ATTRACTIVENESS|"
        "ETF_ALTERNATIVE|CANDIDATE_RACE|SIMULATION_OR_SHADOW_TRACK|"
        "PORTFOLIO_FIT|CAPITAL_MIGRATION|PRE_TRADE_MEMO|USER_CONFIRMATION"
    )
    selected = [
        "symbol",
        "sector_profile",
        "financial_score",
        "score_band",
        "score_confidence",
        "score_confidence_numeric",
        "global_factor_weight_coverage",
        "available_family_count",
        "ranking_eligible",
        "score_state",
        "candidate_pool_financial_evidence",
        "simulation_lab_financial_evidence",
        "real_account_financial_evidence",
        "candidate_pool_action_authorized",
        "simulation_admission_authorized",
        "real_account_admission_authorized",
        "portfolio_action_authorized",
        "order_execution_authorized",
        "required_downstream_gates",
        "source_hardening_release_id",
        "authority",
        "trade_authority",
    ]
    return out[selected].sort_values("symbol").reset_index(drop=True)
