from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "investment_os_runtime/00_CONTROL"
STATE = ROOT / "investment_os_runtime/30_STATE_CURRENT"

REAL_PATH = STATE / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM_PATH = STATE / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
CANDIDATE_PATH = STATE / "40_CANDIDATE/CANDIDATE_CURRENT.json"
LEGACY_DECISION_PATH = STATE / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"
R1_PACK_PATH = STATE / "30_RESEARCH/R1_DECISION_COVERAGE_PACK_CURRENT.json"
SYNTHESIS_PATH = STATE / "60_DECISIONS/R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT.json"
SUMMARY_PATH = STATE / "60_DECISIONS/R2_PORTFOLIO_CONSTRUCTION_SUMMARY_CURRENT.md"
ACCEPTANCE_PATH = CONTROL / "R2_PORTFOLIO_CONSTRUCTION_ACCEPTANCE_RECORD.json"
STATUS_PATH = CONTROL / "R2_STATUS_CURRENT.md"
EXECUTION_PATH = CONTROL / "EXECUTION_REGISTER_CURRENT.json"
CONTRACT_PATH = CONTROL / "WP5_PORTFOLIO_DECISION_CONTRACT.json"
REGISTRY_PATH = CONTROL / "AUTHORITATIVE_ASSET_REGISTRY.json"
MASTER_PATH = CONTROL / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"

R1_MERGE_SHA = "39cc98578ff0324bb6a5602db527b0dd3e70a278"
SOURCE_PR = 154
SOURCE_BRANCH = "agent/r2-portfolio-construction-synthesis"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r(value: float, n: int = 8) -> float:
    return round(float(value), n)


def position_map(account: dict) -> dict[str, dict]:
    return {row["security_id"]: row for row in account["holdings"]}


def group_stats(ids: list[str], positions: dict[str, dict], total_assets: float) -> dict:
    market_value = sum(float(positions[x]["market_value"]) for x in ids)
    pnl = sum(float(positions[x]["unrealized_pnl"]) for x in ids)
    return {
        "security_ids": ids,
        "market_value": r(market_value, 2),
        "weight": r(market_value / total_assets),
        "unrealized_pnl": r(pnl, 2),
    }


def stress_result(weights: dict[str, float], shocks: dict[str, float], total_assets: float) -> dict:
    portfolio_return = sum(weights[key] * shocks.get(key, 0.0) for key in weights)
    return {
        "illustrative_shocks": shocks,
        "portfolio_return": r(portfolio_return),
        "portfolio_pnl_rmb": r(portfolio_return * total_assets, 2),
        "forecast": False,
    }


def band_status(value: float, low: float, high: float) -> str:
    if value < low:
        return "BELOW_BAND"
    if value > high:
        return "ABOVE_BAND"
    return "WITHIN_BAND"


def normalize_master_plan(text: str) -> str:
    text = re.sub(
        r"- 最新已完成main合并：PR #\d+ / `[^`]+`",
        f"- 最新已完成main合并：PR #153 / `{R1_MERGE_SHA}`",
        text,
        count=1,
    )
    text = text.replace(
        "### R1｜Decision Coverage Completion\n\n- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#153`。",
        "### R1｜Decision Coverage Completion\n\n- 状态：`COMPLETED_ON_MAIN`；来源PR：`#153`。",
    )
    r2_heading = "### R2｜Portfolio Construction Synthesis"
    r2_status = "- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#154`。"
    if r2_heading in text:
        section_start = text.index(r2_heading)
        next_heading = text.find("### ", section_start + len(r2_heading))
        if next_heading == -1:
            next_heading = len(text)
        section = text[section_start:next_heading]
        section = re.sub(r"\n- 状态：`[^`]+`；来源PR：`#\d+`。\n", "\n", section)
        section = section.replace(r2_heading + "\n", r2_heading + "\n\n" + r2_status + "\n")
        text = text[:section_start] + section + text[next_heading:]
    text = text.replace(
        "`R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN`",
        "`R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN`",
    )
    marker = "## 九、R2验收结果"
    addition = f"""

{marker}

- 真实账户形成风险调整后的四袖套结构与三种情景；默认长期稳健成长参考架构为纯防御45%、混合增强债15%、A股25%、美股15%、战略现金0%。
- 模拟盘五类投资袖套均处于R2参考区间；当前问题集中在成长创新组和中证500Beta的负贡献，而非全组合权重失控。
- 建立单一持仓、主题簇、现金、A股核心—卫星及标普500单一载体约束。
- R2不生成R3逐仓动作矩阵，不改变持仓、Candidate、旧决策或订单。
"""
    if marker in text:
        text = text[: text.index(marker)].rstrip() + addition
    else:
        text = text.rstrip() + addition
    return text.rstrip() + "\n"


def main() -> None:
    real = load(REAL_PATH)
    sim = load(SIM_PATH)
    r1 = load(R1_PACK_PATH)
    real_positions = position_map(real)
    sim_positions = position_map(sim)
    real_total = float(real["summary"]["account_total_assets"])
    sim_total = float(sim["summary"]["account_total_assets"])

    protected_hashes = {
        "real_account_positions_sha256": sha256(REAL_PATH),
        "simulation_positions_sha256": sha256(SIM_PATH),
        "candidate_current_sha256": sha256(CANDIDATE_PATH),
        "legacy_decisions_sha256": sha256(LEGACY_DECISION_PATH),
    }

    real_groups = {
        "pure_defensive_fixed_income": group_stats(["017534.OF", "217003.OF"], real_positions, real_total),
        "hybrid_enhanced_bond": group_stats(["110017.OF"], real_positions, real_total),
        "a_share_core": group_stats(["159352.SZ"], real_positions, real_total),
        "a_share_midcap_satellite": group_stats(["510500.SH"], real_positions, real_total),
        "us_equity_sp500": group_stats(["159612.SZ", "159655.SZ"], real_positions, real_total),
        "execution_cash": {
            "market_value": r(float(real["summary"]["execution_cash_balance"]), 2),
            "weight": r(float(real["summary"]["execution_cash_balance"]) / real_total),
            "unrealized_pnl": 0.0,
        },
    }
    real_reference = {
        "mode": "BALANCED_STABLE_GROWTH_DEFAULT_FOR_R3_COMPARISON_NOT_USER_TARGET",
        "weights": {
            "pure_defensive_fixed_income": 0.45,
            "hybrid_enhanced_bond": 0.15,
            "a_share_core": 0.175,
            "a_share_midcap_satellite": 0.075,
            "us_equity_sp500": 0.15,
            "strategic_cash": 0.0,
        },
        "rationale": [
            "真实证券账户现金只作为执行余额，外部流动性不计入战略资产桶",
            "纯防御与混合增强债必须分开计量，避免把可转债和权益Beta误记为纯防御",
            "A500宽基核心必须不小于中证500卫星，规划偏好核心为卫星的1.25至2.0倍",
            "标普500只保留一个长期载体，R1条件性优先159655.SZ",
        ],
    }
    real_alternatives = {
        "capital_preservation": {
            "pure_defensive_fixed_income": 0.55,
            "hybrid_enhanced_bond": 0.15,
            "a_share_total": 0.20,
            "us_equity_sp500": 0.10,
            "strategic_cash": 0.0,
        },
        "balanced_stable_growth": {
            "pure_defensive_fixed_income": 0.45,
            "hybrid_enhanced_bond": 0.15,
            "a_share_total": 0.25,
            "us_equity_sp500": 0.15,
            "strategic_cash": 0.0,
        },
        "growth_tilt": {
            "pure_defensive_fixed_income": 0.35,
            "hybrid_enhanced_bond": 0.15,
            "a_share_total": 0.30,
            "us_equity_sp500": 0.20,
            "strategic_cash": 0.0,
        },
    }
    real_weights_for_stress = {key: value["weight"] for key, value in real_groups.items()}
    real_stress = {
        "equity_risk_off": stress_result(real_weights_for_stress, {
            "pure_defensive_fixed_income": 0.01,
            "hybrid_enhanced_bond": -0.05,
            "a_share_core": -0.18,
            "a_share_midcap_satellite": -0.23,
            "us_equity_sp500": -0.18,
            "execution_cash": 0.0,
        }, real_total),
        "rates_and_credit_shock": stress_result(real_weights_for_stress, {
            "pure_defensive_fixed_income": -0.04,
            "hybrid_enhanced_bond": -0.10,
            "a_share_core": -0.10,
            "a_share_midcap_satellite": -0.15,
            "us_equity_sp500": -0.10,
            "execution_cash": 0.0,
        }, real_total),
        "china_midcap_specific_shock": stress_result(real_weights_for_stress, {
            "pure_defensive_fixed_income": 0.0,
            "hybrid_enhanced_bond": -0.03,
            "a_share_core": -0.10,
            "a_share_midcap_satellite": -0.25,
            "us_equity_sp500": -0.05,
            "execution_cash": 0.0,
        }, real_total),
    }

    sim_bucket_ids = {
        "quality_core": ["000333.SZ", "600036.SH", "600660.SH", "600690.SH"],
        "defensive_dividend": ["600406.SH", "600900.SH", "600941.SH"],
        "growth_innovation": ["002463.SZ", "300124.SZ", "300750.SZ", "600276.SH", "601138.SH"],
        "cyclical_resource": ["600309.SH", "600938.SH", "601899.SH"],
        "benchmark_satellite": ["510500.SH"],
    }
    sim_bands = {
        "quality_core": [0.25, 0.35],
        "defensive_dividend": [0.15, 0.25],
        "growth_innovation": [0.12, 0.20],
        "cyclical_resource": [0.10, 0.18],
        "benchmark_satellite": [0.05, 0.10],
        "research_cash": [0.15, 0.25],
    }
    sim_groups = {}
    for key, ids in sim_bucket_ids.items():
        stats = group_stats(ids, sim_positions, sim_total)
        low, high = sim_bands[key]
        stats["reference_band"] = [low, high]
        stats["band_status"] = band_status(stats["weight"], low, high)
        sim_groups[key] = stats
    sim_cash = float(sim["summary"]["execution_cash_balance"]) / sim_total
    sim_groups["research_cash"] = {
        "market_value": r(float(sim["summary"]["execution_cash_balance"]), 2),
        "weight": r(sim_cash),
        "unrealized_pnl": 0.0,
        "reference_band": sim_bands["research_cash"],
        "band_status": band_status(sim_cash, *sim_bands["research_cash"]),
        "semantics": "SIMULATION_RESEARCH_AND_REPLACEMENT_RESERVE_NOT_FORCED_DEPLOYMENT",
    }
    sim_clusters = {
        "home_appliance_overlap": group_stats(["000333.SZ", "600690.SH"], sim_positions, sim_total),
        "dividend_cashflow_factor": group_stats(["600036.SH", "600900.SH", "600938.SH", "600941.SH"], sim_positions, sim_total),
        "ai_hardware": group_stats(["002463.SZ", "601138.SH"], sim_positions, sim_total),
        "electrification_automation": group_stats(["300124.SZ", "300750.SZ", "600406.SH"], sim_positions, sim_total),
        "commodity_cycle": group_stats(["600309.SH", "600938.SH", "601899.SH"], sim_positions, sim_total),
    }
    max_position = max(
        ({"security_id": sid, "weight": float(row["market_value"]) / sim_total} for sid, row in sim_positions.items()),
        key=lambda x: x["weight"],
    )
    sim_weights_for_stress = {key: value["weight"] for key, value in sim_groups.items()}
    sim_stress = {
        "broad_risk_off": stress_result(sim_weights_for_stress, {
            "quality_core": -0.15,
            "defensive_dividend": -0.08,
            "growth_innovation": -0.30,
            "cyclical_resource": -0.25,
            "benchmark_satellite": -0.22,
            "research_cash": 0.0,
        }, sim_total),
        "growth_reversal": stress_result(sim_weights_for_stress, {
            "quality_core": -0.05,
            "defensive_dividend": 0.0,
            "growth_innovation": -0.35,
            "cyclical_resource": -0.08,
            "benchmark_satellite": -0.12,
            "research_cash": 0.0,
        }, sim_total),
        "commodity_and_rate_shock": stress_result(sim_weights_for_stress, {
            "quality_core": -0.08,
            "defensive_dividend": -0.10,
            "growth_innovation": -0.10,
            "cyclical_resource": -0.25,
            "benchmark_satellite": -0.12,
            "research_cash": 0.0,
        }, sim_total),
    }

    synthesis = {
        "synthesis_id": "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_V1",
        "status": "PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_R3_NOT_STARTED",
        "as_of": "2026-07-27",
        "accepted_data_watermark": "2026-07-24_CLOSE",
        "position_continuity": "USER_CONFIRMED_THROUGH_2026_07_24_ONLY_NO_LATER_CONTINUITY_ASSUMED",
        "scope": "CURRENT_ACCEPTED_REAL_AND_SIMULATION_POSITIONS_ONLY",
        "r1_input_complete": {
            "simulation": r1["simulation"]["holding_count"],
            "real_products": r1["real_account"]["holding_count"],
        },
        "real_account": {
            "total_assets_rmb": r(real_total, 2),
            "cash_policy": real["cash_policy"],
            "risk_adjusted_current_structure": real_groups,
            "reference_architecture": real_reference,
            "alternative_architectures": real_alternatives,
            "structural_diagnosis": [
                "名义69.78%债基不能等同于69.78%纯防御；110017含权益与可转债增强Beta",
                "纯防御47.56%接近长期稳健成长默认参考，主要结构缺口来自混合增强债偏高",
                "A股总量接近参考下限，但A500核心7.78%小于中证500卫星13.21%",
                "标普500合计9.20%略低于默认参考且由两个经济重复载体组成",
                "证券账户现金只作为执行余额，不设置固定战略现金目标",
            ],
            "migration_direction_for_r3_not_orders": [
                "优先把标普500归并为单一载体159655.SZ，但须通过同日流动性和折溢价门禁",
                "通过新增资金或受控迁移使A500核心不小于中证500卫星，规划偏好1.25至2.0倍",
                "混合增强债110017的权益和转债Beta计入风险预算，不再与纯债等额替代",
                "纯防御仓不因名义债基总比例而机械大幅削减",
            ],
            "illustrative_stress_scenarios": real_stress,
        },
        "simulation": {
            "total_assets_rmb": r(sim_total, 2),
            "current_structure": sim_groups,
            "structural_diagnosis": [
                "五类投资袖套与研究现金全部处于R2参考区间，整体配置无需推倒重来",
                "质量核心、红利防御和周期资源合计产生正向未实现贡献，成长创新组和中证500Beta构成主要拖累",
                "当前问题是成长创新组内部标的质量与买入价格，而不是成长袖套总权重失控",
                "21.78%现金处于15%至25%研究储备区间，不构成强制买入信号",
            ],
            "current_unrealized_contribution_diagnostic_not_formal_r5_attribution": {
                key: value["unrealized_pnl"] for key, value in sim_groups.items()
            },
            "factor_and_overlap_clusters": sim_clusters,
            "guardrails": {
                "single_position_max": 0.10,
                "current_largest_position": {"security_id": max_position["security_id"], "weight": r(max_position["weight"])},
                "theme_cluster_max": 0.25,
                "dividend_cashflow_cluster": {
                    "weight": sim_clusters["dividend_cashflow_factor"]["weight"],
                    "status": "NEAR_CAP_NO_AUTOMATIC_ADD",
                },
                "growth_innovation_band": sim_bands["growth_innovation"],
                "research_cash_band": sim_bands["research_cash"],
                "benchmark_top_up": "ONLY_FOR_DELIBERATE_BETA_BUDGET_NOT_TO_FILL_CASH",
            },
            "capital_priority_waterfall_for_r3_not_orders": [
                "保留15%至25%研究现金，直到R3形成用户决策包",
                "高置信核心只有在最新收盘、持仓连续性、组合簇上限和15%Base收益门槛同时通过后才可进入增持候选",
                "沪电股份、汇川技术、宁德时代和工业富联组成的亏损成长子集在逻辑与现金流验证前不新增",
                "福耀玻璃已高于历史角色参考权重，不作为新增资金首选",
                "中证500ETF只在R2/R3明确需要中盘Beta时使用，不按历史10%标签自动补仓",
                "周期资源与医药卫星只在各自周期或商业化触发条件通过后使用",
            ],
            "illustrative_stress_scenarios": sim_stress,
        },
        "cross_account_findings": [
            "真实账户与模拟盘均持有510500.SH，经济上形成跨账户中盘Beta叠加；R3必须按账户用途分别处理",
            "真实账户强调防御与全球宽基，模拟盘承担个股研究和策略验证，不应简单复制同一资产配置",
            "近期盈亏仅用于诊断，不得替代R5正式收益归因或成为自动交易依据",
        ],
        "r3_required_outputs": [
            "真实账户按长期稳健成长默认情景形成逐产品保留、减持、迁移和新增条件矩阵",
            "明确三只债基各自的保留角色及110017混合Beta预算",
            "形成159612向159655条件性归并方案及执行门禁",
            "形成A500核心与中证500卫星纠偏路径",
            "模拟盘对16只持仓逐一形成增持、持有、减持、退出、观察或等待证据状态",
            "将现金部署顺序、替代标的和不执行后果呈现给用户选择",
        ],
        "stage_boundary": {
            "r2_complete": True,
            "r3_action_matrix_started": False,
            "user_decision_pack_ready": False,
            "implementation_ready_count": 0,
            "ready_for_user_decision_count": 0,
        },
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "legacy_decisions": 0,
            "orders": 0,
        },
        "trade_authority": "NONE",
    }
    write_json(SYNTHESIS_PATH, synthesis)

    summary = f"""# 股票投资助手｜R2 Portfolio Construction Synthesis CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#154`
- R1合并SHA：`{R1_MERGE_SHA}`
- 数据水位：`2026-07-24_CLOSE`
- R3动作矩阵：`NOT_STARTED`
- 交易权限：`NONE`

## 一、真实账户

风险调整后结构不是“69.78%纯债”，而是：

| 袖套 | 当前权重 | 默认长期稳健成长参考 |
|---|---:|---:|
| 纯防御固定收益 | {real_groups['pure_defensive_fixed_income']['weight']:.2%} | 45.0% |
| 混合增强债 | {real_groups['hybrid_enhanced_bond']['weight']:.2%} | 15.0% |
| A500宽基核心 | {real_groups['a_share_core']['weight']:.2%} | 17.5% |
| 中证500中盘卫星 | {real_groups['a_share_midcap_satellite']['weight']:.2%} | 7.5% |
| 标普500美股袖套 | {real_groups['us_equity_sp500']['weight']:.2%} | 15.0% |
| 执行现金 | {real_groups['execution_cash']['weight']:.2%} | 0%战略目标 |

结构方向：纯防御无需机械大幅削减；混合增强债偏高；A500核心与中证500卫星倒置；标普500应归并为单一载体159655.SZ。

## 二、模拟盘

| 袖套 | 当前权重 | R2区间 | 当前未实现贡献 |
|---|---:|---:|---:|
| 质量核心 | {sim_groups['quality_core']['weight']:.2%} | 25%–35% | ¥{sim_groups['quality_core']['unrealized_pnl']:,.2f} |
| 红利防御 | {sim_groups['defensive_dividend']['weight']:.2%} | 15%–25% | ¥{sim_groups['defensive_dividend']['unrealized_pnl']:,.2f} |
| 成长创新 | {sim_groups['growth_innovation']['weight']:.2%} | 12%–20% | ¥{sim_groups['growth_innovation']['unrealized_pnl']:,.2f} |
| 周期资源 | {sim_groups['cyclical_resource']['weight']:.2%} | 10%–18% | ¥{sim_groups['cyclical_resource']['unrealized_pnl']:,.2f} |
| 中证500基准卫星 | {sim_groups['benchmark_satellite']['weight']:.2%} | 5%–10% | ¥{sim_groups['benchmark_satellite']['unrealized_pnl']:,.2f} |
| 研究现金 | {sim_groups['research_cash']['weight']:.2%} | 15%–25% | — |

五类袖套和现金均处于区间。组合问题集中在成长创新组和中证500Beta的负贡献，因此R3应修复内部持仓，而不是整体推倒重来。

## 三、组合约束

- 单一模拟盘持仓上限：10%；当前最大为`{max_position['security_id']}`，权重{max_position['weight']:.2%}。
- 主题簇上限：25%；红利现金流簇当前{sim_clusters['dividend_cashflow_factor']['weight']:.2%}，已接近上限。
- 模拟盘现金保持15%–25%，在R3前不强制部署。
- 中证500ETF不按历史目标标签自动补仓。
- 真实账户A500核心必须不小于中证500卫星；标普500只保留一个长期载体。

## 四、阶段边界

R2完成组合架构、风险预算、重叠暴露、资金优先顺序和示例压力情景。R3尚未开始逐仓动作矩阵，因此本轮不产生交易建议、订单或持仓变化。
"""
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    acceptance = {
        "acceptance_id": "R2_PORTFOLIO_CONSTRUCTION_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "r1_merge_sha": R1_MERGE_SHA,
        "real_reference_architectures": 3,
        "simulation_sleeves": 6,
        "real_stress_scenarios": len(real_stress),
        "simulation_stress_scenarios": len(sim_stress),
        "portfolio_construction_synthesis_complete": True,
        "position_action_matrix_complete": False,
        "user_decision_pack_complete": False,
        "implementation_ready_count": 0,
        "ready_for_user_decision_count": 0,
        "next_authorized_stage": "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK",
        "protected_state_hashes": protected_hashes,
        "economic_mutations": synthesis["economic_mutations"],
        "trade_authority": "NONE",
    }
    write_json(ACCEPTANCE_PATH, acceptance)

    status = f"""# 股票投资助手｜R2 Portfolio Construction Synthesis CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#154`
- R1合并SHA：`{R1_MERGE_SHA}`
- 真实账户参考架构：`3`
- 模拟盘袖套：`6`
- R3动作矩阵：`NOT_STARTED`
- Ready for User Decision：`0`
- Implementation Ready：`0`
- 交易权限：`NONE`

R2只完成组合层综合，不改变任何真实账户、模拟盘、Candidate、旧决策或订单。唯一下一阶段为R3逐仓动作矩阵与用户决策包。
"""
    STATUS_PATH.write_text(status, encoding="utf-8")

    execution = load(EXECUTION_PATH)
    execution["current_step"] = "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_IF_PRESENT_ON_MAIN"
    execution["latest_completed_main_pr"] = 153
    execution["latest_completed_main_merge_sha"] = R1_MERGE_SHA
    execution["github_merge_sha"] = R1_MERGE_SHA
    execution["latest_governed_merge_sha"] = R1_MERGE_SHA
    execution["next_task"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    execution["overall_status"] = "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_R3_NOT_STARTED"
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V8_R2_PORTFOLIO_CONSTRUCTION"
    execution["release_id"] = "INVESTMENT_OS_R18_20260727_R2_PORTFOLIO_CONSTRUCTION"
    execution["release_sequence"] = 18
    execution.setdefault("r1_decision_coverage", {})["status"] = "COMPLETED_ON_MAIN"
    execution["r1_decision_coverage"]["merge_sha"] = R1_MERGE_SHA
    execution.setdefault("development_roadmap", {})["R1"] = {"status": "COMPLETED_ON_MAIN", "source_pr": 153, "merge_sha": R1_MERGE_SHA}
    execution["development_roadmap"]["R2"] = {"status": "CURRENT_IF_PRESENT_ON_MAIN", "source_pr": SOURCE_PR}
    execution["development_roadmap"]["R3"] = {"status": "NOT_STARTED"}
    wp5 = execution.setdefault("wp5", {})
    wp5["status"] = "PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_NO_ACTION_MATRIX"
    wp5["portfolio_construction_synthesis_complete"] = True
    wp5["position_action_matrix_complete"] = False
    wp5["user_decision_pack_complete"] = False
    wp5["r2_source_pr"] = SOURCE_PR
    wp5["ready_for_user_decision_count"] = 0
    wp5["implementation_ready_count"] = 0
    wp5["position_mutation_allowed"] = False
    wp5["order_execution_allowed"] = False
    execution["portfolio_r2"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "real_reference_architectures": 3,
        "simulation_sleeves": 6,
        "r3_started": False,
    }
    execution["trade_authority"] = "NONE"
    write_json(EXECUTION_PATH, execution)

    contract = load(CONTRACT_PATH)
    contract["contract_id"] = "WP5_PORTFOLIO_DECISION_CONTRACT_V2_R2_SYNTHESIS"
    workstreams = contract["fixed_workstreams"]
    workstreams["WP5-2"]["status"] = "COMPLETED_ON_MAIN"
    workstreams["WP5-3"]["status"] = "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    workstreams["WP5-3"]["remaining"] = []
    workstreams["WP5-3"]["deliverables"] = [
        "REAL_ACCOUNT_REFERENCE_ARCHITECTURES",
        "SIMULATION_SLEEVE_BUDGETS",
        "FACTOR_AND_OVERLAP_GUARDRAILS",
        "CAPITAL_PRIORITY_WATERFALL",
        "ILLUSTRATIVE_STRESS_SCENARIOS",
    ]
    workstreams["WP5-4"]["status"] = "NOT_STARTED"
    state = contract.setdefault("current_completion_state", {})
    state["all_current_positions_covered"] = True
    state["portfolio_construction_synthesis_delivered"] = True
    state["position_action_matrix_delivered"] = False
    state["user_decision_pack_delivered"] = False
    contract["current_stage"] = "WP5-3_COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    contract["next_stage"] = "WP5-4_POSITION_ACTION_MATRIX"
    contract["next_task"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    contract["status"] = "WP5_3_PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    contract["source_pr"] = SOURCE_PR
    contract["source_branch"] = SOURCE_BRANCH
    contract["source_head_sha"] = "GOVERNED_PR154_MATERIALIZATION"
    contract["trade_authority"] = "NONE"
    write_json(CONTRACT_PATH, contract)

    registry = load(REGISTRY_PATH)
    registry["active_branch_candidate"] = SOURCE_BRANCH
    registry["latest_completed_main_pr"] = 153
    registry["latest_completed_main_merge_sha"] = R1_MERGE_SHA
    registry["github_merge_sha"] = R1_MERGE_SHA
    registry["latest_governed_merge_sha"] = R1_MERGE_SHA
    registry["registry_status"] = "R2_PORTFOLIO_CONSTRUCTION_CURRENT_IF_PRESENT_ON_MAIN"
    registry["status"] = "GITHUB_CURRENT_IF_PR154_MERGED_R3_NOT_STARTED"
    registry["release_sequence"] = 18
    registry["release_id"] = "INVESTMENT_OS_R18_20260727_R2_PORTFOLIO_CONSTRUCTION"
    new_assets = [
        {
            "asset_id": "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(SYNTHESIS_PATH.relative_to(ROOT)),
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "role": "Real and Simulation portfolio construction synthesis",
            "source_pr": SOURCE_PR,
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "R2_PORTFOLIO_CONSTRUCTION_SUMMARY_CURRENT",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "MD",
            "location": str(SUMMARY_PATH.relative_to(ROOT)),
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "role": "Human-readable R2 portfolio construction product",
            "source_pr": SOURCE_PR,
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "R2_PORTFOLIO_CONSTRUCTION_ACCEPTANCE",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "JSON",
            "location": str(ACCEPTANCE_PATH.relative_to(ROOT)),
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "role": "R2 scope, lineage and zero-mutation acceptance",
            "source_pr": SOURCE_PR,
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": "NONE",
        },
        {
            "asset_id": "R2_STATUS_CURRENT",
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": "MD",
            "location": str(STATUS_PATH.relative_to(ROOT)),
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "role": "Human-readable R2 stage status",
            "source_pr": SOURCE_PR,
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": "NONE",
        },
    ]
    ids = {row["asset_id"] for row in new_assets}
    registry["assets"] = [row for row in registry["assets"] if row.get("asset_id") not in ids] + new_assets
    registry["trade_authority"] = "NONE"
    write_json(REGISTRY_PATH, registry)

    MASTER_PATH.write_text(normalize_master_plan(MASTER_PATH.read_text(encoding="utf-8")), encoding="utf-8")

    print({
        "real_reference_architectures": 3,
        "simulation_sleeves": 6,
        "r2_complete": True,
        "r3_started": False,
        "mutations": 0,
        "orders": 0,
    })


if __name__ == "__main__":
    main()
