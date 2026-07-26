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
    assert "WP3-2A | COMPLETED" in plan

    if register["current_step"] == "WP3-2B_GOVERNED_SCREENING":
        assert register["wp3_status"]["WP3-2B"] == "READY_FOR_PROTECTED_PROPOSAL_ONLY_SCREENING"
        assert register["next_task"] == "RUN_WP3_2B_GOVERNED_SCREENING_PROPOSAL"
        assert "WP3-2B | ACTIVE / READY" in plan
        assert "同一交易日或已有未关闭Proposal" in plan
    elif register["current_step"] == "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD":
        assert register["wp3_status"]["WP3-2B"] == "COMPLETED_SCREENING_PROPOSAL_ACCEPTED_ON_MAIN"
        assert register["wp3_status"]["WP3-3"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-4"].startswith("COMPLETED_")
        assert register["next_task"] == "RUN_WP3_5_WP3_6_CONCENTRATED_CANDIDATE_REBUILD_PROPOSAL"
        assert "WP3-2B | COMPLETED" in plan
        assert "WP3-3 + WP3-4 | COMPLETED" in plan
        assert "WP3-5 + WP3-6 | READY" in plan
    else:
        assert register["current_step"] == "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION"
        assert register["wp3_status"]["WP3-2B"] == "COMPLETED_SCREENING_PROPOSAL_ACCEPTED_ON_MAIN"
        assert register["wp3_status"]["WP3-3"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-4"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-5"].startswith("COMPLETED_")
        assert register["wp3_status"]["WP3-6"].startswith("COMPLETED_")
        assert register["next_task"] == "RUN_WP4_DEEP_RESEARCH_AND_PORTFOLIO_DECISION_ON_ACCEPTED_CANDIDATE_STATE"
        assert "WP3-5 + WP3-6 | ACCEPTED IF THIS PR MERGES" in plan
        assert "WP4 | READY AFTER MERGE" in plan


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
    assert "ELIGIBLE_UNIVERSE.csv" in script
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
