from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.hkcu_p4_1_portfolio_fit_assessment import build

ROOT = Path(__file__).resolve().parents[1]


def test_p4_1_contract_boundary_and_counts() -> None:
    c = json.loads((ROOT / "config/hkcu_p4_1_portfolio_fit_assessment_contract.json").read_text(encoding="utf-8"))
    assert c["program_id"] == "HKCU-P4-1"
    assert c["entry_contract"]["entry_candidate_count"] == 70
    assert c["entry_contract"]["account_security_assessment_count"] == 140
    assert c["entry_contract"]["rule_assessment_row_count"] == 2100
    assert c["portfolio_context_policy"]["sector_or_industry_neutral_fill_allowed"] is False
    assert c["portfolio_context_policy"]["primary_sleeve_may_substitute_for_sector_classification"] is False
    assert c["portfolio_context_policy"]["diversification_claim_without_portfolio_evidence_allowed"] is False
    assert c["phase_boundary"]["assessment_authorized"] is True
    for k in ["candidate_pool_mutation_authorized", "simulation_admission_authorized", "simulation_mutation_authorized",
              "real_account_admission_authorized", "real_account_mutation_authorized", "portfolio_allocation_authorized",
              "order_creation_authorized"]:
        assert c["phase_boundary"][k] is False
    assert c["phase_boundary"]["trade_authority"] == "NONE"


def test_real_p4_1_assessment_is_complete_and_fail_closed(tmp_path: Path) -> None:
    decision = build(ROOT, tmp_path)
    assert decision["status"] == "BLOCKED_P4_1_PORTFOLIO_CONTEXT"
    assert decision["next_gate"] == "P4_1R_PORTFOLIO_CONTEXT_COMPLETION"
    assert decision["entry_candidate_count"] == 70
    assert decision["account_security_assessment_count"] == 140
    assert decision["rule_assessment_row_count"] == 2100
    assert decision["candidate_pool_mutations"] == 0
    assert decision["simulation_mutations"] == 0
    assert decision["real_account_mutations"] == 0
    assert decision["portfolio_allocations"] == 0
    assert decision["orders_created"] == 0
    assert decision["trade_authority"] == "NONE"

    rules = pd.read_csv(tmp_path / "HKCU_P4_1_RULE_ASSESSMENT.csv", keep_default_na=False)
    account = pd.read_csv(tmp_path / "HKCU_P4_1_ACCOUNT_SECURITY_ASSESSMENT.csv", keep_default_na=False)
    combined = pd.read_csv(tmp_path / "HKCU_P4_1_COMBINED_ROUTING.csv", keep_default_na=False)
    gaps = pd.read_csv(tmp_path / "HKCU_P4_1_CONTEXT_GAP_REGISTER.csv", keep_default_na=False)
    assert len(rules) == 2100
    assert len(account) == 140
    assert len(combined) == 70
    assert len(gaps) >= 4
    for rid in ["P4R10", "P4R11", "P4R12", "P4R13"]:
        assert rules.loc[rules["rule_id"].eq(rid), "rule_state"].eq("DEFER").all()
    assert account["fit_state"].eq("DEFER_PORTFOLIO_CONTEXT").all()
    assert combined["combined_route"].eq("DEFER_PORTFOLIO_CONTEXT").all()
