from __future__ import annotations
import json
from pathlib import Path

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
