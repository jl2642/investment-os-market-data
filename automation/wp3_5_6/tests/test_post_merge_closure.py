from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MERGE_SHA = "f0b3b31927def71873767a727680f5d4ae2339c5"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stable(payload):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_candidate_current_is_unconditionally_accepted_on_main():
    state = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    assert state["status"] == "ACCEPTED_ON_MAIN"
    assert state["accepted_pr"] == 141
    assert state["accepted_merge_sha"] == MERGE_SHA
    assert state["current_operating_stage"] == "WP3_COMPLETED_WP4_READY_NOT_STARTED"
    assert state["counts"]["candidate_core"] == 2
    assert state["counts"]["shadow_track"] == 38
    assert state["counts"]["research_queue"] == 33
    assert state["counts"]["ready_for_user_decision"] == 0
    assert {row["security_name"] for row in state["candidate_core_members"]} == {"美的集团", "长江电力"}
    assert state["state_boundaries"]["candidate_state_transition"] == "GOVERNED_USER_MERGE_APPLIED"
    assert state["state_boundaries"]["real_account_mutations"] == 0
    assert state["state_boundaries"]["simulation_trade_mutations"] == 0
    assert state["state_boundaries"]["orders"] == 0
    assert state["state_boundaries"]["trade_authority"] == "NONE"


def test_candidate_semantic_hash_covers_post_merge_state():
    state = read_json(ROOT / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json")
    claimed = state.pop("semantic_hash")
    assert stable(state) == claimed


def test_execution_register_closes_wp3_and_opens_wp4_without_conditional_language():
    register = read_json(ROOT / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json")
    assert register["overall_status"] == "WP3_COMPLETED_ACCEPTED_ON_MAIN_WP4_READY_NOT_STARTED"
    assert register["current_step"] == "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION"
    assert register["latest_governed_merge_sha"] == MERGE_SHA
    assert register["wp3_5_6"]["status"] == "ACCEPTED_ON_MAIN"
    assert register["wp3_5_6"]["accepted_merge_sha"] == MERGE_SHA
    assert register["wp3_5_6"]["candidate_state_effective"] is True
    assert register["wp3_status"]["WP3-5"] == "COMPLETED_RESEARCH_OBJECT_ENTRY_BASELINE_ACCEPTED_ON_MAIN"
    assert register["wp3_status"]["WP3-6"] == "COMPLETED_CANDIDATE_REBUILD_ACCEPTED_ON_MAIN"
    assert register["state_preservation"]["candidate_core"] == 2
    assert register["state_preservation"]["candidate_shadow_track"] == 38
    assert register["state_preservation"]["candidate_research_queue"] == 33
    assert register["state_preservation"]["candidate_ready_for_user_decision"] == 0
    assert register["state_preservation"]["real_holdings"] == 7
    assert register["state_preservation"]["simulation_holdings"] == 16
    assert register["mutation_proof"]["real_account_mutations"] == 0
    assert register["mutation_proof"]["simulation_trade_mutations"] == 0
    assert register["mutation_proof"]["orders"] == 0
    assert register["trade_authority"] == "NONE"


def test_master_plan_has_no_stale_merge_condition():
    text = (ROOT / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md").read_text(encoding="utf-8")
    assert "WP3-5 + WP3-6 | COMPLETED / ACCEPTED ON MAIN" in text
    assert "WP4 | READY / NOT STARTED" in text
    assert "ACCEPTED IF THIS PR MERGES" not in text
    assert "READY AFTER MERGE" not in text
    assert "Candidate状态只在用户明确合并本PR后生效" not in text
    assert "美的集团、长江电力" in text
    assert "trade_authority=NONE" in text


def test_manifest_and_acceptance_record_match_actual_merge():
    proposal = ROOT / (
        "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_5_6/PROPOSALS/"
        "WP3_5_6_CANDIDATE_REBUILD_20260724_V1"
    )
    manifest = read_json(proposal / "WP3_5_6_MANIFEST.json")
    acceptance = read_json(ROOT / "investment_os_runtime/00_CONTROL/WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE_RECORD.json")
    assert manifest["status"] == "ACCEPTED_ON_MAIN"
    assert manifest["acceptance"]["accepted_merge_sha"] == MERGE_SHA
    assert manifest["acceptance"]["candidate_state_effective"] is True
    assert acceptance["status"] == "ACCEPTED_ON_MAIN"
    assert acceptance["accepted_merge_sha"] == MERGE_SHA
    assert acceptance["after"]["candidate_core"] == 2
    assert acceptance["after"]["historical_core20_moved_to_shadow"] == 18
    assert acceptance["after"]["valid_entry_baselines"] == 2
    assert acceptance["state_boundaries"]["real_account_mutations"] == 0
    assert acceptance["state_boundaries"]["simulation_trade_mutations"] == 0
    assert acceptance["state_boundaries"]["orders"] == 0
    assert acceptance["state_boundaries"]["trade_authority"] == "NONE"


def test_candidate_outcome_is_fail_closed_for_observation_not_missing_baseline():
    contract = read_json(ROOT / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_OUTCOME_CONTRACT.json")
    assert contract["current_status"] == "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS"
    assert contract["valid_entry_baseline_count"] == 2
    assert contract["completed_evaluation_windows"] == []
    assert contract["required_evaluation_windows"] == [20, 60, 120]
    assert contract["alpha_claim_allowed"] is False
    assert contract["fail_closed_until_observation_windows_complete"] is True
    assert contract["accepted_candidate_merge_sha"] == MERGE_SHA
    assert contract["trade_authority"] == "NONE"
    assert "pending_status_if_pr_merged" not in contract
    assert "pending_valid_entry_baseline_count_if_pr_merged" not in contract


def test_authoritative_registry_points_to_wp3_accepted_runtime():
    registry = read_json(ROOT / "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json")
    assert registry["registry_id"] == "WP3_5_6_AUTHORITATIVE_ASSET_REGISTRY_V8"
    assert registry["github_merge_sha"] == MERGE_SHA
    assert registry["release_sequence"] == 14
    assets = {row["asset_id"]: row for row in registry["assets"]}
    assert assets["GITHUB_ACTIVE_RUNTIME"]["status"] == "GITHUB_CURRENT_WP3_ACCEPTED"
    assert assets["WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE"]["status"] == "ACCEPTED_ON_MAIN"
    assert assets["WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE"]["merge_sha"] == MERGE_SHA
    assert registry["trade_authority"] == "NONE"
