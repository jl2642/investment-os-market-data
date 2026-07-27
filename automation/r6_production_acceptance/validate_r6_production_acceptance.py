from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

R5_MERGE_SHA = "3cb173851eac4388f24785cd7a43cd557c58a3bc"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    prod = root / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"

    contract = read_json(control / "R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json")
    acceptance = read_json(control / "R6_PRODUCTION_ACCEPTANCE_RECORD_CURRENT.json")
    gate = read_json(control / "R6_OPERATING_ACTIVATION_GATE_CURRENT.json")
    observation = read_json(prod / "R6_OBSERVATION_LEDGER_CURRENT.json")
    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    r5_contract = read_json(control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json")
    r5_acceptance = read_json(control / "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json")

    assert contract["status"] == "STARTED_CURRENT_IF_PRESENT_ON_MAIN_OBSERVATION_NOT_COMPLETE"
    assert contract["acceptance_mode"] == "SUPERVISED_PRODUCTION_ACCEPTANCE"
    assert contract["observation_window"]["start"] == "2026-08-01"
    assert contract["observation_window"]["end"] == "2026-08-31"
    assert contract["domain_count"] == 8
    assert len(contract["domains"]) == 8
    assert contract["operating_activation"] is False
    assert contract["schedule_activation_count"] == 0
    assert contract["trade_authority"] == "NONE"

    assert r5_contract["status"] == "COMPLETED_ON_MAIN"
    assert r5_contract["merge_sha"] == R5_MERGE_SHA
    assert r5_acceptance["status"] == "COMPLETED_ON_MAIN"
    assert r5_acceptance["merge_sha"] == R5_MERGE_SHA

    assert observation["status"] == "OPEN_SUPERVISED_ACCEPTANCE"
    assert observation["checkpoint_total"] == 10
    assert observation["checkpoint_passed"] == 1
    assert len(observation["checkpoints"]) == 10
    assert observation["checkpoints"][0]["status"] == "PASS"
    assert all(row["status"] == "PENDING" for row in observation["checkpoints"][1:])
    assert observation["operating_activation"] is False
    assert observation["economic_mutations"] == {
        "real_account": 0,
        "simulation": 0,
        "candidate_membership": 0,
        "legacy_decisions": 0,
        "rules": 0,
        "orders": 0,
    }

    assert gate["status"] == "CLOSED_PENDING_FULL_MONTH_ACCEPTANCE"
    assert gate["can_activate_now"] is False
    assert gate["passed"] == ["R6-CP00"]
    assert len(gate["pending"]) == 9
    assert gate["operating_activation"] is False
    assert gate["trade_authority"] == "NONE"

    expected_hashes = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }
    assert acceptance["protected_state_hashes"] == expected_hashes
    assert acceptance["status"] == "STARTED_CURRENT_IF_PRESENT_ON_MAIN_NOT_FINAL_ACCEPTANCE"
    assert acceptance["preflight_passed"] is True
    assert acceptance["full_month_complete"] is False
    assert acceptance["checkpoint_passed"] == 1
    assert acceptance["checkpoint_total"] == 10
    assert acceptance["operating_activation"] is False
    assert acceptance["schedule_activation_count"] == 0
    assert acceptance["economic_mutations"] == {
        "real_account": 0,
        "simulation": 0,
        "candidate_membership": 0,
        "legacy_decisions": 0,
        "rules": 0,
        "orders": 0,
    }

    assert execution["current_step"] == "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["latest_completed_main_pr"] == 159
    assert execution["latest_completed_main_merge_sha"] == R5_MERGE_SHA
    assert execution["development_roadmap"]["R5"]["status"] == "COMPLETED_ON_MAIN"
    assert execution["development_roadmap"]["R6"]["status"] == "IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["production_acceptance_r6"]["full_month_complete"] is False
    assert execution["production_acceptance_r6"]["checkpoint_passed"] == 1
    assert execution["production_acceptance_r6"]["checkpoint_total"] == 10
    assert execution["next_task"] == "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08"
    assert execution["overall_status"] == "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_NOT_PRODUCTION_COMPLETE"
    assert execution["operating_activation"] is False
    assert execution["ready_for_user_decision_count"] == 0
    assert execution["implementation_ready_count"] == 0
    assert execution["trade_authority"] == "NONE"

    registered = {row["asset_id"]: row for row in registry["assets"]}
    for asset_id in (
        "R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT",
        "R6_PRODUCTION_ACCEPTANCE_START_RECORD",
        "R6_OPERATING_ACTIVATION_GATE_CURRENT",
        "R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT",
        "R6_STATUS_CURRENT",
        "R6_OBSERVATION_LEDGER_CURRENT",
        "R6_PRODUCTION_RUNBOOK_CURRENT",
    ):
        assert registered[asset_id]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert registered[asset_id]["trade_authority"] == "NONE"

    matrix = (control / "R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT.md").read_text(encoding="utf-8")
    runbook = (prod / "R6_PRODUCTION_RUNBOOK_CURRENT.md").read_text(encoding="utf-8")
    status = (control / "R6_STATUS_CURRENT.md").read_text(encoding="utf-8")
    master = (control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md").read_text(encoding="utf-8")
    capability = (control / "CAPABILITY_REALITY_MATRIX_CURRENT.md").read_text(encoding="utf-8")
    guide = (control / "USER_OPERATING_GUIDE_CURRENT.md").read_text(encoding="utf-8")

    assert "R6通过后系统自主完成" in matrix
    assert "用户必须完成" in matrix
    assert "用户不再需要做" in matrix
    assert "不需要每天重新上传全部持仓或来源三包" in matrix
    assert "完整自然月" in runbook
    assert "不能在同一天宣称完成" in runbook
    assert "Checkpoint：`1/10`" in status
    assert "Operating Activation：`false`" in status
    assert "R6启动与生产验收状态" in master
    assert "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08" in master
    assert "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN" in capability
    assert "R6之后的正式使用方式" in guide

    test_text = (root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py").read_text(encoding="utf-8")
    assert 'elif step == "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN":' in test_text

    print({
        "r5_main_reconciled": True,
        "r6_preflight": "PASS",
        "r6_checkpoints": "1/10",
        "full_month_complete": False,
        "operating_activation": False,
        "protected_state": "UNCHANGED",
        "orders": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
