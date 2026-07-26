#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def semantic_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--config",
        default="automation/wp3_5_6/post_merge_closure_config.json",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    merge_sha = config["accepted_merge_sha"]
    accepted_at = config["accepted_at"]

    candidate_path = root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    manifest_path = root / (
        "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_5_6/PROPOSALS/"
        "WP3_5_6_CANDIDATE_REBUILD_20260724_V1/WP3_5_6_MANIFEST.json"
    )
    register_path = root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    master_plan_path = root / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    outcome_path = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/CANDIDATE_OUTCOME_CONTRACT.json"
    registry_path = root / "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"
    acceptance_path = root / "investment_os_runtime/00_CONTROL/WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE_RECORD.json"

    candidate = read_json(candidate_path)
    assert candidate["state_id"] == config["candidate_state_id"]
    assert candidate["counts"]["candidate_core"] == config["candidate_core"]
    assert candidate["counts"]["shadow_track"] == config["shadow_track"]
    assert candidate["counts"]["research_queue"] == config["research_queue"]
    assert candidate["counts"]["ready_for_user_decision"] == config["ready_for_user_decision"]
    assert len(candidate["historical_core20_archive"]) == 20

    candidate.update(
        {
            "status": "ACCEPTED_ON_MAIN",
            "accepted_pr": config["accepted_pr"],
            "accepted_merge_sha": merge_sha,
            "accepted_at": accepted_at,
            "promotion_evidence": "GIT_HISTORY_AND_USER_MERGE",
            "candidate_state_change_authority": "USER_MERGE_OF_GOVERNED_PR",
            "current_operating_stage": "WP3_COMPLETED_WP4_READY_NOT_STARTED",
        }
    )
    candidate["state_boundaries"].update(
        {
            "candidate_state_transition": "GOVERNED_USER_MERGE_APPLIED",
            "automatic_candidate_mutation": False,
            "real_account_mutations": 0,
            "simulation_trade_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
    )
    candidate.pop("semantic_hash", None)
    candidate["semantic_hash"] = semantic_hash(candidate)
    write_json(candidate_path, candidate)

    manifest = read_json(manifest_path)
    assert manifest["proposal_id"] == "WP3_5_6_CANDIDATE_REBUILD_20260724_V1"
    assert manifest["metrics"]["candidate_core_proposed"] == config["candidate_core"]
    assert manifest["metrics"]["complete_entry_baselines"] == config["valid_entry_baselines"]
    manifest["status"] = "ACCEPTED_ON_MAIN"
    manifest["acceptance"] = {
        "status": "ACCEPTED_ON_MAIN",
        "accepted_pr": config["accepted_pr"],
        "accepted_merge_sha": merge_sha,
        "accepted_at": accepted_at,
        "candidate_state_effective": True,
        "candidate_core": config["candidate_core"],
        "shadow_track": config["shadow_track"],
        "research_queue": config["research_queue"],
        "ready_for_user_decision": config["ready_for_user_decision"],
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(manifest_path, manifest)

    register = read_json(register_path)
    register.update(
        {
            "register_id": "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V3_6_POST_MERGE_CLOSURE",
            "status_date": "2026-07-26",
            "release_id": config["release_id"],
            "release_sequence": config["release_sequence"],
            "github_merge_sha": merge_sha,
            "latest_governed_merge_sha": merge_sha,
            "overall_status": "WP3_COMPLETED_ACCEPTED_ON_MAIN_WP4_READY_NOT_STARTED",
            "current_step": "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION",
            "next_task": "RUN_WP4_DEEP_RESEARCH_AND_PORTFOLIO_DECISION_ON_ACCEPTED_CANDIDATE_STATE",
            "wp3_completed_at": accepted_at,
            "trade_authority": "NONE",
        }
    )
    register["state_preservation"].update(
        {
            "candidate_core": config["candidate_core"],
            "candidate_shadow_track": config["shadow_track"],
            "candidate_research_queue": config["research_queue"],
            "candidate_ready_for_user_decision": config["ready_for_user_decision"],
            "candidate_state_as_of": config["candidate_as_of"],
            "changed_state_files": 1,
            "real_holdings": config["real_holdings"],
            "simulation_holdings": config["simulation_holdings"],
        }
    )
    register["mutation_proof"].update(
        {
            "candidate_membership_mutations": "GOVERNED_USER_MERGE_APPLIED",
            "candidate_core_before": 20,
            "candidate_core_after": config["candidate_core"],
            "candidate_shadow_track_after": config["shadow_track"],
            "candidate_research_queue_after": config["research_queue"],
            "candidate_ready_for_user_decision_after": config["ready_for_user_decision"],
            "research_object_mutations": 0,
            "real_account_mutations": 0,
            "simulation_trade_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
    )
    register["wp3_3_4"].update(
        {
            "status": "COMPLETED_PROPOSAL_ACCEPTED_ON_MAIN",
            "accepted_merge_sha": config["wp3_3_4_merge_sha"],
        }
    )
    register["wp3_5_6"].update(
        {
            "status": "ACCEPTED_ON_MAIN",
            "accepted_pr": config["accepted_pr"],
            "accepted_merge_sha": merge_sha,
            "accepted_at": accepted_at,
            "candidate_state_effective": True,
            "candidate_core": config["candidate_core"],
            "shadow_track": config["shadow_track"],
            "research_queue": config["research_queue"],
            "ready_for_user_decision": config["ready_for_user_decision"],
            "valid_entry_baselines": config["valid_entry_baselines"],
            "next_gate": "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION",
            "trade_authority": "NONE",
        }
    )
    register["wp3_status"].update(
        {
            "WP3-3": "COMPLETED_MULTIDIMENSIONAL_LONGLIST_ACCEPTED_ON_MAIN",
            "WP3-4": "COMPLETED_HISTORICAL_CORE20_REVIEW_ACCEPTED_ON_MAIN",
            "WP3-5": "COMPLETED_RESEARCH_OBJECT_ENTRY_BASELINE_ACCEPTED_ON_MAIN",
            "WP3-6": "COMPLETED_CANDIDATE_REBUILD_ACCEPTED_ON_MAIN",
        }
    )
    write_json(register_path, register)

    master_plan = """# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：2026-07-26
- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`
- 最新受治理合并：`f0b3b31927def71873767a727680f5d4ae2339c5`
- File Library晋级：`PENDING_MANUAL_UPLOAD`
- 交易权限：`NONE`

## 当前阶段

| Work Package | 状态 | 当前结论 |
|---|---|---|
| WP1 | COMPLETED | Canonical、规则、Runtime与Clean-Room验收完成 |
| WP2 | COMPLETED | 账户、模拟盘、历史Candidate与市场诊断完成 |
| WP3-1 | COMPLETED | 策略、Candidate治理、Entry Baseline与Research Readiness标准完成 |
| WP3-2A / 2B | COMPLETED | 5530只Current与5525只研究Eligible Universe已接受 |
| WP3-3 + WP3-4 | COMPLETED / ACCEPTED ON MAIN | 53只Longlist、20只历史Core重审和73只统一研究计划已接受 |
| WP3-5 + WP3-6 | COMPLETED / ACCEPTED ON MAIN | 73只Research Object；2只Core、38只Shadow、33只Research Queue、0只Ready |
| WP4 | READY / NOT STARTED | 深研、组合适配、决策级估值与Decision Interface |
| WP5–WP7 | PLANNED | 组合迁移、周期运营、归因复盘和真实试点 |

## WP3正式关闭结论

- Candidate Core：美的集团、长江电力；
- 历史Core20不享受祖父条款，2只保留为Core，18只转入Shadow强制补研；
- 新Longlist没有被机械包装为Candidate；
- Ready for User Decision为0，没有生成BUY / ADD / REDUCE / SELL；
- 有效前瞻性Entry Baseline为2，但20 / 60 / 120日观察窗口尚未完成，Alpha归因继续Fail Closed；
- 真实账户、模拟盘和订单变更为0，`trade_authority=NONE`。

## 下一里程碑

`WP4 | Deep Research、Portfolio Fit、Decision-grade Valuation与Decision Interface`

WP4只能基于已接受的Core、Shadow与Research Queue推进。任何Ready-for-User-Decision、模拟盘或真实账户建议必须形成独立受治理Proposal；系统不自动交易。
"""
    master_plan_path.write_text(master_plan, encoding="utf-8")

    outcome = read_json(outcome_path)
    previous_status = outcome["current_status"]
    for key in (
        "pending_status_if_pr_merged",
        "pending_valid_entry_baseline_count_if_pr_merged",
        "current_status_remains_fail_closed_until_merge_and_observation",
    ):
        outcome.pop(key, None)
    outcome.update(
        {
            "current_status": "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS",
            "previous_status": previous_status,
            "valid_entry_baseline_count": config["valid_entry_baselines"],
            "entry_baseline_as_of": "2026-07-24",
            "completed_evaluation_windows": [],
            "required_evaluation_windows": [20, 60, 120],
            "candidate_state_id": config["candidate_state_id"],
            "accepted_candidate_merge_sha": merge_sha,
            "alpha_claim_allowed": False,
            "fail_closed_until_observation_windows_complete": True,
            "trade_authority": "NONE",
        }
    )
    write_json(outcome_path, outcome)

    registry = read_json(registry_path)
    registry.update(
        {
            "registry_id": "WP3_5_6_AUTHORITATIVE_ASSET_REGISTRY_V8",
            "status": "GITHUB_CURRENT_ACCEPTED_FILE_LIBRARY_DEPLOYMENT_PENDING",
            "date": "2026-07-26",
            "release_id": config["release_id"],
            "release_sequence": config["release_sequence"],
            "github_merge_sha": merge_sha,
        }
    )
    for asset in registry["assets"]:
        if asset["asset_id"] == "GITHUB_ACTIVE_RUNTIME":
            asset["status"] = "GITHUB_CURRENT_WP3_ACCEPTED"
            asset["latest_governed_merge_sha"] = merge_sha
    registry["assets"] = [
        asset
        for asset in registry["assets"]
        if asset.get("asset_id") != "WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE"
    ]
    registry["assets"].append(
        {
            "asset_id": "WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE",
            "location": "00_CONTROL/WP3_5_6_CANDIDATE_REBUILD_ACCEPTANCE_RECORD.json",
            "role": "POST_MERGE_CANDIDATE_STATE_ACCEPTANCE_AND_WP3_CLOSURE",
            "status": "ACCEPTED_ON_MAIN",
            "merge_sha": merge_sha,
        }
    )
    write_json(registry_path, registry)

    acceptance = {
        "acceptance_id": config["closure_id"],
        "status": "ACCEPTED_ON_MAIN",
        "accepted_pr": config["accepted_pr"],
        "accepted_merge_sha": merge_sha,
        "accepted_at": accepted_at,
        "candidate_state_id": config["candidate_state_id"],
        "candidate_as_of": config["candidate_as_of"],
        "before": {
            "historical_candidate_core": 20,
            "historical_core20_grandfathering": False,
        },
        "after": {
            "candidate_core": config["candidate_core"],
            "shadow_track": config["shadow_track"],
            "research_queue": config["research_queue"],
            "ready_for_user_decision": config["ready_for_user_decision"],
            "historical_core20_retained_as_core": 2,
            "historical_core20_moved_to_shadow": 18,
            "valid_entry_baselines": config["valid_entry_baselines"],
        },
        "candidate_core_codes": ["000333", "600900"],
        "candidate_core_names": ["美的集团", "长江电力"],
        "alpha_attribution": {
            "status": "BLOCKED_INSUFFICIENT_COMPLETED_EVALUATION_WINDOWS",
            "alpha_claim_allowed": False,
            "required_windows": [20, 60, 120],
            "completed_windows": [],
        },
        "state_boundaries": {
            "research_current_mutations": 0,
            "real_account_mutations": 0,
            "simulation_trade_mutations": 0,
            "orders": 0,
            "automatic_trade": False,
            "trade_authority": "NONE",
        },
        "file_library_promotion_status": "PENDING_MANUAL_UPLOAD",
        "next_gate": "WP4_DEEP_RESEARCH_PORTFOLIO_FIT_AND_DECISION_GRADE_VALUATION",
    }
    write_json(acceptance_path, acceptance)

    print(
        json.dumps(
            {
                "status": "PASS",
                "closure_id": config["closure_id"],
                "accepted_merge_sha": merge_sha,
                "candidate_core": config["candidate_core"],
                "shadow_track": config["shadow_track"],
                "research_queue": config["research_queue"],
                "ready_for_user_decision": config["ready_for_user_decision"],
                "wp4": "READY_NOT_STARTED",
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
