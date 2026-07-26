#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def semantic_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def rehash(payload: dict[str, Any]) -> dict[str, Any]:
    payload.pop("semantic_hash", None)
    payload["semantic_hash"] = semantic_hash(payload)
    return payload


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    assets = registry.setdefault("assets", [])
    for index, existing in enumerate(assets):
        if existing.get("asset_id") == asset["asset_id"]:
            assets[index] = asset
            return
    assets.append(asset)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_wp4_closure/config.json")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    control = root / "investment_os_runtime/00_CONTROL"

    register_path = control / "EXECUTION_REGISTER_CURRENT.json"
    plan_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    wp4_acceptance_path = control / "WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_RECORD.json"
    candidate_path = root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    research_path = root / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json"
    decision_path = root / "investment_os_runtime/30_STATE_CURRENT/50_DECISION_INTERFACE/WP4_DECISION_INTERFACE_CURRENT.json"

    register = read_json(register_path)
    registry = read_json(registry_path)
    wp4_acceptance = read_json(wp4_acceptance_path)
    candidate = read_json(candidate_path)
    research = read_json(research_path)
    decision = read_json(decision_path)

    assert candidate["status"] == "ACCEPTED_ON_MAIN"
    assert candidate["counts"] == {
        "candidate_core": 2,
        "historical_core20": 20,
        "historical_core20_moved_to_shadow": 18,
        "historical_core20_retained_as_core": 2,
        "ready_for_user_decision": 0,
        "research_queue": 33,
        "shadow_track": 38,
    }
    assert {row["security_id"] for row in candidate["candidate_core_members"]} == {
        "000333.SZ",
        "600900.SH",
    }
    assert research["record_count"] == 2
    assert decision["record_count"] == 2
    assert decision["ready_for_user_decision_count"] == 0
    assert wp4_acceptance["acceptance_id"] == "WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_20260726_V1"

    merge_sha = config["accepted_wp4_merge_sha"]
    closure_status = "R1_CANONICAL_AUDIT_CLOSED_R2_HARDENING_REQUIRED_WP5_BLOCKED"

    register.update(
        {
            "register_id": "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V5_R1_AUDIT_CLOSURE",
            "status_date": config["status_date"],
            "github_merge_sha": merge_sha,
            "latest_governed_merge_sha": merge_sha,
            "release_id": config["release_id"],
            "release_sequence": config["release_sequence"],
            "overall_status": closure_status,
            "current_step": config["current_step"],
            "next_task": config["next_task"],
            "file_library_promotion_status": config["file_library_status"],
            "trade_authority": "NONE",
        }
    )
    register["wp4"].update(
        {
            "status": "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN",
            "accepted_pr": config["accepted_wp4_pr"],
            "accepted_merge_sha": merge_sha,
            "accepted_head_sha": config["accepted_wp4_head_sha"],
            "completion_claim": "INITIAL_DECISION_BASELINE_ONLY",
            "full_professional_deep_research_complete": False,
            "position_level_portfolio_fit_complete": False,
            "continuous_refresh_complete": False,
            "next_gate": config["next_task"],
        }
    )
    register["wp2_wp4_audit_closure"] = {
        "closure_id": config["closure_id"],
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "accepted_wp4_pr": config["accepted_wp4_pr"],
        "accepted_wp4_merge_sha": merge_sha,
        "audit_findings": config["audit_findings"],
        "r2_required_capabilities": config["r2_required_capabilities"],
        "wp5_gate": config["wp5_gate"],
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    register["wp5"] = {
        "status": config["wp5_gate"],
        "reason": "PORTFOLIO_CURRENT_CANDIDATE_REFRESH_AND_WP4B_RESEARCH_HARDENING_ARE_NOT_YET_PRODUCT_GRADE",
        "ready_for_user_decision_count": 0,
        "action_review_allowed": False,
        "forced_action_prohibited": True,
        "next_gate": config["next_task"],
        "trade_authority": "NONE",
    }
    write_json(register_path, register)

    candidate.update(
        {
            "current_operating_stage": "WP4_CORE2_INITIAL_BASELINE_ACCEPTED_R2_HARDENING_REQUIRED_WP5_BLOCKED",
            "latest_governed_merge_sha": merge_sha,
            "wp4_baseline_status": "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN",
            "wp5_gate": config["wp5_gate"],
            "continuous_candidate_engine_complete": False,
            "candidate_outcome_windows_complete": False,
        }
    )
    write_json(candidate_path, rehash(candidate))

    wp4_acceptance.update(
        {
            "status": "ACCEPTED_ON_MAIN",
            "accepted_pr": config["accepted_wp4_pr"],
            "accepted_merge_sha": merge_sha,
            "accepted_head_sha": config["accepted_wp4_head_sha"],
            "completion_claim": "CORE2_INITIAL_PRODUCTION_BASELINE",
            "maturity": "INITIAL_DECISION_BASELINE_NOT_FULL_DEEP_RESEARCH_FACTORY",
            "full_professional_deep_research_complete": False,
            "position_level_portfolio_fit_complete": False,
            "continuous_refresh_complete": False,
            "next_gate": config["next_task"],
        }
    )
    write_json(wp4_acceptance_path, wp4_acceptance)

    research.update(
        {
            "status": "ACCEPTED_ON_MAIN_INITIAL_BASELINE",
            "accepted_merge_sha": merge_sha,
            "maturity": "CORE2_INITIAL_RESEARCH_BASELINE",
            "full_professional_deep_research_complete": False,
            "continuous_filing_event_refresh_complete": False,
            "next_hardening_gate": "WP4B_CORE2_DEEP_RESEARCH_DRIVER_MODEL_AND_POSITION_LEVEL_PORTFOLIO_FIT",
        }
    )
    write_json(research_path, rehash(research))

    decision.update(
        {
            "status": "ACCEPTED_ON_MAIN_INITIAL_BASELINE",
            "accepted_merge_sha": merge_sha,
            "maturity": "CORE2_INITIAL_DECISION_INTERFACE",
            "position_sizing_grade": False,
            "continuous_refresh_complete": False,
            "wp5_action_review_allowed": False,
            "next_hardening_gate": "WP4B_CORE2_DEEP_RESEARCH_DRIVER_MODEL_AND_POSITION_LEVEL_PORTFOLIO_FIT",
        }
    )
    write_json(decision_path, rehash(decision))

    registry.update(
        {
            "registry_id": "WP2_WP4_AUTHORITATIVE_ASSET_REGISTRY_V9",
            "date": config["status_date"],
            "github_merge_sha": merge_sha,
            "latest_governed_merge_sha": merge_sha,
            "release_id": config["release_id"],
            "release_sequence": config["release_sequence"],
            "status": "GITHUB_CURRENT_WP4_INITIAL_BASELINE_ACCEPTED_R2_REQUIRED_FILE_LIBRARY_PENDING",
            "trade_authority": "NONE",
        }
    )
    upsert_asset(
        registry,
        {
            "asset_id": "GITHUB_ACTIVE_RUNTIME",
            "latest_governed_merge_sha": merge_sha,
            "location": "investment_os_runtime/",
            "role": "RULE_STATE_RESEARCH_DECISION_OPERATIONS_AND_CONTROL_RUNTIME",
            "status": "GITHUB_CURRENT_WP4_INITIAL_BASELINE_ACCEPTED_R2_REQUIRED",
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP4_CORE2_INITIAL_RESEARCH_CURRENT",
            "location": "30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json",
            "merge_sha": merge_sha,
            "role": "CORE2_INITIAL_RESEARCH_BASELINE_NOT_FULL_DEEP_RESEARCH_FACTORY",
            "status": "ACCEPTED_ON_MAIN_INITIAL_BASELINE",
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP4_DECISION_INTERFACE_CURRENT",
            "location": "30_STATE_CURRENT/50_DECISION_INTERFACE/WP4_DECISION_INTERFACE_CURRENT.json",
            "merge_sha": merge_sha,
            "role": "CORE2_INITIAL_DECISION_INTERFACE_ZERO_READY_ZERO_ACTION",
            "status": "ACCEPTED_ON_MAIN_INITIAL_BASELINE",
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP4_CORE2_ACCEPTANCE",
            "location": "00_CONTROL/WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_RECORD.json",
            "merge_sha": merge_sha,
            "role": "WP4_CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTANCE",
            "status": "ACCEPTED_ON_MAIN",
        },
    )
    upsert_asset(
        registry,
        {
            "asset_id": "WP2_WP4_CANONICAL_AUDIT_CLOSURE",
            "location": "00_CONTROL/WP2_WP4_CANONICAL_AUDIT_CLOSURE_RECORD.json",
            "role": "POST_WP4_MATURITY_RECLASSIFICATION_GAP_REGISTER_AND_WP5_GATE",
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
        },
    )
    write_json(registry_path, registry)

    closure_record = {
        "closure_id": config["closure_id"],
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "status_date": config["status_date"],
        "accepted_wp4_pr": config["accepted_wp4_pr"],
        "accepted_wp4_merge_sha": merge_sha,
        "accepted_wp4_head_sha": config["accepted_wp4_head_sha"],
        "audit_scope": ["WP2", "WP3", "WP4"],
        "audit_findings": config["audit_findings"],
        "formal_conclusions": {
            "WP2": "BASELINE_COMPLETED_RECURRING_PORTFOLIO_CURRENT_PENDING",
            "WP3": "INITIAL_CANDIDATE_BASELINE_COMPLETED_CONTINUOUS_ENGINE_PENDING",
            "WP4": "CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_FULL_DEEP_RESEARCH_PENDING",
            "WP5": config["wp5_gate"],
        },
        "r2_required_capabilities": config["r2_required_capabilities"],
        "file_library_status": config["file_library_status"],
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    write_json(control / "WP2_WP4_CANONICAL_AUDIT_CLOSURE_RECORD.json", closure_record)

    gap_rows = []
    priority = 0
    for work_package in ("WP2", "WP3", "WP4"):
        finding = config["audit_findings"][work_package]
        for limitation in finding["limitations"]:
            priority += 1
            gap_rows.append(
                {
                    "gap_id": f"R1-GAP-{priority:02d}",
                    "work_package": work_package,
                    "limitation": limitation,
                    "maturity": finding["maturity"],
                    "blocks_wp5": True,
                    "resolution_route": config["next_task"],
                    "automatic_state_mutation": False,
                    "trade_authority": "NONE",
                }
            )
    gap_register = {
        "register_id": "WP2_WP4_CAPABILITY_GAP_REGISTER_20260726_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "status_date": config["status_date"],
        "gap_count": len(gap_rows),
        "gaps": gap_rows,
        "wp5_gate": config["wp5_gate"],
        "next_task": config["next_task"],
        "trade_authority": "NONE",
    }
    write_json(control / "WP2_WP4_CAPABILITY_GAP_REGISTER_CURRENT.json", gap_register)

    master_plan = f"""# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：{config['status_date']}
- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`
- 最新受治理合并：PR #{config['accepted_wp4_pr']} / `{merge_sha}`
- File Library晋级：`{config['file_library_status']}`
- 交易权限：`NONE`

## 当前阶段

| Work Package | 正式状态 | 成熟度结论 |
|---|---|---|
| WP1 | COMPLETED | Canonical、规则、Runtime与Clean-Room验收完成 |
| WP2 | BASELINE COMPLETED | 首次账户/模拟盘Current和诊断完成；Recurring Portfolio Current未完成 |
| WP3 | INITIAL CANDIDATE BASELINE COMPLETED | 2只Core、38只Shadow、33只Research Queue；持续财务/Candidate刷新及效果验证未完成 |
| WP4 | CORE2 INITIAL PRODUCTION BASELINE ACCEPTED ON MAIN | 两只Core的初始研究、方向性Portfolio Fit、显式情景估值和Decision Interface完成；完整Deep Research未完成 |
| R2 | READY / REQUIRED | Portfolio Current、Continuous Candidate Refresh、Core2 Research Hardening |
| WP5 | BLOCKED | 等待R2完成；不得以0只Ready为由降低门槛或强制生成交易建议 |
| WP6–WP7 | PLANNED | 正式周期运营、归因复盘和完整自然月实跑验收 |

## R1审计结论

### WP2

WP2完成的是截至2026-07-24的一次正式状态重建和首次运营诊断。真实账户仍无券商连接，`broker_verified=false`，用户发生交易后必须提供增量确认。旧组合行情刷新流程不是每日滚动的正式Portfolio Current。

### WP3

WP3完成了首轮全市场筛选、历史Core20重审和Candidate重建。只有全市场行情获取具备Schedule；财务期间刷新、金融行业独立Profile、下游Candidate周期重跑和20/60/120日效果验证尚未完成。

### WP4

PR #{config['accepted_wp4_pr']}已经合并并形成真实资产，但正确成熟度是`Core2 Initial Production Baseline`。现有5项正式来源、2份研究记录和2份情景估值支持“等待证据或更好价格”，不等同于完整专业Deep Research、驱动式财务模型或仓位级Portfolio Fit。

## 下一里程碑

`R2 | WP2-R Portfolio Current + WP3-R Continuous Candidate Refresh + WP4-B Core2 Research Hardening`

R2完成前不进入WP5。任何Candidate、模拟盘或真实账户状态变化仍须独立受治理Proposal；系统不自动交易。
"""
    plan_path.write_text(master_plan, encoding="utf-8")

    evidence_dir = root / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP2_WP4_AUDIT_CLOSURE"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    review = f"""# R1｜WP2–WP4 Canonical Audit Closure

## 审计结论

- WP2：首次Current与运营诊断完成；Recurring Portfolio Current未完成。
- WP3：首轮Candidate Baseline完成；Continuous Candidate Engine未完成。
- WP4：PR #{config['accepted_wp4_pr']}已合并，Core2 Initial Production Baseline有效；完整Deep Research Factory未完成。
- WP5：`{config['wp5_gate']}`。

## Canonical修正

- 最新受治理合并指向`{merge_sha}`；
- WP4由条件性状态归一为`CORE2_INITIAL_PRODUCTION_BASELINE_ACCEPTED_ON_MAIN`；
- Candidate、Research Current、Decision Interface、Acceptance Record与Asset Registry统一更新；
- 建立正式Capability Gap Register；
- File Library继续标记`{config['file_library_status']}`，未虚构自动晋级。

## 安全边界

- Candidate membership mutations：0
- Real-account mutations：0
- Simulation-trade mutations：0
- Orders：0
- trade_authority：NONE
"""
    (evidence_dir / "WP2_WP4_CANONICAL_AUDIT_CLOSURE_REVIEW.md").write_text(review, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "closure_id": config["closure_id"],
                "latest_governed_merge_sha": merge_sha,
                "wp5_gate": config["wp5_gate"],
                "gap_count": len(gap_rows),
                "candidate_membership_mutations": 0,
                "real_account_mutations": 0,
                "simulation_trade_mutations": 0,
                "orders": 0,
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
