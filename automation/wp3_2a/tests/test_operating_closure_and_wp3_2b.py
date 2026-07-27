from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BINDING = ROOT / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
ACCEPTANCE = ROOT / "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_ACCEPTANCE_RECORD.json"
SCOPE = ROOT / "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_SCOPE_EXCEPTIONS_CURRENT.json"
REGISTER = ROOT / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
MASTER_PLAN = ROOT / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
UNIVERSE_WORKFLOW = ROOT / ".github/workflows/wp3_2a_universe_refresh.yml"
SCREENING_WORKFLOW = ROOT / ".github/workflows/wp3_2a_governed_screening.yml"
SCREENING_BRIDGE = ROOT / ".github/workflows/wp3_2b_screening_connector_bridge.yml"
SCREENING_SCRIPT = ROOT / "automation/wp3_2a/governed_screening.py"
ACCEPT_SCRIPT = ROOT / "automation/wp3_2a/accept_data_proposal.py"
PUBLISHER = ROOT / "automation/wp3_2a/create_or_update_pr.sh"


def test_wp3_2a_is_closed_on_main():
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    assert binding["status"] == "ACCEPTED_ON_MAIN"
    assert binding["as_of_date"] == "2026-07-24"
    assert binding["datasets"]["universe"]["rows"] == 5530
    assert binding["capability_summary"]["full_market_universe"] == 5530
    assert binding["accepted_merge_sha"] == "9305fd210c1729a7227e0e633eed5e29984bc261"
    assert acceptance["status"] == "ACCEPTED_ON_MAIN"
    assert acceptance["accepted_merge_sha"] == binding["accepted_merge_sha"]
    assert scope["status"] == "ACCEPTED_ON_MAIN"
    assert scope["scope_exceptions"][0]["security_code"] == "689009"
    assert acceptance["candidate_membership_mutations"] == 0
    assert acceptance["orders"] == 0
    assert acceptance["trade_authority"] == "NONE"


def test_execution_register_and_master_plan_preserve_wp3_2_closure_and_allow_forward_progression():
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    plan = MASTER_PLAN.read_text(encoding="utf-8")
    assert register["wp3_status"]["WP3-2A"] == "COMPLETED_ACCEPTED_CURRENT"
    assert register["trade_authority"] == "NONE"
    assert any(
        token in plan
        for token in (
            "WP3-2A | COMPLETED",
            "WP3-2A / 2B | COMPLETED",
            "| WP3 | COMPLETED",
            "WP3 | INITIAL CANDIDATE BASELINE COMPLETED",
        )
    )

    step = register["current_step"]
    if step == "WP3-2B_GOVERNED_SCREENING":
        assert register["wp3_status"]["WP3-2B"] == "READY_FOR_PROTECTED_PROPOSAL_ONLY_SCREENING"
        assert register["next_task"] == "RUN_WP3_2B_GOVERNED_SCREENING_PROPOSAL"
    elif step == "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD":
        assert register["wp3_status"]["WP3-2B"] == "COMPLETED_SCREENING_PROPOSAL_ACCEPTED_ON_MAIN"
        assert register["wp3_status"]["WP3-3"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-4"].startswith("COMPLETED_")
    elif step == "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert "WP4 | READY / NOT STARTED" in plan
    elif step == "WP5_PORTFOLIO_MIGRATION_AND_ACTION_REVIEW":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["status"] == "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
        assert register["wp4"]["ready_for_user_decision"] == 0
        assert "WP4 | COMPLETED IF PRESENT ON MAIN" in plan
        assert "0只Ready → NO ACTION" in plan
    elif step == "R2_WP2_WP4_PRODUCT_CAPABILITY_HARDENING":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["status"] == "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN"
        assert register["wp5"]["status"] == "BLOCKED_PENDING_R2_PRODUCT_CAPABILITY_HARDENING"
        assert "WP4 | CORE2 INITIAL PRODUCTION BASELINE ACCEPTED ON MAIN" in plan
        assert "WP5 | BLOCKED" in plan
    elif step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["status"] == "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN"
        assert register["wp4"]["r2_b_status"] == "CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY"
        assert register["wp5"]["status"] == "BLOCKED_PENDING_R2_MERGE"
        assert register["wp5"]["start_allowed"] is False
        assert register["next_task"] == "USER_MERGE_PR_145_TO_MAIN"
        assert register["r2"]["status"] == "R2_ACCEPTED_ON_BRANCH_PENDING_USER_MERGE"
    elif step == "WP5_PORTFOLIO_DECISION_PHASE_STARTED_ANALYSIS_ONLY_ON_BRANCH":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["r2_b_status"] == "CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY"
        assert register["wp5"]["status"] == "STARTED_ANALYSIS_ONLY_ON_BRANCH"
        assert register["wp5"]["start_allowed"] is True
        assert register["wp5"]["action_review_allowed"] is True
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        if register["wp5"].get("p0_internal_evidence_inventory_complete") is True:
            expected_next_task = "WP5_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_AND_FRESH_INPUT_REFRESH"
        elif register["wp5"].get("full_position_review_complete") is True:
            expected_next_task = "WP5_P0_REUNDERWRITE_AND_FRESH_INPUT_REFRESH"
        else:
            expected_next_task = "WP5_FRESH_INPUT_REFRESH_AND_FULL_POSITION_LEVEL_ACTION_REVIEW"
        assert register["next_task"] == expected_next_task
        assert register["r2"]["status"] == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
    elif step == "WP5_P0_EXTERNAL_PRIMARY_SOURCE_REUNDERWRITE_COMPLETE_RESEARCH_ONLY_ON_BRANCH":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["r2_b_status"] == "CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY"
        assert register["wp5"]["status"] == "P0_EXTERNAL_REUNDERWRITE_COMPLETE_RESEARCH_ONLY_ON_BRANCH"
        assert register["wp5"]["p0_external_primary_source_reunderwrite_complete"] is True
        assert register["wp5"]["p0_event_classification_complete"] is True
        assert register["wp5"]["fresh_completed_close_for_action"] is False
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["wp5"]["ready_for_user_decision_count"] == 0
        assert register["next_task"] == "WP5_NEXT_COMPLETED_CLOSE_REFRESH_AND_USER_POSITION_CONTINUITY_CONFIRMATION"
        assert register["r2"]["status"] == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
    elif step == "WP5_E_POST_CLOSE_ACTION_GATE_INSTALLED_ON_BRANCH":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp5"]["status"] == "POST_CLOSE_ACTION_GATE_INSTALLED_ON_BRANCH_PENDING_MERGE"
        assert register["wp5"]["p0_external_reunderwrite_accepted_on_main"] is True
        assert register["wp5"]["p0_merge_sha"] == "70f651ff042fbf815ad8e0346cabad02693745d9"
        assert register["wp5"]["post_close_action_gate_installed"] is True
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["next_task"] == "USER_MERGE_WP5_E_POST_CLOSE_ACTION_GATE_PR"
    elif step == "WP5_E_POST_CLOSE_ACTION_GATE_ACCEPTED_ON_MAIN":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp5"]["status"] == "POST_CLOSE_ACTION_GATE_ACCEPTED_ON_MAIN"
        assert register["wp5"]["post_close_action_gate_installed"] is True
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["next_task"] in {
            "WAIT_FOR_NEXT_COMPLETED_CLOSE_AFTER_2026_07_24",
            "CONTINUE_MONITORING_AND_NON_P0_RESEARCH_TRIAGE",
            "USER_REVIEW_CONDITIONAL_P0_POSITION_PROPOSALS",
        } or register["next_task"].startswith("USER_CONFIRM_POSITION_CONTINUITY_THROUGH_")
    elif step == "WP5_F_POSITION_CONTINUITY_INTERFACE_INSTALLED_ON_BRANCH":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp5"]["status"] == "POSITION_CONTINUITY_INTERFACE_INSTALLED_ON_BRANCH_PENDING_MERGE"
        assert register["wp5"]["post_close_action_gate_accepted_on_main"] is True
        assert register["wp5"]["post_close_action_gate_merge_sha"] == "c2abeb4c0c0a78db6007f2c5683bb84a70947b29"
        assert register["wp5"]["position_continuity_interface_installed"] is True
        assert register["wp5"]["position_continuity_request_status"] in {
            "WAITING_FOR_NEXT_COMPLETED_CLOSE",
            "USER_POSITION_CONTINUITY_CONFIRMATION_REQUIRED",
            "POSITION_CONTINUITY_CURRENT",
        }
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["next_task"] == "USER_MERGE_WP5_F_POSITION_CONTINUITY_INTERFACE_PR"
    elif step == "WP5_F_POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp5"]["status"] == "POSITION_CONTINUITY_INTERFACE_ACCEPTED_ON_MAIN"
        assert register["wp5"]["post_close_action_gate_accepted_on_main"] is True
        assert register["wp5"]["position_continuity_interface_installed"] is True
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["next_task"] in {
            "WAIT_FOR_NEXT_COMPLETED_CLOSE_AFTER_2026_07_24",
            "RUN_WP5_E_POST_CLOSE_ACTION_GATE_RECALCULATION",
        } or register["next_task"].startswith("USER_CONFIRM_ZERO_OR_REPORT_DELTAS_THROUGH_")
    elif step == "WP5_G_REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp5"]["status"] == "REAL_ACCOUNT_STRUCTURE_REVIEW_CURRENT_IF_PRESENT_ON_MAIN"
        assert register["wp5"]["source_pr"] == 151
        assert register["wp5"]["promotion_evidence"] == "GIT_HISTORY_ON_MAIN"
        assert register["wp5"]["canonical_promotion_semantics_v2"] is True
        assert register["wp5"]["position_continuity_interface_accepted_on_main"] is True
        assert register["wp5"]["real_account_lookthrough_complete"] is True
        assert register["wp5"]["real_account_structure_review_complete"] is True
        assert register["wp5"]["ready_for_user_decision_count"] == 0
        assert register["wp5"]["position_mutation_allowed"] is False
        assert register["wp5"]["order_execution_allowed"] is False
        assert register["next_task"] == "WP5_H_SIMULATION_NON_P0_RESEARCH_TRIAGE_AFTER_WP5_G_PRESENT_ON_MAIN"
    elif step == "R0_PRODUCT_AUTHORITY_FREEZE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["product_authority"]["source_pr"] == 152
        assert register["product_authority"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R0"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R1"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["status"] == "PARTIALLY_COMPLETE_NO_USER_ACTION_PACK"
        assert register["next_task"] == "R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN"
    elif step == "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R0"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R1"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R2"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["decision_grade_coverage"]["simulation_complete"] == 16
        assert register["wp5"]["decision_grade_coverage"]["real_product_complete"] == 7
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is False
        assert register["next_task"] == "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN"
    elif step == "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R1"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R2"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is False
        assert register["wp5"]["user_decision_pack_complete"] is False
        assert register["next_task"] == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    elif step == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R2"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN"
        assert register["development_roadmap"]["R4"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is True
        assert register["wp5"]["user_decision_pack_complete"] is True
        assert register["wp5"]["development_decision_scenario_count"] == 7
        assert register["wp5"]["ready_for_user_decision_count"] == 0
        assert register["wp5"]["implementation_ready_count"] == 0
        assert register["wp5"]["operating_activation"] is False
        assert register["next_task"] == "R4_OPERATING_PRODUCTS_DEVELOPMENT"
    else:
        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["wp4"]["r2_b_status"] == "CORE2_RESEARCH_HARDENING_ACCEPTED_RESEARCH_ONLY"
        assert register["wp5"]["status"] == "READY_PENDING_EXPLICIT_WP5_START"
        assert register["wp5"]["start_allowed"] is True
        assert register["next_task"] == "EXPLICITLY_START_WP5_PORTFOLIO_DECISION_PHASE"
        assert register["r2"]["status"] == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"


def test_scheduled_refresh_is_idempotent_and_fail_closed():
    text = UNIVERSE_WORKFLOW.read_text(encoding="utf-8")
    assert "refresh_decision.py" in text
    assert "Record successful no-op" in text
    assert "steps.decision.outputs.proceed == 'true'" in text
    assert "Fail closed when a required proposal was not produced" in text
    assert "Candidate / Research / account / simulation mutations: `0`" in text
    assert "trade_authority: `NONE`" in text


def test_bot_created_pr_dispatches_required_lineage_gate():
    text = PUBLISHER.read_text(encoding="utf-8")
    assert "gh workflow run wp3_2a_lineage_gate.yml" in text
    assert '--ref "$BRANCH"' in text
    assert "enforce_wp3_2a_scope=true" in text
    assert "--force" not in text
    assert "LINEAGE_DISPATCH_RECEIPT.json" in text


def test_future_current_promotion_is_self_closing_on_merge():
    text = ACCEPT_SCRIPT.read_text(encoding="utf-8")
    assert '"status": "ACCEPTED_ON_MAIN"' in text
    assert '"current_step": "WP3-2B_GOVERNED_SCREENING"' in text
    assert '"WP3-2B": "READY_FOR_PROTECTED_PROPOSAL_ONLY_SCREENING"' in text
    assert 'execution.pop("github_merge_sha", None)' in text
    assert '"promotion_evidence": "GIT_HISTORY"' in text
    assert '"candidate_membership_mutations": 0' in text
    assert '"trade_authority": "NONE"' in text


def test_wp3_2b_is_proposal_only_and_connector_dispatchable():
    workflow = SCREENING_WORKFLOW.read_text(encoding="utf-8")
    bridge = SCREENING_BRIDGE.read_text(encoding="utf-8")
    script = SCREENING_SCRIPT.read_text(encoding="utf-8")
    assert "name: WP3-2B Governed Screening Proposal" in workflow
    assert "environment: wp3-2a-screening-approval" in workflow
    assert "<<'EOF'" in workflow
    assert "Accepted universe session:" in workflow
    assert "Eligible Universe rows:" in workflow
    assert "SCREENING_EXCLUSIONS.csv" in script
    assert "WP3_2B_SCREENING_PROPOSAL" in script
    assert '"investment_ranking": False' in script
    assert '"candidate_membership_mutations": 0' in script
    assert '"trade_authority": "NONE"' in script
    assert "automation/wp3-2b-screen-" in bridge
    assert ".wp3_2a_control/screening_request.json" in bridge
    assert "types: [opened]" in bridge
    assert "\n  push:" not in bridge
    assert "synchronize" not in bridge
    assert "reopened" not in bridge
    assert "RUN_PROPOSAL_ONLY_SCREENING" in bridge
    assert "forked screening requests are not permitted" in bridge
    assert "Environment approval remains a human governance gate" in bridge
