from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / os.environ.get(
    "WP4_OUTPUT_DIR",
    "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP4/PROPOSALS/WP4_CORE2_DECISION_INTERFACE_20260726_V1",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def test_wp4_covers_exact_accepted_core_without_candidate_mutation():
    candidate = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    assert candidate["status"] == "ACCEPTED_ON_MAIN"
    assert {row["security_id"] for row in candidate["candidate_core_members"]} == {"000333.SZ", "600900.SH"}
    assert candidate["counts"]["candidate_core"] == 2
    assert candidate["counts"]["shadow_track"] == 38
    assert candidate["counts"]["research_queue"] == 33
    assert candidate["counts"]["ready_for_user_decision"] == 0


def test_source_register_is_primary_first_and_no_unsupported_fill():
    register = read_json(OUTPUT / "WP4_SOURCE_REGISTER.json")
    assert register["source_count"] == 5
    assert register["source_hierarchy"][0] == "OFFICIAL_REGULATORY_FILINGS"
    assert register["unsupported_fact_fill"] == "PROHIBITED"
    assert all(source["source_type"].startswith("OFFICIAL") or source["source_type"].startswith("REGULATORY") for source in register["sources"])
    assert register["trade_authority"] == "NONE"


def test_deep_research_separates_facts_assumptions_and_inference():
    rows = read_jsonl(OUTPUT / "WP4_DEEP_RESEARCH_CORE2.jsonl")
    assert len(rows) == 2
    assert {row["security_id"] for row in rows} == {"000333.SZ", "600900.SH"}
    for row in rows:
        boundary = row["fact_assumption_inference_boundary"]
        assert boundary["facts"] == "SOURCE_REGISTER_AND_ACCEPTED_MARKET_BINDING_ONLY"
        assert boundary["assumptions"] == "VALUATION_SCENARIOS_EXPLICITLY_LABELLED"
        assert boundary["unsupported_fill"] == "PROHIBITED"
        assert row["research_grade"] == "CONDITIONAL_DECISION_GRADE"
        assert row["ready_for_user_decision"] is False
        claimed = row.pop("semantic_hash")
        assert stable(row) == claimed


def test_valuation_math_is_explicit_and_current_price_has_limited_base_upside():
    rows = read_jsonl(OUTPUT / "WP4_DECISION_GRADE_VALUATION_CORE2.jsonl")
    assert len(rows) == 2
    for row in rows:
        assert row["valuation_grade"] == "DECISION_GRADE_ASSUMPTION_EXPLICIT"
        assert row["valuation_not_forecast"] is True
        assert row["assumption_change_requires_new_proposal"] is True
        for scenario in row["scenarios"]:
            expected = round(scenario["normalized_eps_rmb"] * scenario["pe_multiple"], 2)
            assert expected == scenario["fair_value_rmb"]
            assert scenario["classification"] == "ASSUMPTION_SCENARIO_NOT_FORECAST"
        assert -2.0 <= row["base_case_upside_downside_pct"] <= 6.0
        assert row["trade_authority"] == "NONE"


def test_portfolio_fit_fails_closed_without_position_level_current():
    rows = read_jsonl(OUTPUT / "WP4_PORTFOLIO_FIT_CORE2.jsonl")
    assert len(rows) == 2
    for row in rows:
        assert row["fit_grade"] == "DIRECTIONAL_ROLE_GRADE_NOT_POSITION_SIZING_GRADE"
        assert row["concentration_assessment"] == "BLOCKED_POSITION_LEVEL_CURRENT_NOT_AVAILABLE"
        assert row["portfolio_decision"] == "NO_ALLOCATION_OR_MIGRATION_PROPOSAL"
        assert "BROKER_VERIFIED_FALSE" in row["limitations"]
        assert row["real_account_mutations"] == 0
        assert row["simulation_trade_mutations"] == 0
        assert row["orders"] == 0


def test_decision_interface_has_no_forced_action():
    rows = read_jsonl(OUTPUT / "WP4_DECISION_INTERFACE_CORE2.jsonl")
    assert len(rows) == 2
    assert {row["decision_status"] for row in rows} == {
        "WATCH_FOR_EVIDENCE_AND_PRICE",
        "HOLD_FOR_EVIDENCE_OR_BETTER_ENTRY",
    }
    for row in rows:
        assert row["ready_for_user_decision"] is False
        assert row["buy_signal"] == "NO"
        assert row["add_signal"] == "NO"
        assert row["reduce_signal"] == "NO"
        assert row["sell_signal"] == "NO"
        assert row["automatic_trade"] is False
        assert row["candidate_membership_mutations"] == 0
        assert row["real_account_mutations"] == 0
        assert row["simulation_trade_mutations"] == 0
        assert row["orders"] == 0
        assert row["trade_authority"] == "NONE"


def test_current_states_and_acceptance_are_merge_semantic_not_post_merge_patch_dependent():
    research = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json")
    decision = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/50_DECISION_INTERFACE/WP4_DECISION_INTERFACE_CURRENT.json")
    acceptance = read_json(ROOT / "investment_os_runtime/00_CONTROL/WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_RECORD.json")
    for state in (research, decision, acceptance):
        assert state["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert state["promotion_rule"] == "FILES_BECOME_CURRENT_ONLY_WHEN_PRESENT_ON_MAIN_VIA_GOVERNED_USER_MERGE"
        assert state["trade_authority"] == "NONE"
    assert decision["ready_for_user_decision_count"] == 0
    assert decision["portfolio_or_account_action_count"] == 0
    assert acceptance["candidate_membership_mutations"] == 0
    assert acceptance["real_account_mutations"] == 0
    assert acceptance["simulation_trade_mutations"] == 0
    assert acceptance["orders"] == 0


def test_manifest_and_operating_state_open_wp5_without_claiming_action():
    manifest = read_json(OUTPUT / "WP4_MANIFEST.json")
    register = read_json(ROOT / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json")
    plan = (ROOT / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md").read_text(encoding="utf-8")
    assert manifest["metrics"]["core_security_count"] == 2
    assert manifest["metrics"]["ready_for_user_decision"] == 0
    assert manifest["metrics"]["orders"] == 0
    assert register["wp4"]["status"] == "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    assert register["current_step"] == "WP5_PORTFOLIO_MIGRATION_AND_ACTION_REVIEW"
    assert register["wp4"]["ready_for_user_decision"] == 0
    assert "WP4 | COMPLETED IF PRESENT ON MAIN" in plan
    assert "0只Ready → NO ACTION" in plan
    assert register["trade_authority"] == "NONE"
