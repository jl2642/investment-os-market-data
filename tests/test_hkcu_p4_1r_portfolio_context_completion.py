from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

from pipeline.hkcu_p4_1r_canonical_data_adapter import (
    canonical_first_holding_fetcher,
    load_hk_histories_compat,
)

ROOT = Path(__file__).resolve().parents[1]


def contract() -> dict:
    return json.loads((ROOT / "config/hkcu_p4_1r_portfolio_context_completion_contract.json").read_text(encoding="utf-8"))


def test_entry_and_boundaries() -> None:
    c = contract()
    assert c["program_id"] == "HKCU-P4-1R"
    assert c["entry_contract"]["candidate_count"] == 70
    assert c["entry_contract"]["account_security_context_count"] == 140
    assert set(c["entry_contract"]["required_global_gap_ids"]) == {"CTX_SECTOR_INDUSTRY","CTX_PORTFOLIO_FACTOR_LOOKTHROUGH","CTX_MARGINAL_RISK","CTX_EXPECTED_RETURN_OPPORTUNITY_COST"}
    assert c["phase_boundary"]["context_completion_authorized"] is True
    assert c["phase_boundary"]["portfolio_fit_reassessment_authorized"] is True
    for k in ["candidate_pool_mutation_authorized","simulation_mutation_authorized","real_account_mutation_authorized","portfolio_allocation_authorized","position_sizing_authorized","order_creation_authorized"]:
        assert c["phase_boundary"][k] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_evidence_controls() -> None:
    c = contract(); p = c["evidence_policy"]
    assert p["fuzzy_name_identity_matching_allowed"] is False
    assert p["sector_neutral_fill_allowed"] is False
    assert p["ticker_count_diversification_inference_allowed"] is False
    assert p["trailing_return_may_be_called_expected_return"] is False
    assert p["ah_discount_may_be_called_alpha"] is False
    assert p["pooled_fund_or_etf_may_be_assigned_single_industry"] is False
    assert c["opportunity_cost_policy"]["method"] == "PARETO_CONTEXT_NO_WEIGHTED_SCORE"
    assert c["opportunity_cost_policy"]["fixed_top_n"] is False


def test_canonical_sleeves_are_mapped() -> None:
    m = contract()["style_taxonomy"]
    assert set(["QUALITY_COMPOUNDER","HIGH_DIVIDEND_VALUE","TREND_LIQUIDITY","DEFENSIVE_STABILITY","RECOVERY_WATCH"]).issubset(m)
    assert len({m[x] for x in ["QUALITY_COMPOUNDER","HIGH_DIVIDEND_VALUE","TREND_LIQUIDITY","DEFENSIVE_STABILITY","RECOVERY_WATCH"]}) == 5


def test_acceptance_is_context_only() -> None:
    a = contract()["acceptance"]
    assert a["candidate_context_count"] == 70
    assert a["account_holding_context_count"] == 24
    assert a["account_security_context_count"] == 140
    for k in ["candidate_pool_mutations","simulation_mutations","real_account_mutations","portfolio_allocations","orders_created"]:
        assert a[k] == 0
    assert a["trade_authority"] == "NONE"


def test_fmdl5c_current_schema_observation_date_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "fmdl5c.parquet"
    pd.DataFrame(
        {
            "security_id": ["HKEX:00005", "HKEX:00005", "HKEX:00941"],
            "stock_code_5d": ["00005", "00005", "00941"],
            "provider_ticker": ["00005.HK", "00005.HK", "00941.HK"],
            "observation_date": ["2026-08-06", "2026-08-07", "2026-08-07"],
            "adj_close": [98.0, 100.0, 72.0],
            "close": [98.0, 100.0, 72.0],
        }
    ).to_parquet(path, index=False)
    histories, min_date, max_date = load_hk_histories_compat(path)
    assert min_date == "2026-08-06"
    assert max_date == "2026-08-07"
    assert histories["HKEX:00005"].tolist() == [98.0, 100.0]
    assert histories["HKEX:00941"].tolist() == [72.0]


def test_holding_history_prefers_canonical_before_fallback() -> None:
    idx = pd.to_datetime(["2026-08-05", "2026-08-06", "2026-08-07"])
    canonical = {"000333.SZ": pd.Series([80.0, 81.0, 83.5], index=idx, dtype=float)}
    calls: list[str] = []

    def fallback(h: dict, as_of: str) -> pd.Series:
        calls.append(str(h.get("security_id")))
        return pd.Series(dtype=float)

    fetch = canonical_first_holding_fetcher(canonical, fallback)
    got = fetch({"security_id": "000333.SZ"}, "2026-08-07")
    assert got.tolist() == [80.0, 81.0, 83.5]
    assert calls == []

    fetch({"security_id": "510500.SH"}, "2026-08-07")
    assert calls == ["510500.SH"]
