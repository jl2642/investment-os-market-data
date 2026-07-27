from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

AS_OF = "2026-07-27"
R5_PR = 159
R5_FINAL_HEAD_SHA = "3e654c2cbbdbc563999799561b9bcf4b5fa7a4ae"
R5_MERGE_SHA = "3cb173851eac4388f24785cd7a43cd557c58a3bc"
OBSERVATION_START = "2026-08-01"
OBSERVATION_END = "2026-08-31"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    rows = registry.setdefault("assets", [])
    for index, row in enumerate(rows):
        if row.get("asset_id") == asset["asset_id"]:
            rows[index] = {**row, **asset}
            return
    rows.append(asset)


def append_once(text: str, marker: str, block: str) -> str:
    if marker in text:
        return text
    return text.rstrip() + "\n\n" + block.rstrip() + "\n"


def replace_line(text: str, prefix: str, replacement: str) -> str:
    lines = text.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            replaced = True
            break
    if not replaced:
        lines.insert(2, replacement)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-pr", type=int, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    prod = root / "investment_os_runtime/80_PRODUCTION_ACCEPTANCE"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"
    protected = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }

    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    r5_contract = read_json(control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json")
    r5_acceptance = read_json(control / "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json")

    allowed_steps = {
        "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN",
        "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN",
    }
    if execution.get("current_step") not in allowed_steps:
        raise ValueError(f"R6 is not authorized from current step: {execution.get('current_step')}")
    if int(r5_contract.get("source_pr", 0)) != R5_PR:
        raise ValueError("R5 Canonical product is not present")
    if execution.get("next_task") not in {
        "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN",
        "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08",
    }:
        raise ValueError("R6 is not the sole next authorized task")

    contract_path = control / "R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json"
    prior = read_json(contract_path) if contract_path.exists() else {}
    materialization_head = str(prior.get("source_head_sha") or args.source_head_sha)
    source_pr = int(prior.get("source_pr") or args.source_pr)
    source_branch = str(prior.get("source_branch") or args.source_branch)

    r5_contract["status"] = "COMPLETED_ON_MAIN"
    r5_contract["final_governed_head_sha"] = R5_FINAL_HEAD_SHA
    r5_contract["merge_sha"] = R5_MERGE_SHA
    r5_contract["promotion_evidence"] = "MERGED_PR_AND_FILE_PRESENCE"
    r5_acceptance["status"] = "COMPLETED_ON_MAIN"
    r5_acceptance["final_governed_head_sha"] = R5_FINAL_HEAD_SHA
    r5_acceptance["merge_sha"] = R5_MERGE_SHA

    domains = [
        {
            "domain_id": "AUTHORITY_AND_CURRENT",
            "acceptance_question": "Can any new conversation recover the same Canonical state without relying on memory?",
            "initial_status": "READY_FOR_REPLAY_TEST",
            "completion_evidence": ["GitHub main recovery", "Current asset registry", "watermark and lineage reconciliation"],
        },
        {
            "domain_id": "AUTOMATIC_DATA_REFRESH",
            "acceptance_question": "Do governed public-data refreshes complete or fail closed on the expected cadence?",
            "initial_status": "PENDING_FULL_MONTH_OBSERVATION",
            "completion_evidence": ["completed-close equity marks", "fund NAV freshness", "screening refresh receipts", "stale-input blocking"],
        },
        {
            "domain_id": "USER_POSITION_DELTA",
            "acceptance_question": "Are Real-account changes captured only from explicit user zero-Delta or transaction Delta?",
            "initial_status": "PENDING_USER_INPUT_CADENCE",
            "completion_evidence": ["dated zero-Delta confirmations", "transaction and cash-flow Delta records", "no silence inference"],
        },
        {
            "domain_id": "OPERATING_PRODUCTS",
            "acceptance_question": "Are status, daily, weekly, monthly and event products generated with evidence and blockers?",
            "initial_status": "PENDING_FULL_MONTH_OBSERVATION",
            "completion_evidence": ["daily samples", "weekly samples", "one complete monthly review", "event and stale-data handling"],
        },
        {
            "domain_id": "ATTRIBUTION_INTEGRATION",
            "acceptance_question": "Does the monthly product reconcile period returns, flows and R5 attribution without using snapshot P&L as return?",
            "initial_status": "PENDING_MONTH_END_LEDGER",
            "completion_evidence": ["month-start baseline", "transaction/flow ledger", "month-end marks", "P&L bridge", "Candidate maturity status"],
        },
        {
            "domain_id": "RECOVERY_AND_RERUN",
            "acceptance_question": "Can failed or missed cycles be recovered deterministically without duplicate economic mutations?",
            "initial_status": "READY_FOR_INJECTION_TEST",
            "completion_evidence": ["cross-conversation replay", "missed-run backfill", "duplicate-run idempotence", "recovery log"],
        },
        {
            "domain_id": "EVIDENCE_TRACEABILITY",
            "acceptance_question": "Can every material conclusion be traced to Current data, source timestamp and decision rule?",
            "initial_status": "READY_FOR_SAMPLE_AUDIT",
            "completion_evidence": ["source and timestamp", "watermark", "rule reference", "confidence/blocker"],
        },
        {
            "domain_id": "ZERO_AUTHORITY_VIOLATION",
            "acceptance_question": "Does the system preserve user control over holdings, Candidate, rules and orders for the whole month?",
            "initial_status": "CONTINUOUS_MONITORING_REQUIRED",
            "completion_evidence": ["zero unauthorized Real mutations", "zero unauthorized Simulation mutations", "zero Candidate/rule mutations", "zero orders"],
        },
    ]

    contract = {
        "contract_id": "R6_PRODUCTION_ACCEPTANCE_CONTRACT_V1",
        "status": "STARTED_CURRENT_IF_PRESENT_ON_MAIN_OBSERVATION_NOT_COMPLETE",
        "as_of": AS_OF,
        "source_pr": source_pr,
        "source_branch": source_branch,
        "source_head_sha": materialization_head,
        "r5_source_pr": R5_PR,
        "r5_final_governed_head_sha": R5_FINAL_HEAD_SHA,
        "r5_merge_sha": R5_MERGE_SHA,
        "acceptance_mode": "SUPERVISED_PRODUCTION_ACCEPTANCE",
        "observation_window": {
            "type": "COMPLETE_CALENDAR_MONTH",
            "start": OBSERVATION_START,
            "end": OBSERVATION_END,
            "earliest_final_close": "AFTER_2026-08-31_CLOSE_AND_REQUIRED_FUND_NAV_COMPLETION",
        },
        "domain_count": len(domains),
        "domains": domains,
        "production_completion_definition": {
            "full_month_complete": True,
            "all_material_cycles_evidenced": True,
            "monthly_attribution_reconciled": True,
            "recovery_and_rerun_passed": True,
            "cross_conversation_recovery_passed": True,
            "unauthorized_mutations": 0,
            "orders": 0,
            "user_readable_operating_guide_delivered": True,
        },
        "post_acceptance_operating_model": "AUTONOMOUS_RESEARCH_REFRESH_REPORTING_AND_PROPOSALS_WITH_USER_CONTROLLED_PORTFOLIO_STATE",
        "operating_activation": False,
        "schedule_activation_count": 0,
        "trade_authority": TRADE_AUTHORITY,
    }

    checkpoints = [
        ("R6-CP00", "Preflight and R5 main-lineage reconciliation", "PASS"),
        ("R6-CP01", "Month-start baseline and explicit Real-account Delta", "PENDING"),
        ("R6-CP02", "First completed-close daily cycle", "PENDING"),
        ("R6-CP03", "First weekly portfolio and Candidate review", "PENDING"),
        ("R6-CP04", "Cross-conversation recovery test", "PENDING"),
        ("R6-CP05", "Missed-run and duplicate-run recovery test", "PENDING"),
        ("R6-CP06", "Mid-month evidence trace audit", "PENDING"),
        ("R6-CP07", "Month-end holdings, flows, marks and benchmark close", "PENDING"),
        ("R6-CP08", "Monthly performance and R5 attribution integration", "PENDING"),
        ("R6-CP09", "Zero-authority-violation audit and final acceptance", "PENDING"),
    ]
    observation = {
        "ledger_id": "R6_OBSERVATION_LEDGER_CURRENT_V1",
        "status": "OPEN_SUPERVISED_ACCEPTANCE",
        "as_of": AS_OF,
        "observation_start": OBSERVATION_START,
        "observation_end": OBSERVATION_END,
        "checkpoint_total": len(checkpoints),
        "checkpoint_passed": 1,
        "checkpoints": [
            {
                "checkpoint_id": checkpoint_id,
                "description": description,
                "status": status,
                "evidence": [
                    f"R5 PR #{R5_PR} merged as {R5_MERGE_SHA}",
                    "R6 contract, runbook and responsibility matrix installed",
                ] if checkpoint_id == "R6-CP00" else [],
                "completed_at": AS_OF if checkpoint_id == "R6-CP00" else None,
            }
            for checkpoint_id, description, status in checkpoints
        ],
        "current_blockers": [
            "The full August 2026 calendar-month observation has not started.",
            "Current accepted position and decision watermark remains 2026-07-24_CLOSE until refreshed.",
            "A verified month-start holdings, cash, transaction and external-flow baseline is required.",
            "Operating schedules remain inactive until R6 final acceptance.",
        ],
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "legacy_decisions": 0,
            "rules": 0,
            "orders": 0,
        },
        "operating_activation": False,
        "trade_authority": TRADE_AUTHORITY,
    }

    gate = {
        "gate_id": "R6_OPERATING_ACTIVATION_GATE_V1",
        "status": "CLOSED_PENDING_FULL_MONTH_ACCEPTANCE",
        "can_activate_now": False,
        "required_passes": [row[0] for row in checkpoints],
        "passed": ["R6-CP00"],
        "pending": [row[0] for row in checkpoints if row[0] != "R6-CP00"],
        "activation_effect_if_finally_approved": {
            "operating_mode": "ACTIVE_SUPERVISED_AUTONOMOUS_RESEARCH_AND_REPORTING",
            "automatic_portfolio_mutation": False,
            "automatic_candidate_or_rule_mutation": False,
            "automatic_order_creation": False,
            "user_final_decision": True,
        },
        "operating_activation": False,
        "trade_authority": TRADE_AUTHORITY,
    }

    responsibility = f"""# 股票投资助手｜用户—系统职责矩阵 CURRENT

- 当前阶段：`R6生产验收进行中`
- 验收窗口：`{OBSERVATION_START}`至`{OBSERVATION_END}`
- 当前Operating Activation：`false`
- 目标运行模式：`自主研究、刷新、报告和Proposal；用户控制真实状态与最终决策`
- trade_authority：`NONE`

## 一、R6通过后系统自主完成

| 模块 | 系统自主职责 | 失败时处理 |
|---|---|---|
| 市场与公开数据 | 刷新可获得的收盘行情、基金净值、财务与公告证据并记录时间戳 | 显示`BLOCKED/STALE`，不得补造数据 |
| 全市场与Candidate | 执行筛选、Research Queue排序、Entry Baseline和20/60/120日观察 | 只形成Proposal，不自动改变成员 |
| 持仓研究 | 更新投资逻辑、估值、风险触发、组合角色和证据缺口 | 不为制造建议而降低门槛 |
| 模拟盘 | 按已批准状态计算市值、现金、P&L桥接、袖套暴露和动作Proposal | 不自动交易或改写历史成交 |
| 周期产品 | 生成统一状态、日报、周报、月报、季报、年报和事件警报 | 输入不全时保留产品但明确阻断章节 |
| 收益归因 | 执行个股、袖套、仓位、时点、现金、Candidate和规则归因 | 快照P&L不得冒充期间收益 |
| 恢复与重跑 | 从GitHub Canonical恢复，在漏跑或失败后去重补跑 | 不重复产生经济状态变更 |
| 规则迭代 | 汇总多期证据，形成校准Proposal和回归测试 | 未经用户批准不应用 |

## 二、用户必须完成

| 场景 | 用户输入 | 最低要求 |
|---|---|---|
| 真实账户无变化 | 明确零Delta及截止日期 | 例如“截至2026-08-07收盘，真实账户无交易、无转入转出” |
| 真实账户有变化 | 提供交易或现金Delta | 账户、日期、证券/现金项目、买卖方向、数量、价格、费用税费 |
| 新增投资约束 | 告知资金用途、期限、风险偏好或禁投条件 | 系统不得从旧对话推断关键新约束 |
| 需要改变持仓/Candidate/规则 | 审阅并明确批准Proposal | 用户批准后仍须走独立受治理状态更新，不自动下单 |
| 外部无法自动取得的信息 | 提供截图、文件或事实确认 | 包括券商成交、真实费用、外部资金流和特殊公司信息 |
| GitHub治理 | 合并需要晋级为Canonical的PR | 日常分析不要求手工维护来源压缩包 |

## 三、用户不再需要做

- 不需要每天重新上传全部持仓或来源三包；只提供真实账户Delta或零Delta。
- 不需要手工整理公开行情、公告、Candidate排名和周期归因。
- 不需要在固定旧对话框中运行；新对话应从GitHub Canonical恢复。
- 不需要为了让系统给出结论而主动填补未知数据；系统必须Fail Closed。
- 不需要维持真实证券账户固定现金比例；现金继续作为执行余额处理。

## 四、最简使用入口

日常可直接说：

> 基于GitHub Canonical恢复股票投资助手，检查最新数据水位；截至某日收盘真实账户零Delta/以下Delta；运行本期状态、组合、Candidate、风险和动作审查。

系统必须先恢复Current和检查数据水位，再决定生成正式结论或显示`BLOCKED`。
"""

    runbook = f"""# 股票投资助手｜R6 Production Acceptance Runbook CURRENT

## 1. 当前判断

R6已经启动，但不能在同一天宣称完成。完整生产验收至少需要一个完整自然月，即`{OBSERVATION_START}`至`{OBSERVATION_END}`，并在月末收盘、基金净值和交易/资金流Ledger齐备后完成最终验收。

## 2. 验收期运行顺序

1. 月初建立真实账户、模拟盘、Candidate、现金、交易和Benchmark基线；
2. 每个有效收盘周期检查市场数据、基金净值和用户Delta连续性；
3. 运行日度状态与异常检查；
4. 每周运行组合、Candidate和研究缺口审查；
5. 月中执行跨对话恢复、漏跑补跑和重复运行去重测试；
6. 月末冻结期末水位，完成期间收益、资金流和R5归因桥接；
7. 审计全部证据路径、状态变化及零越权记录；
8. 只有全部Checkpoint通过，才可将Operating Activation改为`true`。

## 3. 运营期产品节奏

- 日度：状态变化、重大事件、数据陈旧、风险触发和下一检查；
- 周度：袖套偏离、持仓例外、Candidate生命周期和研究优先级；
- 月度：期间收益、组合结构、逐仓复盘、Candidate结果和规则校准；
- 季度：财务、估值、组合角色和Candidate晋级/退出重估；
- 年度：策略绩效、研究质量、决策治理和规则升级。

## 4. 永久边界

R6完成也不会授予自动交易权限。系统可以自主搜集、分析、刷新、报告、归因和形成Proposal，但真实账户、模拟盘、Candidate、正式规则和订单的改变仍必须由用户明确批准。
"""

    acceptance = {
        "acceptance_id": "R6_PRODUCTION_ACCEPTANCE_START_RECORD_V1",
        "status": "STARTED_CURRENT_IF_PRESENT_ON_MAIN_NOT_FINAL_ACCEPTANCE",
        "source_pr": source_pr,
        "source_branch": source_branch,
        "source_head_sha": materialization_head,
        "r5_merge_reconciled": True,
        "preflight_passed": True,
        "full_month_complete": False,
        "checkpoint_passed": 1,
        "checkpoint_total": len(checkpoints),
        "operating_activation": False,
        "schedule_activation_count": 0,
        "protected_state_hashes": protected,
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "legacy_decisions": 0,
            "rules": 0,
            "orders": 0,
        },
        "next_required_action": "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08",
        "trade_authority": TRADE_AUTHORITY,
    }

    status = f"""# 股票投资助手｜R6 Production Acceptance CURRENT

- 状态：`IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN`
- R5 main合并：PR `#{R5_PR}` / `{R5_MERGE_SHA}`
- 验收窗口：`{OBSERVATION_START}`至`{OBSERVATION_END}`
- Checkpoint：`1/{len(checkpoints)}`
- 完整自然月：`未完成`
- Operating Activation：`false`
- Schedule Activation：`0`
- Orders：`0`
- trade_authority：`NONE`

R6验收框架、用户—系统职责、恢复重跑计划和观察Ledger已安装。当前进入监督式生产验收期，不得提前宣称系统已生产化。完成完整自然月并通过全部Checkpoint后，股票投资助手的集中开发阶段才可基本结束，转入正式运营和持续迭代。
"""

    execution["current_step"] = "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN"
    execution["latest_completed_main_pr"] = R5_PR
    execution["latest_completed_main_merge_sha"] = R5_MERGE_SHA
    execution["latest_governed_merge_sha"] = R5_MERGE_SHA
    execution["github_merge_sha"] = R5_MERGE_SHA
    execution["development_roadmap"]["R5"] = {
        "name": "ATTRIBUTION_AND_CALIBRATION",
        "status": "COMPLETED_ON_MAIN",
        "source_pr": R5_PR,
        "source_head_sha": R5_FINAL_HEAD_SHA,
        "merge_sha": R5_MERGE_SHA,
    }
    execution["development_roadmap"]["R6"] = {
        "name": "PRODUCTION_ACCEPTANCE",
        "status": "IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": source_pr,
        "source_head_sha": materialization_head,
        "observation_start": OBSERVATION_START,
        "observation_end": OBSERVATION_END,
        "checkpoint_passed": 1,
        "checkpoint_total": len(checkpoints),
    }
    execution["production_acceptance_r6"] = {
        "status": "IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN",
        "acceptance_mode": "SUPERVISED_PRODUCTION_ACCEPTANCE",
        "observation_start": OBSERVATION_START,
        "observation_end": OBSERVATION_END,
        "checkpoint_passed": 1,
        "checkpoint_total": len(checkpoints),
        "full_month_complete": False,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "source_pr": source_pr,
    }
    execution["next_task"] = "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08"
    execution["overall_status"] = "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_NOT_PRODUCTION_COMPLETE"
    execution["operating_activation"] = False
    execution["ready_for_user_decision_count"] = 0
    execution["implementation_ready_count"] = 0
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V13_R6_PRODUCTION_ACCEPTANCE"
    execution["release_id"] = "INVESTMENT_OS_R23_20260727_R6_PRODUCTION_ACCEPTANCE_START"
    execution["release_sequence"] = 23
    execution["trade_authority"] = TRADE_AUTHORITY

    registry["active_branch_candidate"] = source_branch
    registry["latest_completed_main_pr"] = R5_PR
    registry["latest_completed_main_merge_sha"] = R5_MERGE_SHA
    registry["latest_governed_merge_sha"] = R5_MERGE_SHA
    registry["github_merge_sha"] = R5_MERGE_SHA
    registry["registry_id"] = "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V15_R6_PRODUCTION_ACCEPTANCE"
    registry["registry_status"] = "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN"
    registry["release_id"] = "INVESTMENT_OS_R23_20260727_R6_PRODUCTION_ACCEPTANCE_START"
    registry["release_sequence"] = 23
    for row in registry.get("assets", []):
        if row.get("asset_id") == "GITHUB_ACTIVE_RUNTIME":
            row["branch_candidate"] = source_branch
            row["latest_governed_merge_sha"] = R5_MERGE_SHA
            row["status"] = "GITHUB_MAIN_PR159_CURRENT_R6_ACCEPTANCE_CANDIDATE"
    asset_specs = [
        ("R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT", "investment_os_runtime/00_CONTROL/R6_PRODUCTION_ACCEPTANCE_CONTRACT_CURRENT.json", "R6 full-month production acceptance contract"),
        ("R6_PRODUCTION_ACCEPTANCE_START_RECORD", "investment_os_runtime/00_CONTROL/R6_PRODUCTION_ACCEPTANCE_RECORD_CURRENT.json", "R6 preflight and zero-mutation start acceptance"),
        ("R6_OPERATING_ACTIVATION_GATE_CURRENT", "investment_os_runtime/00_CONTROL/R6_OPERATING_ACTIVATION_GATE_CURRENT.json", "Closed operating-activation gate pending full-month evidence"),
        ("R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT", "investment_os_runtime/00_CONTROL/R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT.md", "User and autonomous-system responsibility boundary"),
        ("R6_STATUS_CURRENT", "investment_os_runtime/00_CONTROL/R6_STATUS_CURRENT.md", "Human-readable R6 stage status"),
        ("R6_OBSERVATION_LEDGER_CURRENT", "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/R6_OBSERVATION_LEDGER_CURRENT.json", "Full-month acceptance checkpoint ledger"),
        ("R6_PRODUCTION_RUNBOOK_CURRENT", "investment_os_runtime/80_PRODUCTION_ACCEPTANCE/R6_PRODUCTION_RUNBOOK_CURRENT.md", "Production acceptance and future operating runbook"),
    ]
    for asset_id, location, role in asset_specs:
        upsert_asset(registry, {
            "asset_id": asset_id,
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "location": location,
            "role": role,
            "source_pr": source_pr,
            "source_branch": source_branch,
            "source_head_sha": materialization_head,
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": TRADE_AUTHORITY,
        })

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = replace_line(master, "- 最新已完成main合并：", f"- 最新已完成main合并：PR #{R5_PR} / `{R5_MERGE_SHA}`")
    master = master.replace("### R5｜Attribution & Calibration\n\n- 完成个股", "### R5｜Attribution & Calibration\n\n- 状态：`COMPLETED_ON_MAIN`；来源PR：`#159`。\n- 完成个股", 1) if "### R5｜Attribution & Calibration\n\n- 状态：" not in master else master
    master = master.replace("### R6｜Production Acceptance\n\n- 完整自然月实跑；", "### R6｜Production Acceptance\n\n- 状态：`IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN`；完整自然月尚未完成。\n- 完整自然月实跑；", 1) if "### R6｜Production Acceptance\n\n- 状态：" not in master else master
    master = master.replace("`R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN`", "`RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08`", 1)
    master = append_once(master, "## R6启动与生产验收状态", f"""## R6启动与生产验收状态

- R5已通过PR `#{R5_PR}`合并至main，Merge SHA为`{R5_MERGE_SHA}`。
- R6合同、用户—系统职责矩阵、观察Ledger、恢复重跑Runbook和Activation Gate已经安装。
- 当前Checkpoint为`1/{len(checkpoints)}`，仅完成Preflight；Operating Activation仍为`false`。
- 首个可用完整自然月验收窗口为`{OBSERVATION_START}`至`{OBSERVATION_END}`。
- R6最终通过后，固定集中开发路线结束，系统进入正式运营、绩效复盘和受治理持续迭代。
- 当前真实账户、模拟盘、Candidate、规则、旧决策和订单变更均为`0`。
""")

    capability_path = control / "CAPABILITY_REALITY_MATRIX_CURRENT.md"
    capability = capability_path.read_text(encoding="utf-8")
    capability = replace_line(capability, "- 当前阶段：", "- 当前阶段：`R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN`")
    capability = replace_line(capability, "- 下一阶段：", "- 下一阶段：`完成完整自然月验收后进入正式运营与持续迭代`")
    capability = append_once(capability, "## R6生产验收边界", f"""## R6生产验收边界

- 已完成：R5 main晋级、R6验收合同、职责矩阵、观察Ledger、恢复重跑计划及Activation Gate安装。
- 尚未完成：`{OBSERVATION_START}`至`{OBSERVATION_END}`完整自然月运行、月末归因、跨对话恢复及漏跑重跑实证。
- 当前运行模式是监督式生产验收，不是已激活的无人值守生产。
- R6通过后系统自主完成研究、公开数据刷新、报告、归因和Proposal；用户继续负责真实账户Delta、关键约束、状态变更批准和交易执行。
""")

    guide_path = control / "USER_OPERATING_GUIDE_CURRENT.md"
    guide = guide_path.read_text(encoding="utf-8")
    guide = replace_line(guide, "- 当前阶段：", "- 当前阶段：`R6生产验收进行中`")
    guide = append_once(guide, "## 六、R6之后的正式使用方式", """## 六、R6之后的正式使用方式

股票投资助手最终采用“系统自主研究与运营、用户控制投资状态”的模式。系统自主刷新公开数据、筛选Candidate、更新研究、生成周期产品、执行归因并形成Proposal；用户仅持续提供真实账户零Delta或交易Delta、无法自动取得的私有事实、关键约束及对持仓/Candidate/规则变化的明确批准。详细边界以`R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT.md`为准。
""")

    test_path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    test_text = test_path.read_text(encoding="utf-8")
    marker = '    elif step == "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN":'
    if marker not in test_text:
        anchor = '    else:\n        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'
        block = '''    elif step == "R6_PRODUCTION_ACCEPTANCE_IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R5"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R5"]["merge_sha"] == "3cb173851eac4388f24785cd7a43cd557c58a3bc"
        assert register["development_roadmap"]["R6"]["status"] == "IN_PROGRESS_CURRENT_IF_PRESENT_ON_MAIN"
        assert register["production_acceptance_r6"]["full_month_complete"] is False
        assert register["production_acceptance_r6"]["checkpoint_passed"] == 1
        assert register["production_acceptance_r6"]["checkpoint_total"] == 10
        assert register["operating_activation"] is False
        assert register["ready_for_user_decision_count"] == 0
        assert register["implementation_ready_count"] == 0
        assert register["next_task"] == "RUN_R6_SUPERVISED_OPERATING_OBSERVATION_2026_08"
    else:
        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'''
        if anchor not in test_text:
            raise ValueError("forward-lineage insertion anchor not found")
        test_text = test_text.replace(anchor, block, 1)

    write_json(control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json", r5_contract)
    write_json(control / "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json", r5_acceptance)
    write_json(contract_path, contract)
    write_json(control / "R6_PRODUCTION_ACCEPTANCE_RECORD_CURRENT.json", acceptance)
    write_json(control / "R6_OPERATING_ACTIVATION_GATE_CURRENT.json", gate)
    write_text(control / "R6_USER_SYSTEM_RESPONSIBILITY_MATRIX_CURRENT.md", responsibility)
    write_text(control / "R6_STATUS_CURRENT.md", status)
    write_json(prod / "R6_OBSERVATION_LEDGER_CURRENT.json", observation)
    write_text(prod / "R6_PRODUCTION_RUNBOOK_CURRENT.md", runbook)
    write_json(control / "EXECUTION_REGISTER_CURRENT.json", execution)
    write_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json", registry)
    write_text(master_path, master)
    write_text(capability_path, capability)
    write_text(guide_path, guide)
    write_text(test_path, test_text)

    print({
        "r5_main_reconciled": R5_MERGE_SHA,
        "r6_status": "IN_PROGRESS",
        "observation_window": f"{OBSERVATION_START}..{OBSERVATION_END}",
        "checkpoints": "1/10",
        "operating_activation": False,
        "mutations": 0,
        "orders": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
