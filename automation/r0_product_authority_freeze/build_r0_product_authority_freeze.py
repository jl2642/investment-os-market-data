from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_PR = 152
SOURCE_BRANCH = "agent/r0-product-authority-freeze"
LATEST_COMPLETED_MAIN_PR = 151
LATEST_COMPLETED_MAIN_MERGE_SHA = "247203c005b76cfa32a0d04d31390631c304e738"
TRADE_AUTHORITY = "NONE"
STATUS_DATE = "2026-07-27"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    assets = registry.setdefault("assets", [])
    for index, existing in enumerate(assets):
        if existing.get("asset_id") == asset["asset_id"]:
            assets[index] = {**existing, **asset}
            return
    assets.append(asset)


def update_lineage_test(root: Path) -> None:
    path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    text = path.read_text(encoding="utf-8")
    if "R0_PRODUCT_AUTHORITY_FREEZE_CURRENT_IF_PRESENT_ON_MAIN" in text:
        return
    needle = '    else:\n        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'
    replacement = '''    elif step == "R0_PRODUCT_AUTHORITY_FREEZE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["product_authority"]["source_pr"] == 152
        assert register["product_authority"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R0"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R1"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["status"] == "PARTIALLY_COMPLETE_NO_USER_ACTION_PACK"
        assert register["next_task"] == "R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN"
    else:
        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'''
    if needle not in text:
        raise ValueError("Unable to locate WP3 lineage forward-progression insertion point")
    path.write_text(text.replace(needle, replacement), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    decisions = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS"

    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    wp5_contract_path = control / "WP5_PORTFOLIO_DECISION_CONTRACT.json"
    master_plan_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    charter_path = control / "INVESTMENT_ASSISTANT_PRODUCT_CHARTER_CURRENT.md"
    matrix_path = control / "CAPABILITY_REALITY_MATRIX_CURRENT.md"
    guide_path = control / "USER_OPERATING_GUIDE_CURRENT.md"
    acceptance_path = control / "R0_PRODUCT_AUTHORITY_FREEZE_ACCEPTANCE_RECORD.json"

    real_path = root / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    simulation_path = root / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_decisions_path = decisions / "DECISION_PROPOSALS_CURRENT.json"

    execution = read_json(execution_path)
    registry = read_json(registry_path)
    source_head_sha = str(args.source_head_sha)

    protected_hashes = {
        "real_account_positions_sha256": sha256_file(real_path),
        "simulation_positions_sha256": sha256_file(simulation_path),
        "candidate_current_sha256": sha256_file(candidate_path),
        "legacy_decisions_sha256": sha256_file(legacy_decisions_path),
    }

    charter = f'''# 股票投资助手｜Product Charter CURRENT

- 状态日期：{STATUS_DATE}
- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#{SOURCE_PR}`
- 来源Head：`{source_head_sha}`
- 权威仓库：`jl2642/investment-os-market-data`
- 交易权限：`NONE`

## 1. 产品使命

股票投资助手的目标不是生成更多工程文件，而是形成一个可持续运行、证据可追溯、由用户最终决策的股票投资闭环：

`市场与公司数据 → 全市场筛选 → Candidate分层 → 深入研究与估值 → 组合构建 → 持仓动作建议 → 周期运营 → 收益归因与策略校准`

## 2. 用户最终产品

系统完成后必须稳定交付：

1. 真实账户Current、模拟盘Current及持仓连续性状态；
2. Candidate新增、升级、降级和退出原因；
3. 统一口径的公司研究、估值、组合角色和风险触发条件；
4. 覆盖全部持仓的增持、持有、减持、退出、观察或等待证据动作矩阵；
5. 日报、周报、月报、季报和年度策略复盘；
6. 个股、行业、仓位、时点、现金和规则层面的收益归因；
7. 用户批准后的受治理状态更新，但不自动下单。

## 3. 永久安全边界

- 不自动改变真实账户持仓；
- 不自动改变模拟盘持仓；
- 不自动改变Candidate成员；
- 不自动创建订单；
- 不从沉默推断用户没有交易；
- 不把盘中价格当作正式收盘价格；
- 不因存在现金而强制投资；
- 不在证据不足时强制生成买卖建议；
- `trade_authority=NONE`。

## 4. 权威顺序

1. 本Product Charter；
2. `WORK_PACKAGE_MASTER_PLAN_CURRENT.md`；
3. `EXECUTION_REGISTER_CURRENT.json`；
4. `AUTHORITATIVE_ASSET_REGISTRY.json`；
5. 各领域Canonical Current与验收记录；
6. GitHub受治理合并历史；
7. File Library中的明确晋级副本；
8. 对话记忆不具备权威性。

发生冲突时，必须停止推进并按上述顺序修复，不得临时发明新阶段。

## 5. 完成定义

Work Package完成必须同时满足：

- 功能和数据资产可用；
- 用户可读产品已交付；
- 输入、证据、限制和置信度明确；
- 对下游阶段的接口稳定；
- 安全边界和回归验收通过；
- Master Plan和Execution Register同步更新；
- 不得仅因JSON、Workflow、Schema或测试通过而宣称产品完成。

## 6. 阶段变更规则

- 只有Master Plan列出的阶段才可执行；
- 新阶段或拆分必须先修改Master Plan并经用户明确同意；
- PR标题、临时分支名和Execution Register中的临时Next Task不构成新阶段授权；
- 历史`WP5-A`至`WP5-G`仅作为执行标签保留，不再作为未来路线；
- `WP5-H`从未获得冻结授权，状态为`VOID_NOT_STARTED`。

## 7. 当前产品判断

当前系统是：

`具备较强数据治理、Candidate筛选和部分研究/组合控制能力的投资研究Beta`

当前系统不是：

`已经完成并稳定运行的全闭环投资决策系统`

R0之后的固定开发顺序为：

`R1 Decision Coverage Completion → R2 Portfolio Construction Synthesis → R3 Position Action Matrix & User Decision Pack → R4 Operating Products → R5 Attribution & Calibration → R6 Production Acceptance`
'''
    write_text(charter_path, charter)

    master_plan = f'''# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：{STATUS_DATE}
- 产品权威：`INVESTMENT_ASSISTANT_PRODUCT_CHARTER_CURRENT.md`
- Canonical状态源：`EXECUTION_REGISTER_CURRENT.json`
- 最新已完成main合并：PR #{LATEST_COMPLETED_MAIN_PR} / `{LATEST_COMPLETED_MAIN_MERGE_SHA}`
- 本轮治理来源：PR #{SOURCE_PR} / `{source_head_sha}`
- 本轮状态：`CURRENT_IF_PRESENT_ON_MAIN`
- File Library：`RECOVERY_DISTRIBUTION_ONLY_PENDING_EXPLICIT_PROMOTION`
- 交易权限：`NONE`

## 一、固定产品架构

| Work Package | 产品职责 | 当前真实成熟度 |
|---|---|---|
| WP1 | 规则、Canonical、Schema、Runtime和恢复 | `COMPLETED` |
| WP2 | 真实账户、模拟盘、行情、基金净值和用户交易Delta | `CAPABILITY_ACCEPTED_OPERATING_HISTORY_NOT_YET_VALIDATED` |
| WP3 | 全市场筛选、Candidate生命周期和效果评价 | `ENGINE_ACCEPTED_OUTCOME_WINDOWS_INCOMPLETE` |
| WP4 | 公司研究、估值、组合适配和事件监控 | `METHOD_ACCEPTED_COVERAGE_PARTIAL` |
| WP5 | 组合构建、动作矩阵和用户决策包 | `PARTIALLY_COMPLETE_NO_USER_ACTION_PACK` |
| WP6 | 日报、周报、月报、季报和年度运营产品 | `NOT_STARTED_AS_FORMAL_PRODUCT` |
| WP7 | 收益归因、决策复盘和策略校准 | `NOT_STARTED_AS_FORMAL_PRODUCT` |

## 二、截至R0的实际能力

- 真实账户：7个持仓Current；第一轮产品结构审查已完成；三只债基完整穿透未完成。
- 模拟盘：16个持仓Current；2只Core2和3只P0具备较高等级研究；其余11只缺统一决策级覆盖。
- Candidate：2只Core、38只Shadow、33只Research Queue、0只Ready。
- 全市场：5,530只A股Canonical范围；Candidate刷新能力已安装，但20/60/120日效果窗口未成熟。
- 用户决策：当前Ready为0；不存在已授权调仓或订单。

## 三、历史执行映射

| 历史PR/标签 | 实际交付 | 映射后的正式位置 |
|---|---|---|
| PR #141 | WP3 Research Objects、Entry Baseline和Candidate重建 | WP3已完成初始Candidate基线 |
| PR #143 | 美的、长江电力Core2初始研究和Decision Interface | WP4部分覆盖 |
| PR #144 | R1成熟度纠偏和缺口登记 | 历史审计，不是产品阶段 |
| PR #145–#146 | WP2-R、WP3-R、WP4-B能力补强及R2收口 | WP2–WP4能力硬化 |
| PR #147 / WP5-A–C | WP5启动、全持仓初审、P0研究准备 | WP5-1及WP5-2启动 |
| PR #148 / WP5-D | 汇川、宁德、工业富联P0重审 | WP5-2部分完成 |
| PR #149 / WP5-E | 完成收盘及条件动作门禁 | 横向运营控制，不是阶段 |
| PR #150 / WP5-F | 用户持仓连续性接口 | 横向数据控制，不是阶段 |
| PR #151 / WP5-G | 真实账户第一轮结构审查及晋级语义修复 | WP5-2部分完成 |
| WP5-H | 未经计划冻结的临时名称 | `VOID_NOT_STARTED` |

## 四、冻结后的有限开发路线

### R0｜Product Authority Freeze

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 交付：Product Charter、Master Plan、Capability Reality Matrix、Execution Register、User Operating Guide。
- 禁止：新研究、调仓、Candidate变化、订单和架构扩张。

### R1｜Decision Coverage Completion

- 刷新2只Core2和3只P0，不从头重建；
- 补齐其余11只模拟盘持仓的基本面、估值、组合角色和退出条件；
- 完成三只债基穿透、两只标普500ETF执行质量比较及A500/中证500角色确认；
- 交付全部当前持仓的统一Decision Coverage Pack。

### R2｜Portfolio Construction Synthesis

- 汇总真实账户和模拟盘的风险袖套、行业/风格暴露、集中度、重复暴露、现金用途和替代关系；
- 形成核心—卫星结构和新资金优先顺序；
- 回答“为什么这些资产应当放在同一个组合中”。

### R3｜Position Action Matrix & User Decision Pack

- 每个持仓必须归入：增持、持有、减持、退出、观察或等待证据；
- 明确建议仓位区间、价格条件、基本面条件、风险条件、优先级和不执行后果；
- 交付用户可直接审阅的《真实账户与模拟盘投资决策报告》；
- 只有用户明确选择后，才可建立独立状态变更Proposal。

### R4｜Operating Products

- 固化日报、周报、月报、季报和年度复盘；
- 只产品化现有能力，不继续扩张架构。

### R5｜Attribution & Calibration

- 完成个股、行业、仓位、时点、现金、Candidate及规则层归因；
- 解释模拟盘赚钱或亏钱的原因并形成规则升级建议。

### R6｜Production Acceptance

- 完整自然月实跑；
- 验收自动刷新、用户Delta、跨对话恢复、周期报告、故障重跑、证据追溯和零越权交易。

## 五、阶段门禁

- 未完成当前阶段的用户可读交付，不得进入下一阶段；
- 新阶段必须先在本Master Plan中出现并经用户明确同意；
- 临时缺陷修复归入当前阶段或横向控制，不另起字母轮次；
- R1完成前不进入R2；R3完成前不得宣称WP5完成；R6完成前不得宣称系统已生产化。

## 六、下一任务

`R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN`
'''
    write_text(master_plan_path, master_plan)

    matrix = f'''# 股票投资助手｜Capability Reality Matrix CURRENT

- 状态日期：{STATUS_DATE}
- 来源PR：`#{SOURCE_PR}`
- 状态：`CURRENT_IF_PRESENT_ON_MAIN`

| 能力 | 已有资产/能力 | 当前可用程度 | 关键缺口 | 正式完成阶段 |
|---|---|---|---|---|
| 权威规则与恢复 | 118条规则、19个Schema、Clean-Room与故障注入验收 | 高 | File Library仍非自动权威副本 | R0/R6 |
| 真实账户Current | 7个持仓、行情/NAV、用户Delta Ledger | 中高 | 无券商连接；自然月稳定性未验收 | R6 |
| 模拟盘Current | 16个持仓、成本、行情、现金 | 中高 | 尚无完整组合归因与统一动作矩阵 | R3/R5 |
| A股全市场范围 | 5,530只Canonical范围和行业Master | 高 | 数据源和长期运行仍需生产验收 | R6 |
| Candidate引擎 | 2 Core、38 Shadow、33 Research Queue；周/月/季框架 | 中 | 20/60/120日窗口不完整，0 Ready | R5/R6 |
| 公司研究 | Core2两只、P0三只较高等级研究 | 中 | 其余11只模拟盘及债基穿透不足 | R1 |
| 真实账户结构 | 债基、A股ETF、标普500袖套已识别 | 中 | 债基重叠和标普载体选择未完成 | R1/R2 |
| 组合构建 | 已有零散角色和风险判断 | 低 | 无统一风险预算、重复暴露和资金迁移方案 | R2 |
| 调仓决策 | 条件门禁和用户决策队列已建立 | 低 | 无覆盖全部持仓的用户决策包 | R3 |
| 周期运营 | 若干Schedule和Current刷新能力 | 低 | 尚未形成正式日/周/月/季/年产品 | R4/R6 |
| 收益归因 | Candidate Outcome框架和历史部分材料 | 低 | 无完整个股/行业/仓位/时点/现金归因 | R5 |
| 自动交易 | 永久不提供 | 不适用 | 用户始终保留最终决定和执行权 | 永久边界 |

## 当前可依赖的用途

- 恢复并保护真实账户、模拟盘和Candidate Current；
- 运行A股全市场基础筛选和研究优先级管理；
- 复用美的、长江电力、汇川技术、宁德时代和工业富联的现有研究；
- 识别组合重复暴露、角色倒置和证据缺口；
- 在证据或持仓连续性不足时Fail Closed。

## 当前不可依赖的用途

- 不能把系统视为已经完成的自动调仓工具；
- 不能认为Candidate已经证明Alpha；
- 不能要求系统对全部持仓给出同等质量的即时买卖结论；
- 不能认为日报、周报、月报和归因已经生产化；
- 不能从0 Ready推断“系统没有价值”，也不能为制造建议而降低门槛。
'''
    write_text(matrix_path, matrix)

    guide = f'''# 股票投资助手｜User Operating Guide CURRENT

- 状态日期：{STATUS_DATE}
- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 交易权限：`NONE`

## 一、现在可以怎样使用

### 1. 查询当前状态

可以直接要求：

- “汇总当前真实账户、模拟盘和Candidate状态。”
- “哪些持仓的行情或用户交易连续性已过期？”
- “当前哪些研究可以直接复用，哪些仍缺证据？”

系统应明确区分持仓水位、行情水位、基金净值水位和用户确认水位。

### 2. 分析已覆盖标的

可以直接要求更新或比较：

- 美的集团；
- 长江电力；
- 汇川技术；
- 宁德时代；
- 工业富联。

系统必须说明研究日期、价格水位、情景假设和未完成门禁。

### 3. 查看真实账户结构

可以要求系统解释：

- 三只债基的组合角色和待补证据；
- 两只标普500ETF为何属于一个风险袖套；
- A500核心与中证500卫星的当前关系；
- 为什么账户内现金只被视为执行性余额。

### 4. 查看Candidate

可以要求：

- Core、Shadow和Research Queue当前数量；
- 某只股票为何升级、降级或未准入；
- 哪些标的应优先进入R1研究覆盖。

Candidate是研究与生命周期产品，不等于立即买入清单。

## 二、用户需要提供什么

当真实账户或模拟盘发生变化时，用户需明确提供：

- 账户；
- 日期；
- 证券代码或现金项目；
- 买入、卖出、转换、费用、分红、转入或转出类型；
- 数量、价格、现金和费用税费。

如果没有变化，应明确确认零Delta及确认截止日期。系统不得从沉默推断无交易。

## 三、当前不应怎样使用

- 不应把系统当成券商或自动交易机器人；
- 不应要求在缺少新收盘、财报或持仓连续性时强制生成交易；
- 不应把Research Queue或Shadow Track直接理解为买入建议；
- 不应把单次Workflow绿色理解为完整产品已完成；
- 不应绕过Master Plan临时增加新的字母轮次。

## 四、R1–R6完成后可以期待什么

### R1完成后

全部当前持仓拥有统一研究、估值、组合角色、增减持和退出条件。

### R2完成后

系统能够解释真实账户和模拟盘的整体结构、风险来源、重复暴露和新资金顺序。

### R3完成后

用户获得一份可直接审阅的完整动作矩阵和投资决策报告；任何状态变化仍需用户明确批准。

### R4完成后

系统能够稳定生产日、周、月、季和年度投资运营产品。

### R5完成后

系统能够解释模拟盘为何赚钱或亏钱，并提出可验证的规则校准建议。

### R6完成后

系统经过完整自然月生产验收，可在新对话中恢复Current、连续运行、失败重跑并保持全部证据和权限边界。

## 五、当前唯一开发入口

R0经PR #{SOURCE_PR}合并并存在于main后，唯一允许的下一阶段为：

`R1｜Decision Coverage Completion`
'''
    write_text(guide_path, guide)

    wp5_contract = {
        "contract_id": "WP5_PORTFOLIO_DECISION_CONTRACT_V2_R0_FREEZE",
        "phase": "WP5_PORTFOLIO_DECISION_PHASE",
        "status": "PARTIALLY_COMPLETE_NO_USER_ACTION_PACK",
        "formal_plan": "WP5_1_TO_WP5_5",
        "source_pr": SOURCE_PR,
        "source_head_sha": source_head_sha,
        "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
        "authority_boundary": {
            "automatic_candidate_membership_mutation": False,
            "automatic_order_creation": False,
            "automatic_real_account_mutation": False,
            "automatic_simulation_mutation": False,
            "separate_user_approval_before_any_state_mutation": True,
            "trade_authority": TRADE_AUTHORITY,
        },
        "real_account_cash_policy": "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED_NO_FIXED_STRATEGIC_CASH_TARGET",
        "fixed_workstreams": {
            "WP5-1": {
                "name": "PORTFOLIO_BASELINE_AND_FULL_DIAGNOSTIC",
                "status": "COMPLETED",
                "evidence": ["PR_147_FULL_POSITION_REVIEW_7_REAL_16_SIMULATION"],
            },
            "WP5-2": {
                "name": "DECISION_GRADE_COVERAGE_COMPLETION",
                "status": "PARTIALLY_COMPLETE",
                "completed": ["CORE2_2", "P0_SIMULATION_3", "REAL_ACCOUNT_FIRST_PASS_7"],
                "remaining": ["SIMULATION_DECISION_GRADE_11", "BOND_FUND_FULL_LOOKTHROUGH_3", "SP500_SINGLE_VEHICLE_SELECTION", "A500_CSI500_ROLE_CONFIRMATION"],
            },
            "WP5-3": {"name": "PORTFOLIO_CONSTRUCTION_SYNTHESIS", "status": "NOT_STARTED"},
            "WP5-4": {"name": "POSITION_ACTION_MATRIX", "status": "NOT_STARTED"},
            "WP5-5": {"name": "USER_DECISION_AND_GOVERNED_IMPLEMENTATION", "status": "NOT_STARTED"},
        },
        "horizontal_controls": {
            "completed_close_gate": "INSTALLED_PR149",
            "user_position_continuity": "INSTALLED_PR150",
            "canonical_promotion_semantics_v2": "INSTALLED_PR151",
            "classification": "OPERATING_CONTROLS_NOT_SEPARATE_WP5_STAGES",
        },
        "historical_label_map": {
            "WP5-A": "WP5-1_START_AND_INPUT_FREEZE",
            "WP5-B": "WP5-1_FULL_POSITION_DIAGNOSTIC",
            "WP5-C": "WP5-2_P0_RESEARCH_PREPARATION",
            "WP5-D": "WP5-2_P0_RESEARCH_COMPLETION",
            "WP5-E": "HORIZONTAL_COMPLETED_CLOSE_ACTION_GATE",
            "WP5-F": "HORIZONTAL_POSITION_CONTINUITY_CONTROL",
            "WP5-G": "WP5-2_REAL_ACCOUNT_FIRST_PASS_AND_GOVERNANCE_REPAIR",
            "WP5-H": "VOID_NOT_STARTED",
        },
        "hard_gates": {
            "fresh_market_marks_at_decision_run": True,
            "position_delta_continuity_at_action_gate": True,
            "current_event_classification_before_action": True,
            "scenario_unit_scale_validation": True,
            "broker_or_user_verification_before_real_action": True,
            "complete_user_readable_action_pack_before_wp5_completion": True,
            "master_plan_update_and_user_approval_before_new_stage": True,
        },
        "completion_definition": {
            "all_current_positions_covered": True,
            "portfolio_construction_synthesis_delivered": True,
            "position_action_matrix_delivered": True,
            "user_decision_pack_delivered": True,
            "ready_for_user_decision_may_legitimately_be_zero": True,
            "orders_created": 0,
        },
        "next_task": "R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN",
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(wp5_contract_path, wp5_contract)

    execution.update(
        {
            "register_id": "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V6_R0_PRODUCT_AUTHORITY_FREEZE",
            "release_id": "INVESTMENT_OS_R16_20260727_R0_PRODUCT_AUTHORITY_FREEZE",
            "release_sequence": 16,
            "status_date": STATUS_DATE,
            "current_step": "R0_PRODUCT_AUTHORITY_FREEZE_CURRENT_IF_PRESENT_ON_MAIN",
            "overall_status": "PRODUCT_AUTHORITY_FROZEN_CURRENT_IF_PRESENT_ON_MAIN_DEVELOPMENT_PAUSED",
            "next_task": "R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN",
            "github_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "latest_governed_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "latest_completed_main_pr": LATEST_COMPLETED_MAIN_PR,
            "latest_completed_main_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "trade_authority": TRADE_AUTHORITY,
        }
    )
    execution["product_authority"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head_sha,
        "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
        "charter_path": str(charter_path.relative_to(root)),
        "master_plan_path": str(master_plan_path.relative_to(root)),
        "capability_matrix_path": str(matrix_path.relative_to(root)),
        "user_guide_path": str(guide_path.relative_to(root)),
        "file_library_role": "RECOVERY_DISTRIBUTION_ONLY_PENDING_EXPLICIT_PROMOTION",
        "conversation_memory_authority": "NONE",
    }
    execution["development_roadmap"] = {
        "R0": {"name": "PRODUCT_AUTHORITY_FREEZE", "status": "CURRENT_IF_PRESENT_ON_MAIN"},
        "R1": {"name": "DECISION_COVERAGE_COMPLETION", "status": "NOT_STARTED"},
        "R2": {"name": "PORTFOLIO_CONSTRUCTION_SYNTHESIS", "status": "NOT_STARTED"},
        "R3": {"name": "POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK", "status": "NOT_STARTED"},
        "R4": {"name": "OPERATING_PRODUCTS", "status": "NOT_STARTED"},
        "R5": {"name": "ATTRIBUTION_AND_CALIBRATION", "status": "NOT_STARTED"},
        "R6": {"name": "PRODUCTION_ACCEPTANCE", "status": "NOT_STARTED"},
    }
    execution["historical_wp5_label_map"] = wp5_contract["historical_label_map"]
    execution["wp5"] = {
        **execution.get("wp5", {}),
        "status": "PARTIALLY_COMPLETE_NO_USER_ACTION_PACK",
        "formal_plan": "WP5_1_TO_WP5_5",
        "source_pr": SOURCE_PR,
        "source_head_sha": source_head_sha,
        "historical_labels_deprecated_as_future_plan": True,
        "wp5_h_status": "VOID_NOT_STARTED",
        "decision_grade_coverage": {
            "simulation_total": 16,
            "simulation_higher_grade_complete": 5,
            "simulation_remaining": 11,
            "real_account_first_pass_complete": 7,
            "bond_fund_full_lookthrough_complete": False,
        },
        "portfolio_construction_synthesis_complete": False,
        "position_action_matrix_complete": False,
        "user_decision_pack_complete": False,
        "ready_for_user_decision_count": 0,
        "position_mutation_allowed": False,
        "order_execution_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(execution_path, execution)

    registry.update(
        {
            "registry_id": "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V10_R0_FREEZE",
            "registry_status": "R0_PRODUCT_AUTHORITY_FREEZE_CURRENT_IF_PRESENT_ON_MAIN",
            "status": "GITHUB_CURRENT_IF_PR152_MERGED_FILE_LIBRARY_RECOVERY_ONLY",
            "date": STATUS_DATE,
            "active_branch_candidate": None,
            "github_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "latest_governed_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "latest_completed_main_pr": LATEST_COMPLETED_MAIN_PR,
            "latest_completed_main_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
            "release_id": "INVESTMENT_OS_R16_20260727_R0_PRODUCT_AUTHORITY_FREEZE",
            "release_sequence": 16,
            "conversation_memory_authority": "NONE",
            "trade_authority": TRADE_AUTHORITY,
        }
    )

    for asset in registry.get("assets", []):
        if asset.get("asset_id") == "GITHUB_ACTIVE_RUNTIME":
            asset.update(
                {
                    "branch_candidate": SOURCE_BRANCH,
                    "latest_governed_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
                    "status": "GITHUB_MAIN_PR151_CURRENT_R0_AUTHORITY_FREEZE_CONDITIONAL",
                }
            )
        if asset.get("asset_id") in {"WP5_POSITION_CONTINUITY_CONTRACT", "WP5_POSITION_CONTINUITY_REQUEST_CURRENT"}:
            asset.update(
                {
                    "authority": "CANONICAL_CURRENT",
                    "merge_sha": "467280d54e4dbe58204e0137e4f9639550c72dca",
                    "status": "CURRENT",
                }
            )

    authority_assets = [
        ("INVESTMENT_ASSISTANT_PRODUCT_CHARTER_CURRENT", charter_path, "Top-level product mission, authority and completion contract", "MD"),
        ("WORK_PACKAGE_MASTER_PLAN_CURRENT", master_plan_path, "Only authorized development roadmap and stage gate", "MD"),
        ("CAPABILITY_REALITY_MATRIX_CURRENT", matrix_path, "User-facing capability, maturity and gap truth table", "MD"),
        ("USER_OPERATING_GUIDE_CURRENT", guide_path, "Current usage, required inputs, limitations and expected future products", "MD"),
        ("WP5_PORTFOLIO_DECISION_CONTRACT_V2", wp5_contract_path, "Finite WP5-1 to WP5-5 decision-phase contract", "JSON"),
        ("R0_PRODUCT_AUTHORITY_FREEZE_ACCEPTANCE", acceptance_path, "R0 authority, lineage and zero-mutation acceptance", "JSON"),
    ]
    for asset_id, path, role, fmt in authority_assets:
        upsert_asset(
            registry,
            {
                "asset_id": asset_id,
                "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
                "format": fmt,
                "location": str(path.relative_to(root)),
                "role": role,
                "source_pr": SOURCE_PR,
                "source_head_sha": source_head_sha,
                "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
                "status": "CURRENT_IF_PRESENT_ON_MAIN",
                "trade_authority": TRADE_AUTHORITY,
            },
        )
    write_json(registry_path, registry)

    acceptance = {
        "acceptance_id": "R0_PRODUCT_AUTHORITY_FREEZE_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head_sha,
        "latest_completed_main_pr": LATEST_COMPLETED_MAIN_PR,
        "latest_completed_main_merge_sha": LATEST_COMPLETED_MAIN_MERGE_SHA,
        "authority_products": [
            str(charter_path.relative_to(root)),
            str(master_plan_path.relative_to(root)),
            str(matrix_path.relative_to(root)),
            str(execution_path.relative_to(root)),
            str(guide_path.relative_to(root)),
        ],
        "control_products_updated": [
            str(registry_path.relative_to(root)),
            str(wp5_contract_path.relative_to(root)),
        ],
        "historical_pr_range_audited": "141-151",
        "historical_wp5_labels": "A-G_MAPPED_H_VOID_NOT_STARTED",
        "next_authorized_stage": "R1_DECISION_COVERAGE_COMPLETION",
        "new_research_records": 0,
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "legacy_decisions": 0,
            "orders": 0,
        },
        "protected_state_hashes": protected_hashes,
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(acceptance_path, acceptance)
    update_lineage_test(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
