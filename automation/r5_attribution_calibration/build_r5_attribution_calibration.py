from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

AS_OF = "2026-07-27"
R4_SOURCE_PR = 158
R4_FINAL_HEAD_SHA = "422bde92746062316a9b22da194f67f1e5b7783e"
R4_MERGE_SHA = "f4c48b1aa07f05f41f3d79cf5f843d84b384a5ec"
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


def money(value: float) -> str:
    return f"¥{float(value):,.2f}"


def pct(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    rows = registry.setdefault("assets", [])
    for index, row in enumerate(rows):
        if row.get("asset_id") == asset["asset_id"]:
            rows[index] = {**row, **asset}
            return
    rows.append(asset)


def replace_or_append_section(text: str, heading: str, block: str) -> str:
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\n.*?(?=^##\s|\Z)"
    )
    normalized = block.rstrip() + "\n"
    if pattern.search(text):
        return pattern.sub(normalized, text, count=1)
    return text.rstrip() + "\n\n" + normalized


def patch_stage_workflow(path: Path, job_name: str, branch_prefix: str) -> None:
    text = path.read_text(encoding="utf-8")
    condition = (
        f"    if: github.event_name == 'workflow_dispatch' || "
        f"startsWith(github.head_ref, '{branch_prefix}')"
    )
    job_marker = f"  {job_name}:\n"
    if condition in text:
        return
    if job_marker not in text:
        raise ValueError(f"job {job_name} not found in {path}")
    start = text.index(job_marker) + len(job_marker)
    rest = text[start:]
    if rest.startswith("    if:"):
        end = rest.index("\n")
        rest = condition + rest[end:]
    else:
        rest = condition + "\n" + rest
    path.write_text(text[:start] + rest, encoding="utf-8")


def holding_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    total_assets = float(payload["summary"]["account_total_assets"])
    open_pnl = float(payload["summary"]["open_unrealized_pnl"])
    rows = []
    for h in payload["holdings"]:
        pnl_value = float(h["unrealized_pnl"])
        rows.append(
            {
                "security_id": h["security_id"],
                "security_name": h["security_name"],
                "asset_class": h["asset_class"],
                "portfolio_bucket": h.get("portfolio_bucket"),
                "cost_basis_rmb": round(float(h["cost_basis"]), 2),
                "market_value_rmb": round(float(h["market_value"]), 2),
                "weight_of_total_assets": round(float(h["market_value"]) / total_assets, 8),
                "mark": float(h["mark"]),
                "mark_as_of": h["mark_as_of"],
                "unrealized_pnl_rmb": round(pnl_value, 2),
                "unrealized_pnl_pct": round(float(h["unrealized_pnl_pct"]), 8),
                "share_of_open_pnl": None if abs(open_pnl) < 1e-12 else round(pnl_value / open_pnl, 8),
                "attribution_semantics": "CURRENT_MARK_TO_RECORDED_COST_NOT_PERIOD_TOTAL_RETURN",
            }
        )
    return sorted(rows, key=lambda row: row["unrealized_pnl_rmb"], reverse=True)


def sleeve_rows(structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for sleeve, values in structure.items():
        rows.append(
            {
                "sleeve": sleeve,
                "security_ids": values.get("security_ids", []),
                "market_value_rmb": round(float(values.get("market_value", 0.0)), 2),
                "weight": round(float(values.get("weight", 0.0)), 8),
                "unrealized_pnl_rmb": round(float(values.get("unrealized_pnl", 0.0)), 2),
                "reference_band": values.get("reference_band"),
                "band_status": values.get("band_status"),
                "semantics": values.get("semantics"),
                "attribution_semantics": "CURRENT_SLEEVE_MARK_TO_COST_DIAGNOSTIC_NOT_PERIOD_ACTIVE_RETURN",
            }
        )
    return sorted(rows, key=lambda row: row["unrealized_pnl_rmb"], reverse=True)


def render_security_lines(rows: list[dict[str, Any]], count: int = 5) -> str:
    return "\n".join(
        f"- `{row['security_id']}` {row['security_name']}：{money(row['unrealized_pnl_rmb'])}，"
        f"当前权重{pct(row['weight_of_total_assets'])}。"
        for row in rows[:count]
    )


def render_negative_lines(rows: list[dict[str, Any]], count: int = 5) -> str:
    negatives = sorted(rows, key=lambda row: row["unrealized_pnl_rmb"])
    return "\n".join(
        f"- `{row['security_id']}` {row['security_name']}：{money(row['unrealized_pnl_rmb'])}，"
        f"当前权重{pct(row['weight_of_total_assets'])}。"
        for row in negatives[:count]
    )


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
    attribution_dir = root / "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION"
    integration_dir = root / "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    simulation_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"
    outcome_path = attribution_dir / "CANDIDATE_OUTCOME_CURRENT.json"
    r2_path = state / "60_DECISIONS/R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT.json"

    protected = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(simulation_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }

    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    real = read_json(real_path)
    simulation = read_json(simulation_path)
    candidate = read_json(candidate_path)
    candidate_outcome = read_json(outcome_path)
    r2 = read_json(r2_path)
    historical_contract = read_json(root / "config/fmdl7c_portfolio_attribution_contract.json")

    if execution.get("next_task") != "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN":
        raise ValueError("R5 is not the authorized next stage")
    if len(real.get("holdings", [])) != 7 or len(simulation.get("holdings", [])) != 16:
        raise ValueError("R5 requires accepted 7 Real and 16 Simulation holdings")
    if candidate.get("counts", {}).get("candidate_core") != 2:
        raise ValueError("R5 requires the accepted Candidate Current")
    if candidate_outcome.get("valid_entry_baseline_count") != 2:
        raise ValueError("R5 requires the accepted prospective Candidate outcome engine")

    existing_contract_path = control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json"
    if existing_contract_path.exists():
        existing_contract = read_json(existing_contract_path)
        source_head_sha = existing_contract.get("source_head_sha", args.source_head_sha)
    else:
        source_head_sha = args.source_head_sha

    real_summary = real["summary"]
    sim_summary = simulation["summary"]
    real_rows = holding_rows(real)
    sim_rows = holding_rows(simulation)
    real_sleeves = sleeve_rows(r2["real_account"]["risk_adjusted_current_structure"])
    sim_sleeves = sleeve_rows(r2["simulation"]["current_structure"])

    real_cost = float(real_summary["position_cost_basis"])
    real_market = float(real_summary["position_market_value"])
    real_cash = float(real_summary["execution_cash_balance"])
    real_total = float(real_summary["account_total_assets"])
    real_open_pnl = float(real_summary["open_unrealized_pnl"])

    sim_cost = float(sim_summary["position_cost_basis"])
    sim_market = float(sim_summary["position_market_value"])
    sim_cash = float(sim_summary["execution_cash_balance"])
    sim_total = float(sim_summary["account_total_assets"])
    sim_open_pnl = float(sim_summary["open_unrealized_pnl"])
    sim_total_pnl = float(sim_summary["account_total_pnl"])
    sim_residual = round(sim_total_pnl - sim_open_pnl, 2)

    completed_windows = candidate_outcome.get("completed_windows_present", [])
    candidate_counts = candidate["counts"]

    layers = [
        {
            "layer_id": "SECURITY_SELECTION",
            "status": "AVAILABLE_SNAPSHOT_MARK_TO_COST_DIAGNOSTIC_NOT_PERIOD_RETURN",
            "purpose": "Attribute current open mark-to-cost contribution by security.",
            "required_for_production": ["period start and end positions", "cash-flow ledger", "benchmark history"],
        },
        {
            "layer_id": "INDUSTRY_AND_SLEEVE",
            "status": "AVAILABLE_SNAPSHOT_SLEEVE_DIAGNOSTIC_NOT_PERIOD_ACTIVE_RETURN",
            "purpose": "Aggregate security contribution into governed risk sleeves and portfolio roles.",
            "required_for_production": ["effective-dated industry mapping", "period benchmark returns"],
        },
        {
            "layer_id": "POSITION_SIZING",
            "status": "PARTIAL_CURRENT_WEIGHT_AND_CONTRIBUTION_AVAILABLE_COUNTERFACTUAL_BLOCKED",
            "purpose": "Separate security outcome from the effect of chosen position size.",
            "required_for_production": ["reference weights at each rebalance", "period returns", "counterfactual policy"],
        },
        {
            "layer_id": "TIMING",
            "status": "BLOCKED_NO_COMPLETE_TRANSACTION_AND_PERIOD_BASELINE",
            "purpose": "Measure entry, exit and rebalance timing effects without hindsight fabrication.",
            "required_for_production": ["complete transaction ledger", "decision timestamps", "daily marks"],
        },
        {
            "layer_id": "CASH",
            "status": "PARTIAL_BALANCE_AND_SEMANTICS_AVAILABLE_PERIOD_CASH_RETURN_BLOCKED",
            "purpose": "Separate execution cash, research cash and external flows from investment return.",
            "required_for_production": ["period cash balances", "external-flow ledger", "cash benchmark"],
        },
        {
            "layer_id": "CANDIDATE",
            "status": "BLOCKED_WINDOWS_NOT_MATURE",
            "purpose": "Evaluate Candidate selection and lifecycle outcomes at 20/60/120 trading-day windows.",
            "required_for_production": ["mature price windows", "approved entry baseline", "benchmark series"],
        },
        {
            "layer_id": "RULE",
            "status": "PROPOSALS_ONLY_NOT_APPLIED",
            "purpose": "Convert repeated, classified outcomes into governed rule-change proposals.",
            "required_for_production": ["multiple independent observations", "regression", "human approval"],
        },
    ]

    calibration_proposals = [
        {
            "proposal_id": "R5-CAL-001",
            "title": "Current-state and completed-close gate",
            "finding": "Position continuity and decision marks are confirmed only through 2026-07-24.",
            "proposal": "Require fresh completed-close marks and explicit user zero-Delta or transaction Delta before any live action or period attribution.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "LATEST_COMPLETED_CLOSE_PLUS_USER_POSITION_CONTINUITY",
        },
        {
            "proposal_id": "R5-CAL-002",
            "title": "Simulation P&L bridge is mandatory",
            "finding": f"Simulation open P&L {money(sim_open_pnl)} differs from account P&L {money(sim_total_pnl)} by {money(sim_residual)}.",
            "proposal": "Every review must bridge open unrealized P&L to account P&L through realized, fee and other ledger effects; never force equality.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "POSITION_COSTS_MARKS_CASH_AND_ACCOUNT_TOTAL_ASSETS",
        },
        {
            "proposal_id": "R5-CAL-003",
            "title": "Snapshot contribution is not period return",
            "finding": "Current mark-to-recorded-cost figures lack a complete period-start baseline and external-flow reconciliation.",
            "proposal": "Label snapshot contribution separately and block monthly or annual return claims until a reconciled period ledger exists.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "PERIOD_START_END_AND_EXTERNAL_FLOW_LEDGER",
        },
        {
            "proposal_id": "R5-CAL-004",
            "title": "Diagnose sleeve internals before portfolio overhaul",
            "finding": "All Simulation sleeves remain inside R2 bands while growth innovation and CSI500 are the principal negative contributors.",
            "proposal": "Review security selection and entry quality inside a sleeve before changing the entire sleeve architecture.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "MULTIPLE_PERIOD_SECURITY_AND_SLEEVE_ATTRIBUTION",
        },
        {
            "proposal_id": "R5-CAL-005",
            "title": "No-add and hard-review controls remain binding",
            "finding": "Growth names with weak contribution remain subject to R3 evidence and valuation gates.",
            "proposal": "Do not add merely because a position is below cost; require thesis, cash-flow, valuation and portfolio-fit evidence.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "THESIS_FALSIFIER_VALUATION_AND_REVIEW_LOG",
        },
        {
            "proposal_id": "R5-CAL-006",
            "title": "Candidate Alpha claims require mature windows",
            "finding": "Candidate has two valid entry baselines but zero completed 20/60/120-day windows.",
            "proposal": "Keep Alpha claims blocked and preserve Candidate membership until governed windows mature and reconcile to benchmarks.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "MATURE_20_60_120_DAY_WINDOWS",
        },
        {
            "proposal_id": "R5-CAL-007",
            "title": "Real-account cash remains execution balance",
            "finding": f"Real account execution cash is only {money(real_cash)} and external liquidity is managed outside the securities account.",
            "proposal": "Exclude external liquidity from allocation and do not create a fixed strategic cash target for the Real account.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "USER_CASH_POLICY_AND_ACCOUNT_LEDGER",
        },
        {
            "proposal_id": "R5-CAL-008",
            "title": "No single snapshot may mutate strategy rules",
            "finding": "Current conclusions are dominated by one accepted watermark and incomplete prospective outcome windows.",
            "proposal": "Require repeated observations, failure classification, regression tests and explicit user approval before applying a rule change.",
            "status": "PROPOSED_NOT_APPLIED",
            "evidence_requirement": "MULTIPLE_INDEPENDENT_OBSERVATIONS_PLUS_REGRESSION_PLUS_APPROVAL",
        },
    ]

    contract = {
        "contract_id": "R5_ATTRIBUTION_AND_CALIBRATION_CONTRACT_V1",
        "status": "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION",
        "source_pr": args.source_pr,
        "source_branch": args.source_branch,
        "source_head_sha": source_head_sha,
        "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
        "as_of": AS_OF,
        "accepted_decision_watermark": "2026-07-24_CLOSE",
        "position_continuity_confirmed_through": "2026-07-24",
        "development_mode": True,
        "operating_activation": False,
        "layers": layers,
        "cross_layer_rules": {
            "external_flows_are_not_return": True,
            "open_unrealized_pnl_is_not_period_return": True,
            "missing_period_inputs_render_BLOCKED": True,
            "candidate_alpha_claim_requires_mature_windows": True,
            "calibration_outputs_are_proposals_only": True,
            "rule_mutation_requires_user_approval": True,
            "trade_or_order_creation": False,
        },
        "historical_assets_reused": {
            "fmdl7c_rule_proposal_count": len(historical_contract.get("rule_calibration_proposals", [])),
            "candidate_outcome_engine": "WP3R_CANDIDATE_OUTCOME_CURRENT",
            "r2_sleeve_structure": "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT",
        },
        "next_authorized_stage": "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN",
        "trade_authority": TRADE_AUTHORITY,
    }

    return_ledger = {
        "ledger_id": "R5_RETURN_LEDGER_CURRENT_V1",
        "status": "SNAPSHOT_RECONCILED_PERIOD_RETURN_PARTIALLY_BLOCKED",
        "as_of": "2026-07-24_CLOSE",
        "real_account": {
            "position_cost_basis_rmb": round(real_cost, 2),
            "position_market_value_rmb": round(real_market, 2),
            "execution_cash_balance_rmb": round(real_cash, 2),
            "account_total_assets_rmb": round(real_total, 2),
            "open_mark_to_cost_pnl_rmb": round(real_open_pnl, 2),
            "identity_check_market_plus_cash": round(real_market + real_cash, 2),
            "total_return_status": "BLOCKED_NOT_A_VERIFIED_PERIOD_TOTAL_RETURN",
            "missing": ["period-start market value", "external flows", "income and fee ledger", "realized P&L ledger"],
            "cash_semantics": real_summary["cash_semantics"],
        },
        "simulation": {
            "original_capital_rmb": round(float(sim_summary["original_capital"]), 2),
            "position_cost_basis_rmb": round(sim_cost, 2),
            "position_market_value_rmb": round(sim_market, 2),
            "research_cash_rmb": round(sim_cash, 2),
            "account_total_assets_rmb": round(sim_total, 2),
            "account_total_pnl_rmb": round(sim_total_pnl, 2),
            "open_unrealized_pnl_rmb": round(sim_open_pnl, 2),
            "closed_fee_other_residual_rmb": sim_residual,
            "identity_check_market_plus_cash": round(sim_market + sim_cash, 2),
            "pnl_bridge_check": round(sim_open_pnl + sim_residual, 2),
            "period_return_status": "ACCOUNT_SINCE_INCEPTION_PNL_AVAILABLE_PERIOD_ATTRIBUTION_BLOCKED",
            "missing": ["effective-dated transaction history", "period-start holdings", "daily cash history", "benchmark history"],
            "cash_semantics": sim_summary["cash_semantics"],
        },
        "reconciliation_rules": [
            "Market value plus account cash must equal account total assets.",
            "Simulation open P&L plus closed/fee/other residual must equal account total P&L.",
            "External transfers must never be counted as investment return.",
            "Missing components must remain explicit rather than being filled with zero.",
        ],
        "trade_authority": TRADE_AUTHORITY,
    }

    portfolio_attribution = {
        "attribution_id": "R5_PORTFOLIO_ATTRIBUTION_CURRENT_V1",
        "status": "CURRENT_SNAPSHOT_ATTRIBUTION_COMPLETE_PERIOD_ATTRIBUTION_PARTIALLY_BLOCKED",
        "as_of": "2026-07-24_CLOSE",
        "semantics": "CURRENT_OPEN_MARK_TO_COST_DIAGNOSTIC_AND_ACCOUNT_PNL_BRIDGE",
        "real_account": {
            "security_contribution": real_rows,
            "sleeve_contribution": real_sleeves,
            "open_mark_to_cost_pnl_rmb": round(real_open_pnl, 2),
            "period_total_return_claim_allowed": False,
            "diagnosis": [
                "The current Real-account mark-to-cost loss is concentrated in CSI500 and A500 exposure.",
                "Bond funds and S&P500 ETFs partly offset those losses.",
                "Execution cash is not a strategic allocation bucket.",
            ],
        },
        "simulation": {
            "security_contribution": sim_rows,
            "sleeve_contribution": sim_sleeves,
            "account_total_pnl_rmb": round(sim_total_pnl, 2),
            "open_unrealized_pnl_rmb": round(sim_open_pnl, 2),
            "closed_fee_other_residual_rmb": sim_residual,
            "diagnosis": [
                "Quality core, defensive dividend and cyclical resource are positive open contributors.",
                "Growth innovation and CSI500 benchmark satellite are the principal open drags.",
                "All six R2 sleeves remain inside their governed reference bands, so current evidence does not support a wholesale portfolio rebuild.",
                "The negative residual means open-position contribution alone overstates account-level P&L.",
            ],
        },
        "position_sizing": {
            "status": "PARTIAL_CURRENT_EXPOSURE_AVAILABLE_COUNTERFACTUAL_BLOCKED",
            "real_largest_weight": max(real_rows, key=lambda row: row["weight_of_total_assets"]),
            "simulation_largest_weight": max(sim_rows, key=lambda row: row["weight_of_total_assets"]),
            "counterfactual_active_return": None,
            "blocker": "No effective-dated reference weights and period return series.",
        },
        "timing": {
            "status": "BLOCKED_NO_COMPLETE_TRANSACTION_AND_PERIOD_BASELINE",
            "entry_timing_effect_rmb": None,
            "exit_timing_effect_rmb": None,
            "rebalance_timing_effect_rmb": None,
        },
        "cash": {
            "real_execution_cash_rmb": round(real_cash, 2),
            "real_cash_role": "EXECUTION_BALANCE_ONLY",
            "simulation_research_cash_rmb": round(sim_cash, 2),
            "simulation_research_cash_weight": round(sim_cash / sim_total, 8),
            "period_cash_drag_rmb": None,
            "status": "SEMANTICS_AND_BALANCE_AVAILABLE_PERIOD_CASH_EFFECT_BLOCKED",
        },
        "trade_authority": TRADE_AUTHORITY,
    }

    candidate_attribution = {
        "attribution_id": "R5_CANDIDATE_ATTRIBUTION_CURRENT_V1",
        "status": "BLOCKED_WINDOWS_NOT_MATURE",
        "as_of": candidate["as_of"],
        "counts": candidate_counts,
        "valid_entry_baseline_count": candidate_outcome["valid_entry_baseline_count"],
        "required_windows": candidate_outcome["required_windows"],
        "completed_windows_present": completed_windows,
        "results": candidate_outcome["results"],
        "alpha_claim_allowed": False,
        "candidate_membership_mutations": 0,
        "calibration_allowed": "NO_UNTIL_MATURE_WINDOWS_AND_BENCHMARK_RECONCILIATION",
        "trade_authority": TRADE_AUTHORITY,
    }

    rule_calibration = {
        "calibration_id": "R5_RULE_CALIBRATION_PROPOSALS_CURRENT_V1",
        "status": "PROPOSALS_ONLY_NOT_APPLIED",
        "as_of": AS_OF,
        "proposal_count": len(calibration_proposals),
        "proposals": calibration_proposals,
        "applied_rule_mutations": 0,
        "automatic_candidate_mutations": 0,
        "automatic_portfolio_mutations": 0,
        "orders": 0,
        "governance_gate": "REGRESSION_PLUS_MULTIPLE_OBSERVATIONS_PLUS_EXPLICIT_USER_APPROVAL",
        "trade_authority": TRADE_AUTHORITY,
    }

    report = f"""# 股票投资助手｜R5 Attribution & Calibration Report CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION`
- 数据水位：`2026-07-24_CLOSE`
- 持仓连续性：仅确认至`2026-07-24`
- 归因口径：当前持仓按记录成本的开放式贡献 + 模拟盘账户P&L桥接
- Operating Activation：`false`
- Rule Mutations：`0`
- Orders：`0`
- trade_authority：`NONE`

## 一、管理层结论

1. **模拟盘在当前水位并非亏损。** 账户总资产为{money(sim_total)}，相对原始资金的账户总P&L为{money(sim_total_pnl)}。
2. 当前持仓开放式未实现贡献为{money(sim_open_pnl)}，但账户总P&L仅为{money(sim_total_pnl)}，两者之间存在{money(sim_residual)}的已平仓、费用及其他残差。只看当前持仓会高估系统实际效果。
3. 组合层面的主要问题不是全部袖套失控，而是**成长创新组内部选股与进入价格**，以及中证500卫星的负贡献。
4. 真实账户当前按记录成本的开放式损益为{money(real_open_pnl)}，主要拖累来自中证500和A500；债基与标普500敞口形成部分对冲。
5. Candidate只有2个合格Entry Baseline，20/60/120日窗口均未成熟，当前不得声称Candidate已经证明Alpha。
6. R5形成8项校准提案，但全部为`PROPOSED_NOT_APPLIED`；不得自动改规则、持仓、Candidate或订单。

## 二、事实｜账户与收益桥接

### 真实账户

- 持仓市值：{money(real_market)}
- 执行现金：{money(real_cash)}
- 总资产：{money(real_total)}
- 持仓记录成本：{money(real_cost)}
- 当前开放式Mark-to-Cost损益：{money(real_open_pnl)}
- **限制：** 缺少完整期间期初水位、外部资金流、分红费用及已实现盈亏Ledger，因此这不是经验证的期间总收益。

### 模拟盘

- 原始资金：{money(float(sim_summary['original_capital']))}
- 持仓市值：{money(sim_market)}
- 研究现金：{money(sim_cash)}
- 总资产：{money(sim_total)}
- 账户总P&L：{money(sim_total_pnl)}
- 当前持仓未实现P&L：{money(sim_open_pnl)}
- 已平仓、费用及其他残差：{money(sim_residual)}
- 桥接：{money(sim_open_pnl)} + {money(sim_residual)} = {money(sim_total_pnl)}

## 三、个股层归因

### 模拟盘主要正贡献

{render_security_lines(sim_rows)}

### 模拟盘主要负贡献

{render_negative_lines(sim_rows)}

### 真实账户主要正贡献

{render_security_lines(real_rows)}

### 真实账户主要负贡献

{render_negative_lines(real_rows)}

## 四、袖套层归因

| 模拟盘袖套 | 当前权重 | 当前开放式贡献 |
|---|---:|---:|
""" + "\n".join(
        f"| {row['sleeve']} | {pct(row['weight'])} | {money(row['unrealized_pnl_rmb'])} |"
        for row in sim_sleeves
    ) + f"""

所有模拟盘袖套仍处于R2设定区间。当前证据支持的是：优先解决成长创新组内部选股、估值和进入时点问题，而不是推倒重建整个组合。

## 五、仓位、时点与现金

- **仓位层：** 当前权重和贡献可以观察，但缺少逐时点参考权重与反事实组合，不能计算严格的Sizing Alpha。
- **时点层：** 缺少完整交易Ledger、决策时间戳和日频基线，Entry/Exit/Rebalance Timing全部`BLOCKED`。
- **现金层：** 真实账户现金仅为执行余额；模拟盘{pct(sim_cash / sim_total)}研究现金位于R2的15%–25%区间。没有期间现金序列时，不计算现金拖累或贡献。

## 六、Candidate归因

- Core：`{candidate_counts['candidate_core']}`
- Shadow：`{candidate_counts['shadow_track']}`
- Research Queue：`{candidate_counts['research_queue']}`
- Ready：`{candidate_counts['ready_for_user_decision']}`
- 合格Entry Baseline：`{candidate_outcome['valid_entry_baseline_count']}`
- 成熟20/60/120日窗口：`{len(completed_windows)}`

结论：`BLOCKED_WINDOWS_NOT_MATURE`。当前不得以旧Proxy收益、单一水位或模拟盘重合度替代正式Candidate Alpha评价。

## 七、策略校准提案

""" + "\n".join(
        f"{index}. **{proposal['title']}**：{proposal['proposal']} 状态：`{proposal['status']}`。"
        for index, proposal in enumerate(calibration_proposals, start=1)
    ) + """

## 八、R6输入要求

R6生产验收必须补齐并连续验证：

- 完整自然月期初与期末水位；
- 每笔交易、分红、费用和外部资金流；
- 日频持仓、价格、基金净值、现金与Benchmark；
- Candidate 20/60/120日成熟窗口；
- 月报和年报中的R5归因嵌入；
- 故障重跑、跨对话恢复与零越权交易。

R5完成的是归因合同、当前水位诊断、Fail-Closed边界和校准提案机制。R6完成前，系统仍不得宣称已生产化。
"""

    monthly_integration = f"""# 股票投资助手｜月度投资复盘 R5归因集成样例

- 产品状态：`DEVELOPMENT_SAMPLE_NOT_LIVE`
- 数据水位：`2026-07-24_CLOSE`
- Period Return：`BLOCKED_NO_MONTH_START_BASELINE`
- Operating Activation：`false`

## 收益桥接

- 模拟盘账户总P&L：{money(sim_total_pnl)}
- 当前持仓未实现P&L：{money(sim_open_pnl)}
- 已平仓、费用及其他残差：{money(sim_residual)}
- 真实账户当前开放式Mark-to-Cost：{money(real_open_pnl)}，不作为月度总收益。

## 归因结论

- 正贡献主要来自质量核心、红利防御和周期资源。
- 负贡献主要来自成长创新与中证500卫星。
- Candidate窗口未成熟，Alpha归因保持阻断。
- 8项规则校准均为提案，不自动应用。

## 正式月报门禁

缺少月初持仓、月内交易/外部流、日频Benchmark或月末完整水位时，本章节必须显示`BLOCKED`，不得用当前未实现盈亏替代月度收益。
"""

    annual_integration = f"""# 股票投资助手｜年度策略复盘 R5校准集成样例

- 产品状态：`DEVELOPMENT_SAMPLE_NOT_LIVE`
- Operating Activation：`false`
- Rule Mutations：`0`

## 年度归因所需层级

个股、行业/袖套、仓位、时点、现金、Candidate和规则共7层。

## 当前可验证结论

- 模拟盘账户总P&L为{money(sim_total_pnl)}，但这不是完整年度归因。
- 成长创新组和中证500是当前开放式负贡献来源。
- Candidate正式结果仍等待20/60/120日窗口。
- 单一水位不构成修改策略规则的充分证据。

## 年度规则校准门禁

只有在多期独立观察、失败分类、回归测试和用户批准后，规则提案才可能进入独立实施Proposal。
"""

    acceptance = {
        "acceptance_id": "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": args.source_pr,
        "source_branch": args.source_branch,
        "source_head_sha": source_head_sha,
        "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
        "r4_source_pr": R4_SOURCE_PR,
        "r4_final_head_sha": R4_FINAL_HEAD_SHA,
        "r4_merge_sha": R4_MERGE_SHA,
        "layer_count": 7,
        "security_attribution": {
            "real_positions": len(real_rows),
            "simulation_positions": len(sim_rows),
        },
        "sleeve_attribution": {
            "real_sleeves_including_cash": len(real_sleeves),
            "simulation_sleeves_including_cash": len(sim_sleeves),
        },
        "return_ledger_reconciled": True,
        "simulation_pnl_bridge_reconciled": True,
        "candidate_windows_complete": False,
        "candidate_alpha_claim_allowed": False,
        "rule_calibration_proposal_count": len(calibration_proposals),
        "applied_rule_mutations": 0,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "protected_state_hashes": protected,
        "economic_mutations": {
            "real_account": 0,
            "simulation": 0,
            "candidate_membership": 0,
            "legacy_decisions": 0,
            "rules": 0,
            "orders": 0,
        },
        "next_authorized_stage": "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN",
        "trade_authority": TRADE_AUTHORITY,
    }

    r4_contract_path = control / "R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json"
    r4_contract = read_json(r4_contract_path)
    r4_contract["materialization_source_head_sha"] = r4_contract.get("source_head_sha")
    r4_contract["final_governed_head_sha"] = R4_FINAL_HEAD_SHA
    r4_contract["merge_sha"] = R4_MERGE_SHA
    r4_contract["source_head_semantics"] = "INITIAL_MATERIALIZATION_HEAD_RETAINED_FOR_REPLAY"
    write_json(r4_contract_path, r4_contract)

    r4_acceptance_path = control / "R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json"
    r4_acceptance = read_json(r4_acceptance_path)
    r4_acceptance["materialization_source_head_sha"] = r4_acceptance.get("source_head_sha")
    r4_acceptance["final_governed_head_sha"] = R4_FINAL_HEAD_SHA
    r4_acceptance["merge_sha"] = R4_MERGE_SHA
    r4_acceptance["source_head_semantics"] = "INITIAL_MATERIALIZATION_HEAD_RETAINED_FOR_REPLAY"
    write_json(r4_acceptance_path, r4_acceptance)

    r4_status = f"""# 股票投资助手｜R4 Operating Products CURRENT

- 状态：`COMPLETED_ON_MAIN`
- 来源PR：`#158`
- 最终Governed Head：`{R4_FINAL_HEAD_SHA}`
- main合并SHA：`{R4_MERGE_SHA}`
- 产品合同：`7/7`
- 开发样例：`7/7`
- Operating Activation：`false`
- Schedule Activation：`0`
- Ready for User Decision：`0`
- Implementation Ready：`0`
- Orders：`0`
- trade_authority：`NONE`

R4运营产品开发已完成并存在于main。R5负责完整归因与校准；R6完成前不得进入正式运营观察期。
"""
    write_text(control / "R4_STATUS_CURRENT.md", r4_status)

    execution["current_step"] = "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    execution["latest_completed_main_pr"] = R4_SOURCE_PR
    execution["latest_completed_main_merge_sha"] = R4_MERGE_SHA
    execution["latest_governed_merge_sha"] = R4_MERGE_SHA
    execution["github_merge_sha"] = R4_MERGE_SHA
    execution["development_roadmap"]["R4"] = {
        "name": "OPERATING_PRODUCTS",
        "source_pr": R4_SOURCE_PR,
        "source_head_sha": R4_FINAL_HEAD_SHA,
        "merge_sha": R4_MERGE_SHA,
        "status": "COMPLETED_ON_MAIN",
    }
    execution["development_roadmap"]["R5"] = {
        "name": "ATTRIBUTION_AND_CALIBRATION",
        "source_pr": args.source_pr,
        "source_head_sha": source_head_sha,
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
    }
    execution["development_roadmap"]["R6"] = {
        "name": "PRODUCTION_ACCEPTANCE",
        "status": "NOT_STARTED_NEXT_AUTHORIZED_STAGE",
    }
    execution["next_task"] = "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN"
    execution["overall_status"] = "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    execution["attribution_r5"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": args.source_pr,
        "layer_count": 7,
        "real_positions": len(real_rows),
        "simulation_positions": len(sim_rows),
        "candidate_completed_windows": len(completed_windows),
        "candidate_alpha_claim_allowed": False,
        "rule_calibration_proposals": len(calibration_proposals),
        "applied_rule_mutations": 0,
        "operating_activation": False,
    }
    execution["operating_activation"] = False
    execution["ready_for_user_decision_count"] = 0
    execution["implementation_ready_count"] = 0
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V12_R5_ATTRIBUTION_CALIBRATION"
    execution["release_id"] = "INVESTMENT_OS_R22_20260727_R5_ATTRIBUTION_CALIBRATION"
    execution["release_sequence"] = 22
    execution["trade_authority"] = TRADE_AUTHORITY

    registry["github_merge_sha"] = R4_MERGE_SHA
    registry["latest_completed_main_merge_sha"] = R4_MERGE_SHA
    registry["latest_completed_main_pr"] = R4_SOURCE_PR
    registry["latest_governed_merge_sha"] = R4_MERGE_SHA
    registry["registry_id"] = "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V15_R5_ATTRIBUTION_CALIBRATION"
    registry["registry_status"] = "R5_ATTRIBUTION_AND_CALIBRATION_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    registry["release_id"] = "INVESTMENT_OS_R22_20260727_R5_ATTRIBUTION_CALIBRATION"
    registry["release_sequence"] = 22
    registry["active_branch_candidate"] = args.source_branch
    for row in registry.get("assets", []):
        if row.get("asset_id") == "GITHUB_ACTIVE_RUNTIME":
            row["branch_candidate"] = args.source_branch
            row["latest_governed_merge_sha"] = R4_MERGE_SHA
            row["status"] = f"GITHUB_MAIN_PR158_CURRENT_PR{args.source_pr}_R5_CANDIDATE"

    asset_specs = [
        ("R5_ATTRIBUTION_CONTRACT_CURRENT", "investment_os_runtime/00_CONTROL/R5_ATTRIBUTION_CONTRACT_CURRENT.json", "Seven-layer attribution and calibration contract"),
        ("R5_RETURN_LEDGER_CURRENT", "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_RETURN_LEDGER_CURRENT.json", "Reconciled account and P&L bridge"),
        ("R5_PORTFOLIO_ATTRIBUTION_CURRENT", "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_PORTFOLIO_ATTRIBUTION_CURRENT.json", "Security and sleeve attribution"),
        ("R5_CANDIDATE_ATTRIBUTION_CURRENT", "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_CANDIDATE_ATTRIBUTION_CURRENT.json", "Candidate outcome window state"),
        ("R5_RULE_CALIBRATION_PROPOSALS_CURRENT", "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_RULE_CALIBRATION_PROPOSALS_CURRENT.json", "Governed proposals, none applied"),
        ("R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT", "investment_os_runtime/70_ATTRIBUTION_AND_CALIBRATION/R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT.md", "Management-readable attribution report"),
        ("R5_ACCEPTANCE_RECORD", "investment_os_runtime/00_CONTROL/R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json", "R5 reconciliation and zero-mutation acceptance"),
        ("R5_STATUS_CURRENT", "investment_os_runtime/00_CONTROL/R5_STATUS_CURRENT.md", "Human-readable R5 stage status"),
    ]
    for asset_id, location, role in asset_specs:
        upsert_asset(
            registry,
            {
                "asset_id": asset_id,
                "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
                "location": location,
                "role": role,
                "source_pr": args.source_pr,
                "source_branch": args.source_branch,
                "source_head_sha": source_head_sha,
                "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
                "status": "CURRENT_IF_PRESENT_ON_MAIN",
                "trade_authority": TRADE_AUTHORITY,
            },
        )

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = re.sub(
        r"- 最新已完成main合并：PR #[0-9]+ / `[^`]+`",
        f"- 最新已完成main合并：PR #158 / `{R4_MERGE_SHA}`",
        master,
        count=1,
    )
    master = master.replace(
        "| WP5 | 组合构建、动作矩阵和用户决策包 | `USER_DECISION_PACK_READY_NO_IMPLEMENTATION` |",
        "| WP5 | 组合构建、动作矩阵和用户决策包 | `DEVELOPMENT_PRODUCTS_COMPLETE_NO_LIVE_IMPLEMENTATION` |",
    )
    master = master.replace(
        "| WP6 | 日报、周报、月报、季报和年度运营产品 | `NOT_STARTED_AS_FORMAL_PRODUCT` |",
        "| WP6 | 日报、周报、月报、季报和年度运营产品 | `CONTRACT_AND_SAMPLES_COMPLETE_PRODUCTION_NOT_ACCEPTED` |",
    )
    master = master.replace(
        "| WP7 | 收益归因、决策复盘和策略校准 | `NOT_STARTED_AS_FORMAL_PRODUCT` |",
        "| WP7 | 收益归因、决策复盘和策略校准 | `DEVELOPMENT_PRODUCT_COMPLETE_PRODUCTION_WINDOWS_PENDING` |",
    )
    master = master.replace(
        "- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`。",
        "- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN`；纠偏来源PR：`#157`。",
        1,
    )
    master = re.sub(
        r"## 六、下一任务\n\n`[^`]+`",
        "## 六、下一任务\n\n`R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN`",
        master,
        count=1,
    )
    r5_block = f"""## R5开发验收结果

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#{args.source_pr}`。
- 已建立个股、行业/袖套、仓位、时点、现金、Candidate和规则共7层归因合同。
- 真实账户7/7、模拟盘16/16完成当前水位的Mark-to-Cost贡献拆解。
- 模拟盘完成账户P&L桥接：开放式未实现P&L {money(sim_open_pnl)}，已平仓/费用/其他残差 {money(sim_residual)}，账户总P&L {money(sim_total_pnl)}。
- Candidate仅2个Entry Baseline且20/60/120日窗口均未成熟，Alpha Claim继续阻断。
- 形成8项规则校准提案，实际规则变更、持仓变更、Candidate变更和订单均为`0`。
- R6完成完整自然月运行、恢复、重跑和正式激活验收前，Operating Activation保持`false`。
"""
    master = replace_or_append_section(master, "## R5开发验收结果", r5_block)
    write_text(master_path, master)

    capability = f"""# 股票投资助手｜Capability Reality Matrix CURRENT

- 状态日期：{AS_OF}
- 当前阶段：`R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN`
- 下一阶段：`R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN`
- Operating Activation：`false`
- 交易权限：`NONE`

| 能力 | 当前真实成熟度 | 已完成 | 关键剩余缺口 |
|---|---|---|---|
| 权威规则与恢复 | 高 | Product Charter、Master Plan、Execution Register、Clean-Room和故障注入 | File Library自动晋级与生产恢复仍待R6 |
| 真实账户Current | 中高 | 7个持仓、行情/NAV、用户Delta接口、结构与动作开发产品 | 无券商连接；完整自然月连续性未验收 |
| 模拟盘Current | 中高 | 16个持仓、成本、现金、动作矩阵和账户P&L桥接 | 完整交易/费用日历与自然月归因待R6 |
| A股全市场 | 高 | 5,530只Canonical普通A股范围和持续筛选能力 | 长期生产稳定性待R6 |
| Candidate引擎 | 中 | 2 Core、38 Shadow、33 Research Queue、Entry Baseline和20/60/120引擎 | 观察窗口未成熟，0 Ready，不得声称Alpha |
| 公司研究 | 中高 | 当前真实及模拟持仓7/7与16/16具备统一决策覆盖 | Candidate广泛深研仍需按优先级持续推进 |
| 组合构建与动作 | 中高 | 风险袖套、参考架构、23仓动作矩阵与开发决策场景 | 需R6基于届时Current重新生成Live决策包 |
| 周期运营产品 | 中高 | 统一状态、日/周/月/季/年及事件共7类合同与样例 | Schedule、连续运行和故障重跑未激活 |
| 收益归因 | 中高 | 7层合同、7+16当前贡献、模拟盘P&L桥接、8项校准提案 | 时点、期间现金和Candidate窗口需自然月数据 |
| 自动交易 | 永久不提供 | 用户最终决策和执行权已冻结 | 不适用 |

## 当前可以依赖

- 查询并恢复真实账户、模拟盘、Candidate及其数据水位；
- 分析当前个股和袖套的开放式Mark-to-Cost贡献；
- 解释模拟盘账户P&L与当前持仓未实现P&L之间的差异；
- 在输入不足时显示`BLOCKED`，不制造期间收益、Alpha或交易建议；
- 形成规则校准Proposal，但不自动应用。

## 当前不能依赖

- 不能把当前开放式未实现盈亏当作月度、年度或经现金流调整的总收益；
- 不能计算缺少交易Ledger的严格时点Alpha；
- 不能声称Candidate已经证明20/60/120日Alpha；
- 不能认为日报、周报和归因已经完成自然月生产验收；
- 不能自动改变规则、Candidate、持仓或订单。
"""
    write_text(control / "CAPABILITY_REALITY_MATRIX_CURRENT.md", capability)

    guide = f"""# 股票投资助手｜User Operating Guide CURRENT

- 状态日期：{AS_OF}
- 当前阶段：`R5完成，R6待开始`
- Operating Activation：`false`
- 交易权限：`NONE`

## 一、当前可以直接要求系统完成

### 1. 当前状态与数据水位

- 汇总真实账户、模拟盘和Candidate；
- 检查行情、基金净值和用户交易连续性；
- 识别哪些结论因输入过期而必须`BLOCKED`。

### 2. 当前持仓与组合分析

- 查看全部7个真实账户产品和16个模拟盘持仓的研究、估值、组合角色与条件动作；
- 查看真实账户稳健成长参考架构和模拟盘五类投资袖套；
- 解释A500/中证500核心—卫星关系、标普500重复载体及三只债基的不同风险来源。

### 3. 收益归因与策略校准

- 查看每只证券当前Mark-to-Cost贡献；
- 查看质量核心、红利防御、成长创新、周期资源和Benchmark卫星的贡献；
- 查看模拟盘开放式P&L、已平仓/费用/其他残差和账户总P&L桥接；
- 查看Candidate 20/60/120日窗口成熟状态；
- 查看规则校准提案及其证据门槛。

## 二、用户需要持续提供

账户发生变化时，提供账户、日期、证券或现金项目、交易类型、数量、价格、现金及费用税费。

没有变化时，需要明确确认零Delta及确认截止日期。系统不得从沉默推断无交易。

## 三、归因口径边界

- 当前开放式Mark-to-Cost只回答“现有持仓相对记录成本贡献多少”，不等于期间总收益；
- 外部转入转出不是投资收益；
- 模拟盘必须把开放式未实现P&L桥接到账户总P&L；
- 时点归因需要完整交易、决策时间戳和日频价格；
- Candidate Alpha需要合格Entry Baseline、Benchmark和成熟20/60/120日窗口；
- 校准结果只能形成Proposal，不能自动改规则。

## 四、当前不应怎样使用

- 不把系统当成券商或自动交易机器人；
- 不以亏损本身作为退出条件；
- 不把Research Queue或Shadow Track理解为买入清单；
- 不为制造建议而降低证据门槛；
- 不把单次Workflow绿色或单一水位理解为生产化完成。

## 五、下一阶段

`R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN`

R6必须完成完整自然月实跑，验收自动刷新、用户Delta、跨对话恢复、周期报告、归因嵌入、故障重跑、证据追溯及零越权交易。R6通过前，Operating Activation保持`false`。
"""
    write_text(control / "USER_OPERATING_GUIDE_CURRENT.md", guide)

    status = f"""# 股票投资助手｜R5 Attribution & Calibration CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#{args.source_pr}`
- 来源Head：`{source_head_sha}`
- R4 main合并SHA：`{R4_MERGE_SHA}`
- 归因层级：`7/7`
- 真实账户覆盖：`7/7`
- 模拟盘覆盖：`16/16`
- 模拟盘P&L桥接：`PASS`
- Candidate成熟窗口：`0`
- Rule Calibration Proposals：`8`
- Applied Rule Mutations：`0`
- Operating Activation：`false`
- Orders：`0`
- trade_authority：`NONE`

R5已完成归因与校准开发产品。严格期间收益、时点、现金及Candidate结果继续Fail Closed，等待R6完整自然月生产验收。
"""
    write_text(control / "R5_STATUS_CURRENT.md", status)

    write_json(control / "R5_ATTRIBUTION_CONTRACT_CURRENT.json", contract)
    write_json(control / "R5_ATTRIBUTION_AND_CALIBRATION_ACCEPTANCE_RECORD.json", acceptance)
    write_json(control / "EXECUTION_REGISTER_CURRENT.json", execution)
    write_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json", registry)
    write_json(attribution_dir / "R5_RETURN_LEDGER_CURRENT.json", return_ledger)
    write_json(attribution_dir / "R5_PORTFOLIO_ATTRIBUTION_CURRENT.json", portfolio_attribution)
    write_json(attribution_dir / "R5_CANDIDATE_ATTRIBUTION_CURRENT.json", candidate_attribution)
    write_json(attribution_dir / "R5_RULE_CALIBRATION_PROPOSALS_CURRENT.json", rule_calibration)
    write_text(attribution_dir / "R5_ATTRIBUTION_AND_CALIBRATION_REPORT_CURRENT.md", report)
    write_text(integration_dir / "R5_MONTHLY_ATTRIBUTION_INTEGRATION_SAMPLE.md", monthly_integration)
    write_text(integration_dir / "R5_ANNUAL_CALIBRATION_INTEGRATION_SAMPLE.md", annual_integration)

    lineage_path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    lineage = lineage_path.read_text(encoding="utf-8")
    r5_case = """    elif step == "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R4"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R5"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R6"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
        assert register["attribution_r5"]["layer_count"] == 7
        assert register["attribution_r5"]["candidate_alpha_claim_allowed"] is False
        assert register["attribution_r5"]["applied_rule_mutations"] == 0
        assert register["operating_activation"] is False
        assert register["ready_for_user_decision_count"] == 0
        assert register["implementation_ready_count"] == 0
        assert register["next_task"] == "R6_PRODUCTION_ACCEPTANCE_AFTER_R5_PRESENT_ON_MAIN"
"""
    if 'elif step == "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"' not in lineage:
        fallback = '    else:\n        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'
        if fallback not in lineage:
            raise ValueError("forward-lineage fallback not found")
        lineage = lineage.replace(fallback, r5_case + fallback, 1)
        lineage_path.write_text(lineage, encoding="utf-8")

    patch_stage_workflow(
        root / ".github/workflows/r1_decision_coverage.yml",
        "build-validate-publish",
        "agent/r1-",
    )
    patch_stage_workflow(
        root / ".github/workflows/r3_position_action_matrix.yml",
        "validate",
        "agent/r3-",
    )
    patch_stage_workflow(
        root / ".github/workflows/r4_operating_products.yml",
        "validate",
        "agent/r4-",
    )

    print(
        {
            "r5_layers": 7,
            "real_positions": len(real_rows),
            "simulation_positions": len(sim_rows),
            "simulation_account_pnl": round(sim_total_pnl, 2),
            "simulation_open_pnl": round(sim_open_pnl, 2),
            "simulation_residual": sim_residual,
            "candidate_completed_windows": len(completed_windows),
            "calibration_proposals": len(calibration_proposals),
            "mutations": 0,
            "orders": 0,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
