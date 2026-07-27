from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_PR = 158
SOURCE_BRANCH = "agent/r4-operating-products"
R3_CORRECTION_MERGE_SHA = "2fbcb84d7a23d5804975fd8319781464c2a18ab2"
AS_OF = "2026-07-27"
TRADE_AUTHORITY = "NONE"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def money(value: Any) -> str:
    try:
        return f"¥{float(value):,.2f}"
    except Exception:
        return "N/A"


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


def product(
    product_id: str,
    title: str,
    cadence: str,
    purpose: str,
    sections: list[str],
    required_inputs: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "title": title,
        "cadence": cadence,
        "purpose": purpose,
        "required_sections": sections,
        "required_inputs": required_inputs,
        "fail_closed_when": blockers,
        "development_sample_required": True,
        "operating_activation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    products_dir = root / "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES"
    decisions = state / "60_DECISIONS"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = decisions / "DECISION_PROPOSALS_CURRENT.json"
    protected = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }

    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    real = read_json(real_path)
    simulation = read_json(sim_path)
    r1 = read_json(state / "30_RESEARCH/R1_DECISION_COVERAGE_PACK_CURRENT.json")
    r2 = read_json(decisions / "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT.json")
    r3 = read_json(decisions / "R3_POSITION_ACTION_MATRIX_CURRENT.json")

    real_count = len(real.get("holdings", []))
    simulation_count = len(simulation.get("holdings", []))
    if real_count != 7 or simulation_count != 16:
        raise ValueError("R4 requires accepted R1-R3 holding coverage")
    if r3.get("development_mode") is not True or r3.get("operating_activation") is not False:
        raise ValueError("R3 development boundary is not accepted")
    if execution.get("next_task") != "R4_OPERATING_PRODUCTS_DEVELOPMENT":
        raise ValueError("R4 is not the authorized next stage")

    state_preservation = execution.get("state_preservation", {})
    candidate_counts = {
        "core": int(state_preservation.get("candidate_core", 2)),
        "shadow_track": int(state_preservation.get("candidate_shadow_track", 38)),
        "research_queue": int(state_preservation.get("candidate_research_queue", 33)),
        "ready_for_user_decision": int(state_preservation.get("candidate_ready_for_user_decision", 0)),
    }
    real_total = float(real.get("summary", {}).get("account_total_assets", 0.0))
    simulation_total = float(simulation.get("summary", {}).get("account_total_assets", 0.0))
    simulation_cash = float(simulation.get("summary", {}).get("cash", 0.0))
    simulation_pnl = float(simulation.get("summary", {}).get("total_unrealized_pnl", 0.0))

    common_inputs = [
        "REAL_ACCOUNT_POSITIONS_CURRENT",
        "SIMULATION_POSITIONS_CURRENT",
        "CANDIDATE_CURRENT",
        "latest completed-close equity marks",
        "latest available fund NAV",
        "explicit user position-delta continuity",
        "R1 decision coverage",
        "R2 portfolio construction synthesis",
        "R3 development action matrix",
    ]
    common_blocks = [
        "position continuity does not cover the report watermark",
        "required equity close or fund NAV is missing or stale",
        "Candidate snapshot is older than the stated report period",
        "a conclusion has no traceable evidence path",
        "the product would imply a trade or order without separate user approval",
    ]

    products = [
        product(
            "R4-STATUS",
            "统一运营状态页",
            "Whenever any upstream Current changes; no schedule is activated in R4",
            "Show authoritative watermarks, product readiness, blockers and the sole next operating step.",
            ["authority and watermark", "Real account status", "Simulation status", "Candidate status", "research and decision status", "blockers", "next step"],
            common_inputs,
            common_blocks,
        ),
        product(
            "R4-DAILY",
            "日度运营简报",
            "Development default: trading days 23:15 Asia/Shanghai after portfolio/NAV refresh",
            "Surface state changes, material events, abnormal moves, stale inputs and required follow-up without full attribution.",
            ["data watermark", "Real and Simulation snapshot", "material events", "Candidate changes", "risk and freshness alerts", "action gate", "next check"],
            common_inputs + ["same-day event evidence"],
            common_blocks,
        ),
        product(
            "R4-WEEKLY",
            "周度组合与候选池审查",
            "Development default: Saturday 09:30 Asia/Shanghai after Friday close and NAV completion",
            "Review sleeve drift, position exceptions, Candidate lifecycle changes and unresolved evidence gaps.",
            ["weekly market context", "portfolio sleeve review", "position exception list", "Candidate changes", "research progress", "risk register", "next-week priorities"],
            common_inputs + ["weekly benchmark marks"],
            common_blocks,
        ),
        product(
            "R4-MONTHLY",
            "月度投资复盘",
            "Development default: T+1 10:00 after month-end close, NAV and transaction continuity are complete",
            "Provide portfolio performance, structural drift, decision history and a clearly separated R5 attribution placeholder.",
            ["executive summary", "performance snapshot", "portfolio structure", "position review", "Candidate review", "decision log", "R5 attribution placeholder", "next-month plan"],
            common_inputs + ["month-start baseline", "month-end benchmark and FX marks"],
            common_blocks + ["month-start or month-end baseline is incomplete"],
        ),
        product(
            "R4-QUARTERLY",
            "季度组合与候选池重估",
            "Development default: after quarter-end portfolio/NAV close and required financial refresh; target T+5 10:00",
            "Re-underwrite portfolio roles, financial evidence, valuation ranges and Candidate promotions or removals.",
            ["quarter summary", "financial and valuation refresh", "portfolio construction review", "Candidate lifecycle review", "risk scenarios", "rule exceptions", "next-quarter agenda"],
            common_inputs + ["quarterly financial evidence", "valuation refresh"],
            common_blocks + ["required financial period evidence is incomplete"],
        ),
        product(
            "R4-ANNUAL",
            "年度策略复盘",
            "Development default: within the first ten trading days after year-end data completeness",
            "Review annual portfolio outcomes, research process, Candidate conversion and strategy governance; R5 supplies final attribution.",
            ["annual executive summary", "portfolio outcomes", "Candidate outcomes", "research quality", "decision governance", "R5 attribution integration", "strategy changes", "next-year priorities"],
            common_inputs + ["year-start baseline", "year-end marks", "complete annual decision history"],
            common_blocks + ["annual baseline or decision history is incomplete"],
        ),
        product(
            "R4-EVENT",
            "事件与异常警报",
            "On evidence ingest; development fallback is no more frequent than hourly when later activated",
            "Classify material company, portfolio, market and data-quality events and route them to the correct review gate.",
            ["severity", "event timestamp", "affected assets", "evidence", "thesis/valuation/portfolio impact", "required review", "prohibited actions"],
            common_inputs + ["event evidence with source timestamp"],
            common_blocks + ["event source or timestamp cannot be verified"],
        ),
    ]

    contract = {
        "contract_id": "R4_OPERATING_PRODUCT_CONTRACT_V1",
        "status": "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": str(args.source_head_sha),
        "as_of": AS_OF,
        "development_mode": True,
        "operating_activation": False,
        "timezone": "Asia/Shanghai",
        "product_count": len(products),
        "products": products,
        "cross_product_rules": {
            "single_authority": "EXECUTION_REGISTER_CURRENT and product-specific Current inputs",
            "no_silent_continuity_inference": True,
            "no_trade_or_order_creation": True,
            "development_samples_are_not_live_reports": True,
            "R5_owns_full_attribution": True,
            "R6_owns_activation_and_continuous_run_acceptance": True,
            "stale_or_missing_sections_must_render_BLOCKED_with_reason": True,
        },
        "trade_authority": TRADE_AUTHORITY,
    }

    blockers = [
        "R4 products are development samples; operating activation is false.",
        "R5 attribution and calibration are not complete.",
        "R6 production acceptance has not started.",
        "Position continuity is confirmed only through 2026-07-24.",
        "The accepted decision watermark is 2026-07-24_CLOSE and must be refreshed before any future live report.",
    ]
    unified = {
        "status_id": "R4_UNIFIED_OPERATING_STATUS_DEVELOPMENT_SAMPLE_V1",
        "status": "DEVELOPMENT_SAMPLE_READY_NOT_OPERATING",
        "as_of": AS_OF,
        "accepted_decision_watermark": "2026-07-24_CLOSE",
        "position_continuity_confirmed_through": "2026-07-24",
        "development_mode": True,
        "operating_activation": False,
        "real_account": {"holdings": real_count, "total_assets_rmb": round(real_total, 2)},
        "simulation": {"holdings": simulation_count, "total_assets_rmb": round(simulation_total, 2), "cash_rmb": round(simulation_cash, 2), "unrealized_pnl_rmb": round(simulation_pnl, 2)},
        "candidate": candidate_counts,
        "research_coverage": {"real_products": r1["real_account"]["holding_count"], "simulation_positions": r1["simulation"]["holding_count"]},
        "portfolio_construction": {"status": r2.get("status"), "real_reference_architectures": 3, "simulation_sleeves": 6},
        "r3_scenarios": {"count": int(r3.get("development_decision_scenario_count", 7)), "live_decisions": 0},
        "product_readiness": {row["product_id"]: "DEVELOPMENT_SAMPLE_READY_NOT_SCHEDULED" for row in products},
        "blockers": blockers,
        "next_stage": "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN",
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }

    header = f"""- 产品状态：`DEVELOPMENT_SAMPLE_NOT_LIVE`
- 样例日期：`{AS_OF}`
- 决策数据水位：`2026-07-24_CLOSE`
- 持仓连续性：仅确认至`2026-07-24`
- Operating Activation：`false`
- Orders：`0`
- trade_authority：`NONE`
"""

    daily = f"""# 股票投资助手｜日度运营简报（R4开发验收样例）

{header}
## 今日状态

- 真实账户：`{real_count}`个持仓，总资产约{money(real_total)}。
- 模拟盘：`{simulation_count}`个持仓，总资产约{money(simulation_total)}，研究现金约{money(simulation_cash)}。
- Candidate：Core `{candidate_counts['core']}`、Shadow `{candidate_counts['shadow_track']}`、Research Queue `{candidate_counts['research_queue']}`、Live Ready `{candidate_counts['ready_for_user_decision']}`。

## 风险与数据警报

- `BLOCKED_DATA_FRESHNESS`：当前样例决策水位仍为2026-07-24收盘。
- `BLOCKED_POSITION_CONTINUITY`：2026-07-24之后的真实账户和模拟盘交易Delta尚未确认。
- `NO_LIVE_ACTION`：R3的7项动作为开发场景，不构成今日调仓请求。

## 事件与异常

本样例不制造公司事件。正式产品只能呈现有时间戳和证据路径的真实事件；无法验证的事件必须显示`BLOCKED_EVIDENCE`。

## 下一步

继续R5开发；R6完成前不启用日报调度，也不生成订单。
"""

    weekly = f"""# 股票投资助手｜周度组合与候选池审查（R4开发验收样例）

{header}
## 组合结构

- 真实账户：R2已形成3套参考架构，R3动作矩阵仅用于开发验收。
- 模拟盘：6个风险袖套均已建立区间；当前开发结论是不整体推倒重来，重点监控成长创新子集的证据与估值门槛。

## 本周例外清单

- 沪电股份、汇川技术、宁德时代、工业富联：开发样例中维持停止新增或等待证据。
- 标普500双载体、A500与中证500核心—卫星关系：属于结构审查主题，不是当前执行指令。

## Candidate与研究进度

- Core `{candidate_counts['core']}`只；Shadow `{candidate_counts['shadow_track']}`只；Research Queue `{candidate_counts['research_queue']}`只。
- 20/60/120日Candidate效果窗口仍未完成，不得宣称策略Alpha。

## 下周优先级

1. R5建立收益归因与策略校准；
2. 保持持仓、Candidate和订单变更为0；
3. R6前不启动周报定时生产。
"""

    monthly = f"""# 股票投资助手｜月度投资复盘（R4开发验收样例）

{header}
## 执行摘要

R4证明月报可以统一呈现真实账户、模拟盘、Candidate、研究、组合结构和决策历史；当前不是完整自然月实跑结果。

## 组合快照

- 真实账户总资产约{money(real_total)}；现金继续仅作为执行余额。
- 模拟盘总资产约{money(simulation_total)}；当前未实现盈亏字段约{money(simulation_pnl)}，但本数值不是月度收益。
- Candidate Live Ready为`0`。

## 结构与决策

- R2组合结构产品已完成；R3有7项开发场景、0项Live Ready、0项Implementation Ready。
- 月报不得把开发样例动作转化为真实交易建议。

## 收益归因

`NOT_AVAILABLE_UNTIL_R5`：个股、行业、仓位、时点、现金和Candidate归因属于R5，不在R4伪造。

## 下月计划

完成R5归因与校准开发，再进入R6端到端生产验收。
"""

    quarterly = f"""# 股票投资助手｜季度组合与候选池重估（R4开发验收样例）

{header}
## 季度重估框架

1. 刷新季度财务、经营指标、治理与重大事件；
2. 重算估值区间与组合适配；
3. 复核真实账户风险袖套、模拟盘6袖套及重复暴露；
4. 对Candidate执行升级、降级、退出和研究优先级变更；
5. 所有变更仅形成受治理Proposal。

## 当前开发水位

- R1覆盖：真实产品`7/7`、模拟盘`16/16`。
- R2：组合构建综合完成。
- R3：动作矩阵开发产品完成，但Operating Activation为false。

## 阻断项

季度财务证据与最新完整收盘尚未为本样例刷新，因此所有估值和Candidate变更均为`BLOCKED_NOT_RUN`。
"""

    annual = f"""# 股票投资助手｜年度策略复盘（R4开发验收样例）

{header}
## 年度产品应回答的问题

- 真实账户和模拟盘全年表现如何；
- 收益来自选股、行业、仓位、时点、现金还是市场Beta；
- Candidate从研究到持仓的转化是否创造价值；
- 哪些决策规则有效，哪些规则需要废止或调整；
- 下一年度的风险预算、研究优先级和产品目标是什么。

## 当前可交付内容

R4已经固化年度产品结构、输入和Fail-Closed规则。

## 当前不可交付内容

`NOT_AVAILABLE_UNTIL_R5_AND_R6`：年度归因、完整决策历史和连续生产证据尚未完成，不能生成正式年度结论。
"""

    event_alert = f"""# 股票投资助手｜事件与异常警报（R4开发验收样例）

{header}
## Alert

- Alert ID：`R4-SAMPLE-DATA-FRESHNESS-001`
- Severity：`P1`
- 类型：`DATA_FRESHNESS_AND_POSITION_CONTINUITY`
- 影响范围：真实账户、模拟盘、R3动作矩阵及全部周期报告
- 证据：决策水位为2026-07-24收盘；持仓连续性仅确认至2026-07-24

## 影响判断

任何后续价格敏感结论、目标金额或实时动作均不得被标记为Current或Implementation Ready。

## 必需处理

在未来R6运营激活后，先刷新最新完整收盘和基金净值，再取得用户零Delta确认或交易Delta。

## 禁止事项

- 不得推断用户没有交易；
- 不得把盘中价当作收盘价；
- 不得创建订单；
- 不得将R3开发场景当成真实建议。
"""

    catalog_lines = [
        "# 股票投资助手｜R4 Operating Product Catalog CURRENT",
        "",
        "- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION`",
        "- 来源PR：`#158`",
        "- 时区：`Asia/Shanghai`",
        "- 产品数量：`7`",
        "- Operating Activation：`false`",
        "- 下一阶段：`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN`",
        "",
        "| 产品 | 开发默认节奏 | 核心职责 |",
        "|---|---|---|",
    ]
    for row in products:
        catalog_lines.append(f"| {row['title']} | {row['cadence']} | {row['purpose']} |")
    catalog_lines += [
        "",
        "## 产品边界",
        "",
        "- R4只定义产品、输入、输出、门禁和开发样例；不激活Schedule。",
        "- R5提供完整收益归因与策略校准。",
        "- R6完成连续运行、恢复、重跑和正式激活验收。",
        "- 任一关键输入过期时，产品必须显示`BLOCKED`及具体原因，不能用推测填充。",
    ]

    acceptance = {
        "acceptance_id": "R4_OPERATING_PRODUCTS_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": str(args.source_head_sha),
        "r3_correction_merge_sha": R3_CORRECTION_MERGE_SHA,
        "product_contract_complete": True,
        "product_count": len(products),
        "development_sample_count": 7,
        "products": [row["product_id"] for row in products],
        "unified_status_complete": True,
        "R5_attribution_started": False,
        "R6_production_acceptance_started": False,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "protected_state_hashes": protected,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0},
        "next_authorized_stage": "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN",
        "trade_authority": TRADE_AUTHORITY,
    }

    execution["current_step"] = "R4_OPERATING_PRODUCTS_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    execution["latest_completed_main_pr"] = 157
    execution["latest_completed_main_merge_sha"] = R3_CORRECTION_MERGE_SHA
    execution["latest_governed_merge_sha"] = R3_CORRECTION_MERGE_SHA
    execution["github_merge_sha"] = R3_CORRECTION_MERGE_SHA
    execution["development_roadmap"]["R3"] = {"status": "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN", "source_pr": 157, "merge_sha": R3_CORRECTION_MERGE_SHA}
    execution["development_roadmap"]["R4"] = {"name": "OPERATING_PRODUCTS", "status": "CURRENT_IF_PRESENT_ON_MAIN", "source_pr": SOURCE_PR}
    execution["development_roadmap"]["R5"]["status"] = "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
    execution["development_roadmap"]["R6"]["status"] = "NOT_STARTED"
    execution["next_task"] = "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN"
    execution["overall_status"] = "R4_OPERATING_PRODUCTS_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    execution["operating_products_r4"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "product_count": 7,
        "development_samples": 7,
        "unified_status": True,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "source_pr": SOURCE_PR,
    }
    execution["operating_activation"] = False
    execution["ready_for_user_decision_count"] = 0
    execution["implementation_ready_count"] = 0
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V11_R4_OPERATING_PRODUCTS"
    execution["release_id"] = "INVESTMENT_OS_R21_20260727_R4_OPERATING_PRODUCTS"
    execution["release_sequence"] = 21
    execution["trade_authority"] = TRADE_AUTHORITY

    registry["github_merge_sha"] = R3_CORRECTION_MERGE_SHA
    registry["latest_completed_main_merge_sha"] = R3_CORRECTION_MERGE_SHA
    registry["latest_completed_main_pr"] = 157
    registry["latest_governed_merge_sha"] = R3_CORRECTION_MERGE_SHA
    registry["registry_id"] = "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V14_R4_OPERATING_PRODUCTS"
    registry["registry_status"] = "R4_OPERATING_PRODUCTS_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    registry["release_id"] = "INVESTMENT_OS_R21_20260727_R4_OPERATING_PRODUCTS"
    registry["release_sequence"] = 21
    registry["active_branch_candidate"] = SOURCE_BRANCH
    for row in registry.get("assets", []):
        if row.get("asset_id") == "GITHUB_ACTIVE_RUNTIME":
            row["branch_candidate"] = SOURCE_BRANCH
            row["latest_governed_merge_sha"] = R3_CORRECTION_MERGE_SHA
            row["status"] = "GITHUB_MAIN_PR157_CURRENT_PR158_R4_CANDIDATE"
    asset_specs = [
        ("R4_OPERATING_PRODUCT_CONTRACT_CURRENT", "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json", "Seven-product operating contract"),
        ("R4_OPERATING_PRODUCT_CATALOG_CURRENT", "investment_os_runtime/50_OPERATING_PRODUCTS/R4_OPERATING_PRODUCT_CATALOG_CURRENT.md", "User-readable product catalog"),
        ("R4_UNIFIED_OPERATING_STATUS_SAMPLE", "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_UNIFIED_OPERATING_STATUS_SAMPLE.json", "Development unified status sample"),
        ("R4_OPERATING_PRODUCTS_ACCEPTANCE", "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json", "R4 scope, sample and zero-mutation acceptance"),
        ("R4_STATUS_CURRENT", "investment_os_runtime/00_CONTROL/R4_STATUS_CURRENT.md", "Human-readable R4 stage status"),
    ]
    for asset_id, location, role in asset_specs:
        upsert_asset(registry, {
            "asset_id": asset_id,
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "location": location,
            "role": role,
            "source_pr": SOURCE_PR,
            "source_branch": SOURCE_BRANCH,
            "source_head_sha": str(args.source_head_sha),
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": TRADE_AUTHORITY,
        })

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = master.replace("- 最新已完成main合并：PR #154 / `fc57e7a08fee6870130871e8491bb2db59b70e54`", f"- 最新已完成main合并：PR #157 / `{R3_CORRECTION_MERGE_SHA}`")
    master = master.replace("`R4_OPERATING_PRODUCTS_DEVELOPMENT`", "`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN`", 1)
    r4_marker = "## R4开发验收结果"
    r4_block = f"""## R4开发验收结果

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#158`。
- 已固化统一状态、日报、周报、月报、季报、年度复盘和事件警报共7类产品。
- 每类产品具备固定节奏、必填输入、必备章节、Fail-Closed规则和开发验收样例。
- R4不启动Schedule；Operating Activation为`false`。
- 收益归因仍由R5完成，连续运行和自动激活仍由R6验收。
- 真实账户、模拟盘、Candidate、旧决策和订单变更均为`0`。
"""
    master = append_once(master, r4_marker, r4_block)

    capability_path = control / "CAPABILITY_REALITY_MATRIX_CURRENT.md"
    capability = capability_path.read_text(encoding="utf-8")
    capability = append_once(capability, "## R4运营产品能力", """## R4运营产品能力

- 已完成7类运营产品的合同、模板、Fail-Closed规则和开发样例。
- 当前可以验证报告结构和输入依赖，但Schedule尚未激活。
- 完整收益归因需等待R5；连续自然月运行和生产激活需等待R6。
""")

    guide_path = control / "USER_OPERATING_GUIDE_CURRENT.md"
    guide = guide_path.read_text(encoding="utf-8")
    guide = append_once(guide, "## R4之后用户可以期待什么", """## R4之后用户可以期待什么

R4完成后，系统已经明确未来运营时应生产的统一状态页、日报、周报、月报、季报、年度复盘和事件警报。当前这些文件仍是开发样例，不会自动发送，也不会要求用户执行其中的动作。R5和R6完成后，系统才会基于届时Current生成正式运营产品。
""")

    status_text = f"""# 股票投资助手｜R4 Operating Products CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#158`
- R3纠偏合并SHA：`{R3_CORRECTION_MERGE_SHA}`
- 产品合同：`7/7`
- 开发样例：`7/7`
- Operating Activation：`false`
- Schedule Activation：`0`
- Ready for User Decision：`0`
- Implementation Ready：`0`
- Orders：`0`
- trade_authority：`NONE`

R4完成运营产品体系开发。唯一下一阶段是R5收益归因与策略校准开发；R6完成前不得进入正式运营观察期。
"""

    write_json(control / "R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json", contract)
    write_json(control / "R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json", acceptance)
    write_text(control / "R4_STATUS_CURRENT.md", status_text)
    write_json(control / "EXECUTION_REGISTER_CURRENT.json", execution)
    write_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json", registry)
    write_text(master_path, master)
    write_text(capability_path, capability)
    write_text(guide_path, guide)

    write_text(root / "investment_os_runtime/50_OPERATING_PRODUCTS/R4_OPERATING_PRODUCT_CATALOG_CURRENT.md", "\n".join(catalog_lines))
    write_json(products_dir / "R4_UNIFIED_OPERATING_STATUS_SAMPLE.json", unified)
    write_text(products_dir / "R4_DAILY_OPERATING_BRIEF_SAMPLE.md", daily)
    write_text(products_dir / "R4_WEEKLY_OPERATING_REVIEW_SAMPLE.md", weekly)
    write_text(products_dir / "R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md", monthly)
    write_text(products_dir / "R4_QUARTERLY_PORTFOLIO_REVIEW_SAMPLE.md", quarterly)
    write_text(products_dir / "R4_ANNUAL_STRATEGY_REVIEW_SAMPLE.md", annual)
    write_text(products_dir / "R4_EVENT_ALERT_SAMPLE.md", event_alert)

    print({
        "products": len(products),
        "development_samples": 7,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "R5_started": False,
        "R6_started": False,
        "mutations": 0,
        "orders": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
