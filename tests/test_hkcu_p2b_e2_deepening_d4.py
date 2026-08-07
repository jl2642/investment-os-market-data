from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/hkcu_p2b_e2_deepening_d4_contract.json"
EVIDENCE = ROOT / "evidence/hkcu_p2b/HKCU_P2B_E2_D4_TOP20_REMAINING_BLOCKER_EVIDENCE_20260807.csv"


def load():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    evidence = pd.read_csv(EVIDENCE, dtype={"stock_code_5d": str}, keep_default_na=False)
    post = evidence["post_blocker"].astype(str).str.lower().isin(["true", "1"])
    return contract, evidence, post


def test_d4_contract_exact_remaining_surface():
    contract, evidence, post = load()
    assert contract["selection_policy"]["expected_target_rows"] == 12
    assert contract["selection_policy"]["expected_security_count"] == 10
    assert len(evidence) == 12
    assert evidence["security_id"].nunique() == 10
    assert int(post.sum()) == 2
    assert contract["next_gate"] == "P2B_E2_TOP20_DECISION_SYNTHESIS"
    assert contract["acceptance"]["formal_candidate_graduation_allowed"] is False
    assert contract["trade_authority"] == "NONE"


def test_retained_blockers_are_fresh_negative_signals():
    contract, evidence, post = load()
    keys = set(evidence.loc[post, "security_id"] + "|" + evidence.loc[post, "research_dimension"])
    assert keys == set(contract["expected_retained_blocker_keys"])
    retained = evidence.loc[post]
    assert retained["resolution_direction"].eq("NEGATIVE").all()
    assert retained["post_finding"].str.contains("NEGATIVE_EARNINGS", case=False).all()
    assert retained["decision_effect"].eq("RETAIN_BLOCKER").all()


def test_pending_value_unlock_is_confidence_cap_not_blocker():
    _, evidence, _ = load()
    pending = evidence[
        evidence["security_id"].isin(["HKEX:00300", "HKEX:01530"])
        & evidence["research_dimension"].eq("CATALYST")
    ]
    assert len(pending) == 2
    assert not pending["post_blocker"].astype(str).str.lower().isin(["true", "1"]).any()
    assert pending["decision_effect"].eq("CONFIDENCE_CAP").all()


def test_missing_current_earnings_data_is_not_bearish():
    _, evidence, _ = load()
    missing = evidence[
        evidence["research_dimension"].eq("EARNINGS_EXPECTATION_REVISION")
        & evidence["resolution_direction"].eq("UNKNOWN")
    ]
    assert set(missing["security_id"]) == {"HKEX:01530", "HKEX:00440"}
    assert not missing["post_blocker"].astype(str).str.lower().isin(["true", "1"]).any()
    assert missing["decision_effect"].eq("CONFIDENCE_CAP").all()


def test_current_results_clear_stale_evidence_blockers():
    _, evidence, _ = load()
    current = evidence[
        evidence["security_id"].isin(["HKEX:01308", "HKEX:00669", "HKEX:01997"])
        & evidence["research_dimension"].eq("EARNINGS_EXPECTATION_REVISION")
    ]
    assert len(current) == 3
    assert not current["post_blocker"].astype(str).str.lower().isin(["true", "1"]).any()
    assert set(current["resolution_direction"]).issubset({"MIXED", "POSITIVE"})


def test_succession_is_resolved_for_china_mobile_and_stanchart():
    _, evidence, _ = load()
    leadership = evidence[
        evidence["security_id"].isin(["HKEX:00941", "HKEX:02888"])
        & evidence["research_dimension"].eq("GOVERNANCE_VALUE_TRAP")
    ]
    assert len(leadership) == 2
    assert leadership["post_finding"].eq("SENIOR_LEADERSHIP_SUCCESSION_RESOLVED").all()
    assert not leadership["post_blocker"].astype(str).str.lower().isin(["true", "1"]).any()
