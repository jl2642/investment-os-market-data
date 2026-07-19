from __future__ import annotations

import pandas as pd

from scripts.fmdl3cc_core import (
    build_profile_registry,
    harden_factor_current,
    profile_reconciliation_status,
)


def config():
    return {
        "hardening": {
            "valid_raw_quality_states": ["VALID", "VALID_WITH_WARNING"],
            "production_profile": "GENERAL_NON_FINANCIAL",
            "minimum_peer_group_size": 3,
            "robust_zscore_clip": 5.0,
        }
    }


def policy(status="PRODUCTION_CORE", percentile=True, minimum=0.60):
    return pd.DataFrame(
        [
            {
                "factor_id": "FIN_TEST",
                "factor_status": status,
                "minimum_coverage_ratio": minimum,
                "winsor_lower_quantile": 0.01,
                "winsor_upper_quantile": 0.99,
                "percentile_authorized": percentile,
                "policy_reason": "test",
            }
        ]
    )


def profiles():
    return pd.DataFrame(
        [
            {"symbol": "000001.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"},
            {"symbol": "000002.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"},
            {"symbol": "000003.SZ", "sector_profile": "GENERAL_NON_FINANCIAL"},
            {"symbol": "600000.SH", "sector_profile": "BANK"},
        ]
    )


def current(values, states=None, direction="HIGHER_BETTER"):
    states = states or ["VALID"] * len(values)
    symbols = ["000001.SZ", "000002.SZ", "000003.SZ", "600000.SH"][: len(values)]
    sectors = [
        "GENERAL_NON_FINANCIAL",
        "GENERAL_NON_FINANCIAL",
        "GENERAL_NON_FINANCIAL",
        "BANK",
    ][: len(values)]
    return pd.DataFrame(
        {
            "symbol": symbols,
            "factor_id": ["FIN_TEST"] * len(values),
            "factor_value": values,
            "quality_state": states,
            "economic_direction": [direction] * len(values),
            "sector_profile": sectors,
            "period_end": ["2025-12-31"] * len(values),
            "as_of_timestamp": ["2026-03-31T09:30:00+08:00"] * len(values),
            "lineage_id": [f"l{i}" for i in range(len(values))],
            "trade_authority": ["NONE"] * len(values),
        }
    )


def test_profile_reconciliation_is_fail_closed():
    assert (
        profile_reconciliation_status("GENERAL_NON_FINANCIAL")
        == "COARSE_PROFILE_ACCEPTED_FOR_HARDENING"
    )
    assert (
        profile_reconciliation_status("BANK")
        == "CONTROLLED_EXCLUSION_PENDING_SECTOR_FACTOR_PACK"
    )
    assert (
        profile_reconciliation_status("UNRESOLVED")
        == "CONTROLLED_EXCLUSION_UNRESOLVED"
    )
    registry = build_profile_registry(profiles())
    assert not registry["industry_neutral_scoring_authorized"].any()


def test_production_factor_is_winsorized_and_ranked():
    hardened, registry, _, tails, _ = harden_factor_current(
        current([1.0, 2.0, 100.0, 3.0]),
        profiles(),
        policy(),
        config(),
    )
    general = hardened[hardened["sector_profile"].eq("GENERAL_NON_FINANCIAL")]
    assert registry.iloc[0]["factor_gate_status"] == "ACCEPTED_PRODUCTION_CORE"
    assert general["factor_value_winsorized"].notna().all()
    assert general["directional_percentile"].between(0, 1).all()
    assert general["production_eligibility"].isin(["ELIGIBLE", "CONDITIONAL"]).all()
    assert len(tails) == 2
    bank = hardened[hardened["sector_profile"].eq("BANK")].iloc[0]
    assert bank["hardening_state"] == "CONTROLLED_PROFILE_EXCLUSION"
    assert bank["production_eligibility"] == "INELIGIBLE"


def test_diagnostic_and_deferred_factors_never_enter_production():
    diagnostic, _, _, _, _ = harden_factor_current(
        current([1.0, 2.0, 3.0]),
        profiles().iloc[:3],
        policy(status="DIAGNOSTIC_ONLY", percentile=False, minimum=0.0),
        config(),
    )
    assert diagnostic["hardening_state"].eq("DIAGNOSTIC_ONLY").all()
    assert diagnostic["production_eligibility"].eq("INELIGIBLE").all()
    assert diagnostic["directional_percentile"].isna().all()

    deferred, _, _, _, _ = harden_factor_current(
        current([None, None, None], states=["MISSING_REQUIRED_INPUT"] * 3),
        profiles().iloc[:3],
        policy(status="DEFERRED_HISTORY", percentile=False, minimum=0.0),
        config(),
    )
    assert deferred["hardening_state"].eq("DEFERRED_HISTORY").all()
    assert deferred["production_eligibility"].eq("INELIGIBLE").all()


def test_coverage_gate_blocks_undercovered_core_factor():
    hardened, registry, _, _, _ = harden_factor_current(
        current(
            [1.0, None, None],
            states=["VALID", "MISSING_REQUIRED_INPUT", "MISSING_REQUIRED_INPUT"],
        ),
        profiles().iloc[:3],
        policy(minimum=0.60),
        config(),
    )
    assert registry.iloc[0]["factor_gate_status"] == "BLOCKED_PRODUCTION_COVERAGE"
    assert hardened["production_eligibility"].eq("INELIGIBLE").all()


def test_lower_better_percentile_is_reversed():
    hardened, _, _, _, _ = harden_factor_current(
        current([1.0, 2.0, 3.0], direction="LOWER_BETTER"),
        profiles().iloc[:3],
        policy(),
        config(),
    )
    ranked = hardened.set_index("symbol")["directional_percentile"]
    assert ranked["000001.SZ"] > ranked["000003.SZ"]
