from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline/hkcu_p3_2_candidate_pool_promotion.py"
SPEC = importlib.util.spec_from_file_location("p3_2", PIPELINE)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def load_contract():
    return json.loads((ROOT / "config/hkcu_p3_2_candidate_pool_promotion_contract.json").read_text(encoding="utf-8"))


def sample_row(proposal: str) -> pd.Series:
    return pd.Series(
        {
            "p2a_overall_rank": 1,
            "security_id": "HKEX:00001",
            "stock_code_5d": "00001",
            "security_name": "TEST",
            "primary_sleeve": "QUALITY_COMPOUNDER",
            "valuation_support_state": "SUPPORTIVE",
            "thesis_strength": "COMPANY_EVIDENCE_SUPPORTED",
            "investment_thesis": "Thesis",
            "principal_falsifier": "Falsifier",
            "monitor_triggers": "Monitor",
            "ah_pair_status": "NOT_APPLICABLE",
            "ah_relative_value_direction": "",
            "h_discount_to_a_pct": "",
            "material_confidence_cap_count": 0,
            "bounded_confidence_cap_count": 0,
            "proposal_state": proposal,
            "proposal_reason": "Accepted P3-1 route",
        }
    )


def test_contract_pins_exact_accepted_p3_1_artifact_and_counts():
    c = load_contract()
    assert c["authoritative_inputs"]["accepted_p3_1_head_sha"] == "e475adb24ba4af02720bbf20874440e2039979c9"
    assert c["authoritative_inputs"]["accepted_p3_1_artifact_digest"].startswith("sha256:")
    assert c["entry_contract"]["proposal_state_counts"] == {
        "PROPOSE_CORE_CANDIDATE": 2,
        "PROPOSE_WATCH_CANDIDATE": 68,
        "DEFER_RESEARCH_MONITOR": 2,
        "HOLD_RETAINED_INVESTMENT_BLOCKER": 5,
    }


def test_only_core_and_watch_are_formal_candidate_members():
    c = load_contract()
    m = c["promotion_mapping"]
    assert m["PROPOSE_CORE_CANDIDATE"]["candidate_member"] is True
    assert m["PROPOSE_WATCH_CANDIDATE"]["candidate_member"] is True
    assert m["DEFER_RESEARCH_MONITOR"]["candidate_member"] is False
    assert m["HOLD_RETAINED_INVESTMENT_BLOCKER"]["candidate_member"] is False


def test_candidate_promotion_does_not_authorize_portfolio_or_trading():
    c = load_contract()
    b = c["phase_boundary"]
    assert b["formal_hk_candidate_graduation_authorized"] is True
    assert b["hk_candidate_pool_mutation_authorized"] is True
    assert b["a_share_candidate_mutation_authorized"] is False
    assert b["simulation_mutation_authorized"] is False
    assert b["real_account_mutation_authorized"] is False
    assert b["portfolio_allocation_authorized"] is False
    assert b["order_creation_authorized"] is False
    assert b["trade_authority"] == "NONE"


def test_candidate_row_preserves_tier_and_zero_downstream_authority():
    r = MOD.candidate_row(sample_row("PROPOSE_CORE_CANDIDATE"), "CORE", "2026-08-07")
    assert r["candidate_tier"] == "CORE"
    assert r["formal_candidate_graduation"] is True
    assert r["portfolio_allocation_authorized"] is False
    assert r["simulation_admission_authorized"] is False
    assert r["real_account_admission_authorized"] is False
    assert r["orders_created"] == 0
    assert r["trade_authority"] == "NONE"


def test_monitor_row_never_becomes_candidate_member():
    r = MOD.monitor_row(sample_row("DEFER_RESEARCH_MONITOR"), "RESEARCH_MONITOR", "2026-08-07")
    assert r["candidate_member"] is False
    assert r["formal_candidate_graduation"] is False
    assert r["trade_authority"] == "NONE"


def test_ledger_is_explicit_first_promotion_transition():
    c = load_contract()
    m = c["promotion_mapping"]["PROPOSE_WATCH_CANDIDATE"]
    r = MOD.ledger_row(sample_row("PROPOSE_WATCH_CANDIDATE"), m, "2026-08-07")
    assert r["from_state"] == "NOT_HK_CANDIDATE"
    assert r["to_state"] == "HK_CANDIDATE_WATCH"
    assert r["transition_action"] == "ADMIT_WATCH"
    assert r["formal_candidate_member"] is True
    assert r["a_share_candidate_mutation"] is False
    assert r["simulation_mutation"] is False
    assert r["real_account_mutation"] is False


def test_phase_three_closes_into_portfolio_fit_not_portfolio_allocation():
    c = load_contract()
    assert c["acceptance"]["formal_candidate_count"] == 70
    assert c["acceptance"]["next_gate"] == "P4_0_PORTFOLIO_FIT_CONTRACT"
