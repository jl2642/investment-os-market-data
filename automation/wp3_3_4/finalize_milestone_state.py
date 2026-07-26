#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def build_master_plan(manifest: dict[str, Any]) -> str:
    metrics = manifest["metrics"]
    return f"""# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：2026-07-26
- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`
- 市场数据Current：`investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json`
- WP3-3/4 Proposal：`investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_3_4/PROPOSALS/WP3_3_4_PROPOSAL_20260724_V4/`
- 交易权限：`NONE`

## 当前阶段

| Work Package | 状态 | 当前结论 |
|---|---|---|
| WP1 | COMPLETED | Canonical、规则、Runtime与独立Clean-Room验收完成 |
| WP2 | COMPLETED | 真实账户、模拟盘、历史Candidate与市场状态诊断完成；无交易变更 |
| WP3-1 | COMPLETED | 稳健成长策略、Candidate准入、生命周期、Entry Baseline与Research Readiness Gate完成 |
| WP3-2A | COMPLETED | 2026-07-24普通A股5530只Current已接受；定时刷新、Lineage Gate、Proposal与受保护Acceptance上线 |
| WP3-2B | COMPLETED | 5525只数据与流动性Eligible Universe、5只排除和100只初始研究工作队列已接受 |
| WP3-3 + WP3-4 | COMPLETED ON MERGE | 5525只多维评估、{metrics['multidimensional_eligible_rows']}只多维Eligible、{metrics['industry_longlist_rows']}只行业Longlist、20只历史Core重审及{metrics['unified_research_workplan_rows']}只统一研究计划 |
| WP3-5 + WP3-6 | READY ON MERGE | Research Object、Entry Baseline、Candidate Core / Shadow / Ready-to-Buy重建Proposal |
| WP4–WP7 | PLANNED | 深研、组合决策、周期运营、归因复盘与真实试点 |

## WP3-3 + WP3-4结果边界

- A Deep Dive：{metrics['deep_dive_rows']}
- B Structured Research：{metrics['structured_research_rows']}
- C Watch / Evidence Fill：{metrics['watch_rows']}
- Longlist行业桶：{metrics['industry_bucket_count']}
- Longlist策略袖套：{metrics['strategy_sleeve_count']}
- 历史Core20重审：{metrics['historical_core20_review_rows']}
- 新Longlist与历史Core20重合：{metrics['core20_longlist_overlap']}
- 独立金融Profile：{metrics['separate_profile_review_rows']}
- 既有研究拒绝、等待新证据：{metrics['prior_rejection_deferred_rows']}

本轮是研究优先级，不是证券投资吸引力排名。估值只进行2026-07-24价格联动重估，不宣称底层财务期已刷新。历史Core20不享受祖父条款，但所有20只均进入强制重审工作计划；没有自动留存、自动删除或自动重新准入。

## 下一里程碑

```text
WP3-5 + WP3-6
统一研究工作计划
→ Research Object与证据缺口
→ Entry Baseline
→ Candidate Core / Shadow / Ready-to-Buy建议
→ 新旧Candidate迁移对照
→ 单一受治理Candidate重建Proposal
```

该里程碑内部开发和测试由ChatGPT与GitHub执行。只有最终Candidate成员或状态变更Proposal需要用户批准与合并。

## 永久权限边界

- Candidate membership mutations：0（截至本Current）
- Research Object mutations：0（截至本Current）
- real-account mutations：0
- simulation-trade mutations：0
- orders：0
- `trade_authority=NONE`
"""


def finalize(repo_root: Path, proposal_dir: Path) -> None:
    manifest = read_json(proposal_dir / "WP3_3_4_MANIFEST.json")
    register_path = repo_root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    master_path = repo_root / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    register = read_json(register_path)
    metrics = manifest["metrics"]

    register["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V3_4_PROPOSAL_ACCEPTED_ON_MERGE"
    register["status_date"] = "2026-07-26"
    register["overall_status"] = "WP3_IN_PROGRESS_WP3_2B_COMPLETED_WP3_3_4_ACCEPTED_ON_MERGE"
    register["current_step"] = "WP3-5_WP3-6_RESEARCH_OBJECT_ENTRY_BASELINE_AND_CANDIDATE_REBUILD"
    register["release_id"] = "INVESTMENT_OS_R12_20260726_WP3_3_4"
    register["release_sequence"] = 12
    register["next_task"] = "RUN_WP3_5_WP3_6_CONCENTRATED_CANDIDATE_REBUILD_PROPOSAL"
    register["trade_authority"] = "NONE"
    register["mutation_proof"].update(
        {
            "candidate_membership_mutations": 0,
            "research_object_mutations": 0,
            "real_account_mutations": 0,
            "simulation_trade_mutations": 0,
            "automatic_rule_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        }
    )
    register["wp3_status"].update(
        {
            "WP3-2B": "COMPLETED_SCREENING_PROPOSAL_ACCEPTED_ON_MAIN",
            "WP3-3": "COMPLETED_MULTIDIMENSIONAL_LONGLIST_ACCEPTED_ON_MERGE",
            "WP3-4": "COMPLETED_HISTORICAL_CORE20_REVIEW_ACCEPTED_ON_MERGE",
            "WP3-5": "READY_FOR_RESEARCH_OBJECT_AND_ENTRY_BASELINE",
            "WP3-6": "READY_FOR_CANDIDATE_REBUILD_PROPOSAL",
        }
    )
    register["wp3_2b"] = {
        "status": "COMPLETED_SCREENING_PROPOSAL_ACCEPTED_ON_MAIN",
        "input_current_session": "2026-07-24",
        "full_market_rows": 5530,
        "eligible_universe_rows": 5525,
        "excluded_rows": 5,
        "research_workload_queue_rows": 100,
        "method": "DATA_READINESS_AND_LIQUIDITY_ONLY",
        "investment_ranking": False,
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "next_gate": "WP3_3_WP3_4_MULTIDIMENSIONAL_SCREENING_AND_CORE20_REVIEW",
    }
    register["wp3_3_4"] = {
        "status": "COMPLETED_PROPOSAL_ACCEPTED_ON_MAIN_IF_THIS_PR_MERGES",
        "proposal_id": proposal_dir.name,
        "proposal_path": str(proposal_dir.relative_to(repo_root)),
        "as_of_date": manifest["as_of_date"],
        "contract_version": manifest["contract_version"],
        "method": manifest["method"],
        "valuation_refresh": manifest["valuation_refresh"],
        "full_market_rows": metrics["full_market_rows"],
        "multidimensional_eligible_rows": metrics["multidimensional_eligible_rows"],
        "industry_longlist_rows": metrics["industry_longlist_rows"],
        "deep_dive_rows": metrics["deep_dive_rows"],
        "structured_research_rows": metrics["structured_research_rows"],
        "watch_rows": metrics["watch_rows"],
        "historical_core20_review_rows": metrics["historical_core20_review_rows"],
        "core20_longlist_overlap": metrics["core20_longlist_overlap"],
        "unified_research_workplan_rows": metrics["unified_research_workplan_rows"],
        "historical_core20_grandfathering": False,
        "automatic_candidate_decision": False,
        "promotion_evidence": "GIT_HISTORY_ON_PR_MERGE",
        "candidate_membership_mutations": 0,
        "research_object_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "next_gate": manifest["next_gate"],
    }
    register["github_main_head_at_wp3_3_4_closure"] = "RESOLVED_BY_GIT_HISTORY_ON_PR_MERGE"
    write_json(register_path, register)
    master_path.write_text(build_master_plan(manifest), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--proposal-dir", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    finalize(root, root / args.proposal_dir)


if __name__ == "__main__":
    main()
