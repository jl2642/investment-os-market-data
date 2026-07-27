from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

R4_MERGE_SHA = "f4c48b1aa07f05f41f3d79cf5f843d84b384a5ec"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a: float, b: float, tolerance: float = 0.02) -> bool:
    return math.isclose(float(a), float(b), abs_tol=tolerance)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    attribution = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION"
    samples = root / "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"

    real = read_json(real_path)
    simulation = read_json(sim_path)
    candidate = read_json(candidate_path)
    contract = read_json(control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json")
    acceptance = read_json(control / "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json")
    ledger = read_json(attribution / "R5_RETURN_LEDGER_CURRENT.json")
    portfolio = read_json(attribution / "R5_PORTFOLIO_ATTRIBUTION_CURRENT.json")
    candidate_attr = read_json(attribution / "R5_CANDIDATE_ATTRIBUTION_CURRENT.json")
    calibration = read_json(attribution / "R5_RULE_CALIBRATION_PROPOSALS_CURRENT.json")
    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    r4_contract = read_json(control / "R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json")
    r4_acceptance = read_json(control / "R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json")

    assert contract["status"] == "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    assert contract["promotion_evidence"] == "MERGED_PR_AND_FILE_PRESENCE"
    assert len(contract["layers"]) == 7
    assert {row["layer_id"] for row in contract["layers"]} == {
        "SECURITY_SELECTION",
        "INDUSTRY_AND_SLEEVE",
        "POSITION_SIZING",
        "TIMING",
        "CASH",
        "CANDIDATE",
        "RULE",
    }
    assert contract["operating_activation"] is False
    assert contract["trade_authority"] == "NONE"
    assert contract["next_authorized_stage"] == "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN"

    real_summary = real["summary"]
    sim_summary = simulation["summary"]
    assert close(ledger["real_account"]["identity_check_market_plus_cash"], real_summary["account_total_assets"])
    assert close(ledger["simulation"]["identity_check_market_plus_cash"], sim_summary["account_total_assets"])
    assert close(sum(float(row["unrealized_pnl"]) for row in real["holdings"]), real_summary["open_unrealized_pnl"])
    assert close(sum(float(row["unrealized_pnl"]) for row in simulation["holdings"]), sim_summary["open_unrealized_pnl"])
    assert close(ledger["simulation"]["pnl_bridge_check"], sim_summary["account_total_pnl"])
    assert close(
        ledger["simulation"]["open_unrealized_pnl_rmb"] + ledger["simulation"]["closed_fee_other_residual_rmb"],
        ledger["simulation"]["account_total_pnl_rmb"],
    )
    assert ledger["real_account"]["total_return_status"] == "BLOCKED_NOT_A_VERIFIED_PERIOD_TOTAL_RETURN"
    assert ledger["simulation"]["period_return_status"] == "ACCOUNT_SINCE_INCEPTION_PNL_AVAILABLE_PERIOD_ATTRIBUTION_BLOCKED"

    assert len(portfolio["real_account"]["security_contribution"]) == 7
    assert len(portfolio["simulation"]["security_contribution"]) == 16
    assert len(portfolio["real_account"]["sleeve_contribution"]) == 6
    assert len(portfolio["simulation"]["sleeve_contribution"]) == 6
    assert close(sum(row["unrealized_pnl_rmb"] for row in portfolio["real_account"]["sleeve_contribution"]), real_summary["open_unrealized_pnl"])
    assert close(sum(row["unrealized_pnl_rmb"] for row in portfolio["simulation"]["sleeve_contribution"]), sim_summary["open_unrealized_pnl"])
    assert portfolio["timing"]["status"] == "BLOCKED_NO_COMPLETE_TRANSACTION_AND_PERIOD_BASELINE"
    assert portfolio["cash"]["real_cash_role"] == "EXECUTION_BALANCE_ONLY"

    assert candidate_attr["status"] == "BLOCKED_WINDOWS_NOT_MATURE"
    assert candidate_attr["valid_entry_baseline_count"] == 2
    assert candidate_attr["completed_windows_present"] == []
    assert candidate_attr["alpha_claim_allowed"] is False
    assert candidate_attr["candidate_membership_mutations"] == 0
    assert candidate_attr["counts"]["candidate_core"] == 2
    assert candidate_attr["counts"]["shadow_track"] == 38
    assert candidate_attr["counts"]["research_queue"] == 33
    assert candidate_attr["counts"]["ready_for_user_decision"] == 0
    assert candidate["candidate_outcome_windows_complete"] is False

    assert calibration["status"] == "PROPOSALS_ONLY_NOT_APPLIED"
    assert calibration["proposal_count"] == 8
    assert len(calibration["proposals"]) == 8
    assert all(row["status"] == "PROPOSED_NOT_APPLIED" for row in calibration["proposals"])
    assert calibration["applied_rule_mutations"] == 0
    assert calibration["automatic_candidate_mutations"] == 0
    assert calibration["automatic_portfolio_mutations"] == 0
    assert calibration["orders"] == 0

    expected_hashes = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }
    assert acceptance["protected_state_hashes"] == expected_hashes
    assert acceptance["economic_mutations"] == {
        "real_account": 0,
        "simulation": 0,
        "candidate_membership": 0,
        "legacy_decisions": 0,
        "rules": 0,
        "orders": 0,
    }
    assert acceptance["layer_count"] == 7
    assert acceptance["return_ledger_reconciled"] is True
    assert acceptance["simulation_pnl_bridge_reconciled"] is True
    assert acceptance["candidate_windows_complete"] is False
    assert acceptance["rule_calibration_proposal_count"] == 8
    assert acceptance["operating_activation"] is False
    assert acceptance["next_authorized_stage"] == "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN"

    assert execution["current_step"] == "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["latest_completed_main_pr"] == 158
    assert execution["latest_completed_main_merge_sha"] == R4_MERGE_SHA
    assert execution["development_roadmap"]["R4"]["status"] == "COMPLETED_ON_MAIN"
    assert execution["development_roadmap"]["R5"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["development_roadmap"]["R6"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
    assert execution["next_task"] == "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN"
    assert execution["operating_activation"] is False
    assert execution["ready_for_user_decision_count"] == 0
    assert execution["implementation_ready_count"] == 0
    assert execution["trade_authority"] == "NONE"

    assert r4_contract["final_governed_head_sha"] == "422bde92746062316a9b22da194f67f1e5b7783e"
    assert r4_contract["merge_sha"] == R4_MERGE_SHA
    assert r4_acceptance["final_governed_head_sha"] == "422bde92746062316a9b22da194f67f1e5b7783e"
    assert r4_acceptance["merge_sha"] == R4_MERGE_SHA

    registered = {row["asset_id"]: row for row in registry["assets"]}
    for asset_id in (
        "R5_ATTRIBUTION_CONTRACT_CURRENT",
        "R5_RETURN_LEDGER_CURRENT",
        "R5_PORTFOLIO_ATTRIBUTION_CURRENT",
        "R5_CANDIDATE_ATTRIBUTION_CURRENT",
        "R5_RULE_CALIBRATION_PROPOSALS_CURRENT",
        "R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT",
        "R5_ACCEPTANCE_RECORD",
        "R5_STATUS_CURRENT",
    ):
        assert registered[asset_id]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert registered[asset_id]["trade_authority"] == "NONE"

    report = (attribution / "R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT.md").read_text(encoding="utf-8")
    status = (control / "R5_STATUS_CURRENT.md").read_text(encoding="utf-8")
    master = (control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md").read_text(encoding="utf-8")
    capability = (control / "CAPABILITY_REALITY_MATRIX_CURRENT.md").read_text(encoding="utf-8")
    guide = (control / "USER_OPERATING_GUIDE_CURRENT.md").read_text(encoding="utf-8")
    assert "模拟盘在当前水位并非亏损" in report
    assert "BLOCKED_WINDOWS_NOT_MATURE" in report
    assert "Rule Calibration Proposals：`8`" in status
    assert "## R5开发验收结果" in master
    assert "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN" in master
    assert "DEVELOPMENT_PRODUCT_COMPLETE_PRODUCTION_WINDOWS_PENDING" in capability
    assert "当前阶段：`R5完成，R6待开始`" in guide
    assert (samples / "R5_MONTHLY_ATTRIBUTION_INTEGRATION_SAMPLE.md").exists()
    assert (samples / "R5_ANNUAL_CALIBRATION_INTEGRATION_SAMPLE.md").exists()

    r1_workflow = (root / ".github/workflows/r1_decision_coverage.yml").read_text(encoding="utf-8")
    r3_workflow = (root / ".github/workflows/r3_position_action_matrix.yml").read_text(encoding="utf-8")
    r4_workflow = (root / ".github/workflows/r4_operating_products.yml").read_text(encoding="utf-8")
    assert "startsWith(github.head_ref, 'agent/r1-')" in r1_workflow
    assert "startsWith(github.head_ref, 'agent/r3-')" in r3_workflow
    assert "startsWith(github.head_ref, 'agent/r4-')" in r4_workflow

    print({
        "r5_layers": 7,
        "real_positions": 7,
        "simulation_positions": 16,
        "simulation_pnl_bridge": "PASS",
        "candidate_windows": 0,
        "rule_proposals": 8,
        "economic_mutations": 0,
        "orders": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
