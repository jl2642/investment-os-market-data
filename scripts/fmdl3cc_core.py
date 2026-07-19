from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

VALID_RAW_STATES = {"VALID", "VALID_WITH_WARNING"}


@dataclass(frozen=True)
class DistributionStats:
    count: int
    minimum: float
    q001: float
    q01: float
    median: float
    q99: float
    q999: float
    maximum: float
    mad: float


def profile_reconciliation_status(profile: str) -> str:
    if profile == "GENERAL_NON_FINANCIAL":
        return "COARSE_PROFILE_ACCEPTED_FOR_HARDENING"
    if profile in {"BANK", "INSURANCE", "SECURITIES_AND_BROKERAGE"}:
        return "CONTROLLED_EXCLUSION_PENDING_SECTOR_FACTOR_PACK"
    return "CONTROLLED_EXCLUSION_UNRESOLVED"


def distribution_stats(values: pd.Series) -> DistributionStats | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    numeric = numeric[np.isfinite(numeric)]
    if numeric.empty:
        return None
    median = float(numeric.median())
    mad = float((numeric - median).abs().median())
    quantiles = numeric.quantile([0.001, 0.01, 0.99, 0.999])
    return DistributionStats(
        count=int(len(numeric)),
        minimum=float(numeric.min()),
        q001=float(quantiles.loc[0.001]),
        q01=float(quantiles.loc[0.01]),
        median=median,
        q99=float(quantiles.loc[0.99]),
        q999=float(quantiles.loc[0.999]),
        maximum=float(numeric.max()),
        mad=mad,
    )


def robust_zscore(values: pd.Series, median: float, mad: float, clip: float) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    if not np.isfinite(mad) or mad <= 1e-12:
        return pd.Series(np.zeros(len(numeric)), index=numeric.index, dtype=float)
    scaled = 0.6744897501960817 * (numeric - median) / mad
    return scaled.clip(lower=-clip, upper=clip)


def directional_percentile(values: pd.Series, direction: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    rank = numeric.rank(method="average", pct=True)
    if direction == "LOWER_BETTER":
        return 1.0 - rank + (1.0 / max(len(rank), 1))
    if direction == "HIGHER_BETTER":
        return rank
    return pd.Series(np.nan, index=numeric.index, dtype=float)


def build_profile_registry(profiles: pd.DataFrame) -> pd.DataFrame:
    out = profiles.copy()
    out["profile_reconciliation_status"] = out["sector_profile"].astype(str).map(
        profile_reconciliation_status
    )
    out["industry_neutral_scoring_authorized"] = False
    out["profile_hardening_authorized"] = out["sector_profile"].eq(
        "GENERAL_NON_FINANCIAL"
    )
    out["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    out["trade_authority"] = "NONE"
    return out.sort_values("symbol").reset_index(drop=True)


def harden_factor_current(
    current: pd.DataFrame,
    profiles: pd.DataFrame,
    policy: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hard = current.copy()
    policy = policy.copy()
    policy["percentile_authorized"] = (
        policy["percentile_authorized"].astype(str).str.lower().eq("true")
    )
    profile_registry = build_profile_registry(profiles)
    profile_lookup = profile_registry.set_index("symbol")
    policy_lookup = policy.set_index("factor_id")

    hard = hard.merge(
        policy,
        on="factor_id",
        how="left",
        validate="many_to_one",
    )
    hard["factor_value_raw"] = pd.to_numeric(hard["factor_value"], errors="coerce")
    hard["factor_value_winsorized"] = np.nan
    hard["robust_zscore"] = np.nan
    hard["directional_percentile"] = np.nan
    hard["tail_flag"] = "NONE"
    hard["hardening_reason_codes"] = "NONE"
    hard["hardening_state"] = "RAW_FACTOR_INELIGIBLE"
    hard["production_eligibility"] = "INELIGIBLE"
    hard["profile_reconciliation_status"] = hard["sector_profile"].astype(str).map(
        profile_reconciliation_status
    )
    hard["peer_group_id"] = hard["sector_profile"].astype(str)
    hard["peer_group_count"] = 0
    hard["factor_gate_status"] = "UNASSESSED"

    profile_counts = profiles["sector_profile"].astype(str).value_counts().to_dict()
    distribution_rows: list[dict[str, Any]] = []
    factor_rows: list[dict[str, Any]] = []
    tail_rows: list[pd.DataFrame] = []

    valid_states = set(config["hardening"]["valid_raw_quality_states"])
    production_profile = str(config["hardening"]["production_profile"])
    min_peer = int(config["hardening"]["minimum_peer_group_size"])
    zclip = float(config["hardening"]["robust_zscore_clip"])

    for factor_id, factor_policy in policy_lookup.iterrows():
        factor_mask = hard["factor_id"].astype(str).eq(str(factor_id))
        raw_valid = factor_mask & hard["quality_state"].isin(valid_states) & hard[
            "factor_value_raw"
        ].notna()
        production_profile_count = int(profile_counts.get(production_profile, 0))
        production_valid_count = int(
            (raw_valid & hard["sector_profile"].eq(production_profile)).sum()
        )
        coverage_ratio = (
            production_valid_count / production_profile_count
            if production_profile_count
            else 0.0
        )
        factor_status = str(factor_policy["factor_status"])
        minimum_coverage = float(factor_policy["minimum_coverage_ratio"])
        if factor_status == "DEFERRED_HISTORY":
            factor_gate_status = "DEFERRED_HISTORY"
        elif factor_status == "DIAGNOSTIC_ONLY":
            factor_gate_status = "ACCEPTED_DIAGNOSTIC_ONLY"
        elif coverage_ratio >= minimum_coverage:
            factor_gate_status = "ACCEPTED_PRODUCTION_CORE"
        else:
            factor_gate_status = "BLOCKED_PRODUCTION_COVERAGE"
        hard.loc[factor_mask, "factor_gate_status"] = factor_gate_status

        factor_rows.append(
            {
                "factor_id": factor_id,
                "factor_status": factor_status,
                "production_profile_count": production_profile_count,
                "production_valid_or_warning_count": production_valid_count,
                "production_coverage_ratio": coverage_ratio,
                "minimum_coverage_ratio": minimum_coverage,
                "factor_gate_status": factor_gate_status,
                "percentile_authorized": bool(
                    factor_policy["percentile_authorized"]
                ),
                "policy_reason": factor_policy["policy_reason"],
                "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                "trade_authority": "NONE",
            }
        )

        for profile, group_index in hard.loc[factor_mask].groupby(
            "sector_profile"
        ).groups.items():
            group_mask = hard.index.isin(group_index)
            group_valid = group_mask & raw_valid
            values = hard.loc[group_valid, "factor_value_raw"]
            stats = distribution_stats(values)
            peer_count = int(len(values))
            hard.loc[group_mask, "peer_group_count"] = peer_count
            distribution_rows.append(
                {
                    "factor_id": factor_id,
                    "sector_profile": profile,
                    "factor_status": factor_status,
                    "valid_or_warning_count": peer_count,
                    "profile_symbol_count": int(profile_counts.get(profile, 0)),
                    "coverage_ratio": (
                        peer_count / int(profile_counts.get(profile, 0))
                        if int(profile_counts.get(profile, 0))
                        else 0.0
                    ),
                    "minimum": None if stats is None else stats.minimum,
                    "q001": None if stats is None else stats.q001,
                    "q01": None if stats is None else stats.q01,
                    "median": None if stats is None else stats.median,
                    "q99": None if stats is None else stats.q99,
                    "q999": None if stats is None else stats.q999,
                    "maximum": None if stats is None else stats.maximum,
                    "mad": None if stats is None else stats.mad,
                    "peer_group_method": "COARSE_SECTOR_PROFILE",
                    "industry_neutral": False,
                    "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
                    "trade_authority": "NONE",
                }
            )
            if stats is None or peer_count < min_peer:
                continue
            if profile != production_profile:
                continue
            lower_q = float(factor_policy["winsor_lower_quantile"])
            upper_q = float(factor_policy["winsor_upper_quantile"])
            lower = float(values.quantile(lower_q))
            upper = float(values.quantile(upper_q))
            clipped = values.clip(lower=lower, upper=upper)
            hard.loc[group_valid, "factor_value_winsorized"] = clipped
            hard.loc[group_valid, "robust_zscore"] = robust_zscore(
                clipped,
                float(clipped.median()),
                float((clipped - clipped.median()).abs().median()),
                zclip,
            )
            if bool(factor_policy["percentile_authorized"]):
                hard.loc[group_valid, "directional_percentile"] = directional_percentile(
                    clipped,
                    str(hard.loc[group_valid, "economic_direction"].iloc[0]),
                )
            low_tail = group_valid & hard["factor_value_raw"].lt(lower)
            high_tail = group_valid & hard["factor_value_raw"].gt(upper)
            hard.loc[low_tail, "tail_flag"] = "WINSORIZED_LOW"
            hard.loc[high_tail, "tail_flag"] = "WINSORIZED_HIGH"
            if low_tail.any() or high_tail.any():
                tails = hard.loc[low_tail | high_tail, [
                    "symbol",
                    "factor_id",
                    "factor_value_raw",
                    "factor_value_winsorized",
                    "sector_profile",
                    "quality_state",
                    "tail_flag",
                    "period_end",
                    "as_of_timestamp",
                    "lineage_id",
                ]].copy()
                tails["lower_limit"] = lower
                tails["upper_limit"] = upper
                tail_rows.append(tails)

    deferred = hard["factor_status"].eq("DEFERRED_HISTORY")
    diagnostic = hard["factor_status"].eq("DIAGNOSTIC_ONLY")
    profile_excluded = ~hard["sector_profile"].eq(production_profile)
    raw_eligible = hard["quality_state"].isin(valid_states) & hard[
        "factor_value_raw"
    ].notna()
    production_gate = hard["factor_gate_status"].eq("ACCEPTED_PRODUCTION_CORE")
    peer_sufficient = hard["peer_group_count"].ge(min_peer)
    production_rows = (
        hard["factor_status"].eq("PRODUCTION_CORE")
        & ~profile_excluded
        & raw_eligible
        & production_gate
        & peer_sufficient
    )

    hard.loc[deferred, "hardening_state"] = "DEFERRED_HISTORY"
    hard.loc[deferred, "hardening_reason_codes"] = "HISTORY_LOOKBACK_UNAVAILABLE"
    hard.loc[diagnostic & ~profile_excluded & raw_eligible, "hardening_state"] = (
        "DIAGNOSTIC_ONLY"
    )
    hard.loc[diagnostic & ~profile_excluded & raw_eligible, "hardening_reason_codes"] = (
        "FACTOR_POLICY_DIAGNOSTIC_ONLY"
    )
    hard.loc[profile_excluded & ~deferred, "hardening_state"] = (
        "CONTROLLED_PROFILE_EXCLUSION"
    )
    hard.loc[profile_excluded & ~deferred, "hardening_reason_codes"] = (
        "PROFILE_NOT_AUTHORIZED_FOR_INDUSTRIAL_FACTOR_PACK"
    )
    hard.loc[production_rows, "hardening_state"] = "ACCEPTED"
    warning_rows = production_rows & (
        hard["quality_state"].eq("VALID_WITH_WARNING")
        | ~hard["tail_flag"].eq("NONE")
    )
    hard.loc[warning_rows, "hardening_state"] = "ACCEPTED_WITH_WARNING"
    hard.loc[production_rows & ~warning_rows, "hardening_reason_codes"] = "NONE"
    hard.loc[production_rows & hard["quality_state"].eq("VALID_WITH_WARNING"), "hardening_reason_codes"] = (
        "RAW_FACTOR_WARNING"
    )
    hard.loc[production_rows & ~hard["tail_flag"].eq("NONE"), "hardening_reason_codes"] = (
        "TAIL_WINSORIZED"
    )
    hard.loc[production_rows & ~warning_rows, "production_eligibility"] = "ELIGIBLE"
    hard.loc[warning_rows, "production_eligibility"] = "CONDITIONAL"

    non_hardened = ~hard["hardening_state"].isin(
        ["ACCEPTED", "ACCEPTED_WITH_WARNING", "DIAGNOSTIC_ONLY", "DEFERRED_HISTORY", "CONTROLLED_PROFILE_EXCLUSION"]
    )
    hard.loc[non_hardened, "hardening_state"] = "RAW_FACTOR_INELIGIBLE"
    hard.loc[non_hardened & hard["hardening_reason_codes"].eq("NONE"), "hardening_reason_codes"] = (
        "RAW_QUALITY_OR_FACTOR_GATE_FAILED"
    )
    hard.loc[~production_rows, "production_eligibility"] = "INELIGIBLE"
    hard["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
    hard["trade_authority"] = "NONE"

    tail_registry = (
        pd.concat(tail_rows, ignore_index=True)
        if tail_rows
        else pd.DataFrame(
            columns=[
                "symbol",
                "factor_id",
                "factor_value_raw",
                "factor_value_winsorized",
                "sector_profile",
                "quality_state",
                "tail_flag",
                "period_end",
                "as_of_timestamp",
                "lineage_id",
                "lower_limit",
                "upper_limit",
            ]
        )
    )
    if len(tail_registry):
        tail_registry["authority"] = "DATA_AND_RESEARCH_EVIDENCE_ONLY"
        tail_registry["trade_authority"] = "NONE"

    factor_registry = pd.DataFrame(factor_rows).sort_values("factor_id")
    distribution_registry = pd.DataFrame(distribution_rows).sort_values(
        ["factor_id", "sector_profile"]
    )
    ordered = hard.sort_values(["symbol", "factor_id"]).reset_index(drop=True)
    return (
        ordered,
        factor_registry,
        distribution_registry,
        tail_registry.sort_values(["factor_id", "symbol"]).reset_index(drop=True),
        profile_registry,
    )
