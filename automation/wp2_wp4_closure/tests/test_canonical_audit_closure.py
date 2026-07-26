from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "investment_os_runtime/00_CONTROL"
MERGE_SHA = "7b3cd0f154c8bdbab55ffabe149e21d69aa4fe7a"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stable(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def assert_hash(path: Path):
    payload = read_json(path)
    claimed = payload.pop("semantic_hash")
    assert stable(payload) == claimed


def test_execution_register_records_wp4_merge_and_blocks_wp5_until_r2():
    register = read_json(CONTROL / "EXECUTION_REGISTER_CURRENT.json")
    assert register["github_merge_sha"] == MERGE_SHA
    assert register["latest_governed_merge_sha"] == MERGE_SHA
    assert register["release_sequence"] == 15
    assert register["current_step"] == "R2_WP2_WP4_PRODUCT_CAPABILITY_HARDENING"
    assert register["overall_status"] == "R1_CANONICAL_AUDIT_CLOSED_R2_HARDENING_REQUIRED_WP5_BLOCKED"
    assert register["wp4"]["status"] == "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN"
    assert register["wp4"]["accepted_pr"] == 143
    assert register["wp4"]["accepted_merge_sha"] == MERGE_SHA
    assert register["wp4"]["full_professional_deep_research_complete"] is False
    assert register["wp4"]["position_level_portfolio_fit_complete"] is False
    assert register["wp5"]["status"] == "BLOCKED_PENDING_R2_PRODUCT_CAPABILITY_HARDENING"
    assert register["wp5"]["action_review_allowed"] is False
    assert register["trade_authority"] == "NONE"


def test_audit_closure_distinguishes_completed_baselines_from_missing_product_capabilities():
    closure = read_json(CONTROL / "WP2_WP4_CANONICAL_AUDIT_CLOSURE_RECORD.json")
    assert closure["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
    assert closure["accepted_wp4_pr"] == 143
    assert closure["accepted_wp4_merge_sha"] == MERGE_SHA
    assert closure["formal_conclusions"] == {
        "WP2": "BASELINE_COMPLETED_RECURRING_PORTFOLIO_CURRENT_PENDING",
        "WP3": "INITIAL_CANDIDATE_BASELINE_COMPLETED_CONTINUOUS_ENGINE_PENDING",
        "WP4": "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_FULL_DEEP_RESEARCH_PENDING",
        "WP5": "BLOCKED_PENDING_R2_PRODUCT_CAPABILITY_HARDENING",
    }
    assert len(closure["r2_required_capabilities"]) == 3
    assert closure["candidate_membership_mutations"] == 0
    assert closure["real_account_mutations"] == 0
    assert closure["simulation_trade_mutations"] == 0
    assert closure["orders"] == 0
    assert closure["trade_authority"] == "NONE"


def test_gap_register_is_explicit_complete_and_fail_closed():
    gaps = read_json(CONTROL / "WP2_WP4_CAPABILITY_GAP_REGISTER_CURRENT.json")
    assert gaps["gap_count"] == 16
    assert len(gaps["gaps"]) == 16
    assert {row["work_package"] for row in gaps["gaps"]} == {"WP2", "WP3", "WP4"}
    assert all(row["blocks_wp5"] is True for row in gaps["gaps"])
    assert all(row["automatic_state_mutation"] is False for row in gaps["gaps"])
    assert all(row["trade_authority"] == "NONE" for row in gaps["gaps"])
    limitations = {row["limitation"] for row in gaps["gaps"]}
    assert "RECURRING_PORTFOLIO_CURRENT_NOT_IMPLEMENTED" in limitations
    assert "DOWNSTREAM_CANDIDATE_REFRESH_NOT_SCHEDULED" in limitations
    assert "NOT_FULL_PROFESSIONAL_DEEP_RESEARCH" in limitations


def test_candidate_current_preserves_membership_and_updates_operating_stage_only():
    candidate_path = ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    candidate = read_json(candidate_path)
    assert candidate["counts"]["candidate_core"] == 2
    assert candidate["counts"]["shadow_track"] == 38
    assert candidate["counts"]["research_queue"] == 33
    assert candidate["counts"]["ready_for_user_decision"] == 0
    assert {row["security_id"] for row in candidate["candidate_core_members"]} == {"000333.SZ", "600900.SH"}
    assert candidate["current_operating_stage"] == "WP4_CORE2_INITIAL_BASELINE_ACCEPTED_R2_HARDENING_REQUIRED_WP5_BLOCKED"
    assert candidate["latest_governed_merge_sha"] == MERGE_SHA
    assert candidate["continuous_candidate_engine_complete"] is False
    assert candidate["candidate_outcome_windows_complete"] is False
    assert_hash(candidate_path)


def test_wp4_assets_are_accepted_but_maturity_claim_is_limited():
    acceptance = read_json(CONTROL / "WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_RECORD.json")
    research_path = ROOT / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json"
    decision_path = ROOT / "investment_os_runtime/30_STATE_CURRENT/50_DECISION_INTERFACE/WP4_DECISION_INTERFACE_CURRENT.json"
    research = read_json(research_path)
    decision = read_json(decision_path)

    assert acceptance["status"] == "ACCEPTED_ON_MAIN"
    assert acceptance["accepted_pr"] == 143
    assert acceptance["accepted_merge_sha"] == MERGE_SHA
    assert acceptance["completion_claim"] == "CORE2_INITIAL_PRODUCTION_BASELINE"
    assert acceptance["full_professional_deep_research_complete"] is False
    assert acceptance["position_level_portfolio_fit_complete"] is False
    assert acceptance["continuous_refresh_complete"] is False

    assert research["status"] == "ACCEPTED_ON_MAIN_INITIAL_BASELINE"
    assert research["record_count"] == 2
    assert research["full_professional_deep_research_complete"] is False
    assert research["continuous_filing_event_refresh_complete"] is False
    assert decision["status"] == "ACCEPTED_ON_MAIN_INITIAL_BASELINE"
    assert decision["record_count"] == 2
    assert decision["ready_for_user_decision_count"] == 0
    assert decision["position_sizing_grade"] is False
    assert decision["wp5_action_review_allowed"] is False
    assert decision["buy_signal_count"] == 0
    assert decision["portfolio_or_account_action_count"] == 0
    assert_hash(research_path)
    assert_hash(decision_path)


def test_authoritative_registry_points_to_wp4_and_r1_closure():
    registry = read_json(CONTROL / "AUTHORITATIVE_ASSET_REGISTRY.json")
    assert registry["github_merge_sha"] == MERGE_SHA
    assert registry["latest_governed_merge_sha"] == MERGE_SHA
    assert registry["release_sequence"] == 15
    assert registry["status"] == "GITHUB_CURRENT_WP4_INITIAL_BASELINE_ACCEPTED_R2_REQUIRED_FILE_LIBRARY_PENDING"
    assets = {row["asset_id"]: row for row in registry["assets"]}
    assert assets["GITHUB_ACTIVE_RUNTIME"]["status"] == "GITHUB_CURRENT_WP4_INITIAL_BASELINE_ACCEPTED_R2_REQUIRED"
    assert assets["WP4_CORE2_INITIAL_RESEARCH_CURRENT"]["status"] == "ACCEPTED_ON_MAIN_INITIAL_BASELINE"
    assert assets["WP4_DECISION_INTERFACE_CURRENT"]["status"] == "ACCEPTED_ON_MAIN_INITIAL_BASELINE"
    assert assets["WP4_CORE2_ACCEPTANCE"]["status"] == "ACCEPTED_ON_MAIN"
    assert assets["WP2_WP4_CANONICAL_AUDIT_CLOSURE"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"


def test_master_plan_does_not_overclaim_or_open_wp5():
    plan = (CONTROL / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md").read_text(encoding="utf-8")
    assert "WP2 | BASELINE COMPLETED" in plan
    assert "WP3 | INITIAL CANDIDATE BASELINE COMPLETED" in plan
    assert "WP4 | CORE2 INITIAL PRODUCTION BASELINE ACCEPTED ON MAIN" in plan
    assert "WP5 | BLOCKED" in plan
    assert "Recurring Portfolio Current未完成" in plan
    assert "持续财务/Candidate刷新及效果验证未完成" in plan
    assert "不等同于完整专业Deep Research" in plan
    assert "R2完成前不进入WP5" in plan
    assert "交易权限：`NONE`" in plan
