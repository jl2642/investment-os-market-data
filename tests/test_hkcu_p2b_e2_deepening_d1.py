from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_deepening_d1_contract.json"


def test_d1_contract_closes_only_negative_catalyst_gaps():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["negative_evidence_policy"]["target_dimension"] == "CATALYST"
    assert c["negative_evidence_policy"]["required_prior_status"] == "RESEARCH_REQUIRED"
    assert c["negative_evidence_policy"]["negative_finding"] == "NO_QUALIFYING_ACTIVE_CATALYST"
    assert c["negative_evidence_policy"]["negative_finding_is_not_bearish_score"] is True
    assert c["negative_evidence_policy"]["no_alpha_score"] is True
    assert c["expected_target_count"] == 23
    assert len(c["expected_target_codes"]) == 23


def test_d1_expected_cumulative_state_has_no_unstarted_company_tasks():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = c["expected_cumulative_after_d1"]
    assert expected["company_specific_dimension_rows"] == 231
    assert expected["EVIDENCE_COMPLETE"] == 45
    assert expected["EVIDENCE_PARTIAL"] == 186
    assert expected["RESEARCH_REQUIRED"] == 0
    assert expected["company_specific_open_tasks"] == 186
    assert expected["company_specific_unstarted_tasks"] == 0
    assert expected["all_77_securities_started"] is True


def test_d1_keeps_protected_state_closed():
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    a = c["acceptance"]
    assert a["score_non_null_count"] == 0
    assert a["candidate_pool_mutations"] == 0
    assert a["simulation_mutations"] == 0
    assert a["real_account_mutations"] == 0
    assert a["orders_created"] == 0
    assert a["formal_candidate_graduation_allowed"] is False
    assert a["trade_authority"] == "NONE"
