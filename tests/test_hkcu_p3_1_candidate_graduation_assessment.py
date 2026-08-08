from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline/hkcu_p3_1_candidate_graduation_assessment.py"
SPEC = importlib.util.spec_from_file_location("p3_1", PIPELINE)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def test_contract_preserves_p3_0_rule_count_and_zero_mutation_boundary():
    contract = json.loads((ROOT / "config/hkcu_p3_1_candidate_graduation_assessment_contract.json").read_text(encoding="utf-8"))
    assert contract["entry_contract"]["graduation_rule_count"] == 12
    assert contract["entry_contract"]["entry_security_count"] == 77
    assert contract["entry_contract"]["retained_blocker_security_count"] == 5
    assert contract["entry_contract"]["rule_assessment_row_count"] == 924
    assert contract["assessment_policy"]["weighted_composite_score_allowed"] is False
    assert contract["assessment_policy"]["neutral_fill_allowed"] is False
    assert contract["assessment_policy"]["arbitrary_fixed_top_n_allowed"] is False
    assert contract["phase_boundary"]["candidate_pool_mutations"] == 0
    assert contract["phase_boundary"]["trade_authority"] == "NONE"


def test_valuation_support_never_uses_ah_discount_as_substitute():
    state, passed, _ = MOD.valuation_support(pd.Series({"earnings_yield": "", "pe_ratio": "", "dividend_yield_365d": "", "h_discount_to_a_pct": 35.0}))
    assert state == "MISSING"
    assert passed is False


def test_valuation_support_positive_earnings_or_dividend_is_supportive():
    state, passed, _ = MOD.valuation_support(pd.Series({"earnings_yield": 0.08, "pe_ratio": 12.5, "dividend_yield_365d": 0.03}))
    assert state == "SUPPORTIVE"
    assert passed is True


def test_valuation_call_site_uses_canonical_hkcu_row():
    source = PIPELINE.read_text(encoding="utf-8")
    assert "valuation_support(pd.Series(h))" in source
    assert "valuation_support(pd.Series(s._asdict()))" not in source


def test_thesis_package_is_evidence_tied_and_has_falsifier_monitor():
    grp = pd.DataFrame(
        [
            {
                "research_dimension": "EARNINGS_EXPECTATION_REVISION",
                "final_direction": "POSITIVE",
                "final_finding": "CURRENT_POSITIVE_H1_OPERATING_EVIDENCE",
                "final_dimension_state": "EVIDENCE_COMPLETE",
                "next_required_evidence": "Continue routine issuer monitoring.",
                "monitor_trigger": "Next interim or annual results.",
            },
            {
                "research_dimension": "CATALYST",
                "final_direction": "NEUTRAL",
                "final_finding": "NO_QUALIFYING_ACTIVE_CATALYST",
                "final_dimension_state": "MONITOR_ONLY",
                "next_required_evidence": "No action until a new catalyst appears.",
                "monitor_trigger": "New company-specific catalyst disclosure.",
            },
            {
                "research_dimension": "GOVERNANCE_VALUE_TRAP",
                "final_direction": "NEUTRAL",
                "final_finding": "ROUTINE_GOVERNANCE_MONITOR",
                "final_dimension_state": "MONITOR_ONLY",
                "next_required_evidence": "Continue monitoring.",
                "monitor_trigger": "New governance disclosure.",
            },
        ]
    )
    thesis, falsifier, monitor, strength = MOD.thesis_package(grp, pd.Series({"primary_sleeve": "QUALITY_COMPOUNDER"}))
    assert "CURRENT_POSITIVE_H1_OPERATING_EVIDENCE" in thesis
    assert "falsifier" in falsifier.lower()
    assert "Next interim or annual results." in monitor
    assert strength == "COMPANY_EVIDENCE_SUPPORTED"


def test_assessment_states_are_proposals_not_formal_promotions():
    contract = json.loads((ROOT / "config/hkcu_p3_1_candidate_graduation_assessment_contract.json").read_text(encoding="utf-8"))
    assert set(contract["proposal_states"]) == {
        "PROPOSE_CORE_CANDIDATE",
        "PROPOSE_WATCH_CANDIDATE",
        "DEFER_RESEARCH_MONITOR",
        "HOLD_RETAINED_INVESTMENT_BLOCKER",
    }
    assert contract["acceptance"]["formal_candidate_graduation_count"] == 0
    assert contract["acceptance"]["next_gate"] == "P3_2_CANDIDATE_POOL_PROMOTION"
