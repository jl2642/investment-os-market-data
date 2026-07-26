#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(value: float, base: float) -> float:
    return round((value / base - 1.0) * 100.0, 2)


def implied_eps(price: float, pe: float) -> float:
    return round(price / pe, 4)


def build_security_record(
    security: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    market = security["current_market"]
    price = float(market["price_rmb"])
    source_records = [sources[source_id] for source_id in security["source_ids"]]
    source_facts = {
        source["source_id"]: source["facts"]
        for source in source_records
    }

    scenarios = []
    for scenario in security["valuation"]["scenarios"]:
        row = dict(scenario)
        expected = round(float(row["normalized_eps_rmb"]) * float(row["pe_multiple"]), 2)
        assert abs(expected - float(row["fair_value_rmb"])) < 0.011
        row["upside_downside_vs_current_pct"] = pct(float(row["fair_value_rmb"]), price)
        row["classification"] = "ASSUMPTION_SCENARIO_NOT_FORECAST"
        scenarios.append(row)

    cross_key = next(
        key for key in security["valuation"]
        if key.endswith("_cross_check")
    )
    cross_checks = []
    for item in security["valuation"][cross_key]:
        row = dict(item)
        row["upside_downside_vs_current_pct"] = pct(float(row["fair_value_rmb"]), price)
        row["classification"] = "ASSUMPTION_CROSS_CHECK_NOT_TARGET_PRICE"
        cross_checks.append(row)

    base = next(row for row in scenarios if row["name"] == "BASE")
    bear = next(row for row in scenarios if row["name"] == "BEAR")
    bull = next(row for row in scenarios if row["name"] == "BULL")

    deep_research = {
        "record_id": f"WP4-DR-{security['security_id']}",
        "security_id": security["security_id"],
        "security_name": security["security_name"],
        "benchmark": security["benchmark"],
        "portfolio_role": security["portfolio_role"],
        "research_scope": "ACCEPTED_CANDIDATE_CORE",
        "source_ids": security["source_ids"],
        "source_facts": source_facts,
        "current_market_facts": market,
        "thesis": security["thesis"],
        "falsifiers": security["falsifiers"],
        "catalysts": security["catalysts"],
        "fact_assumption_inference_boundary": {
            "facts": "SOURCE_REGISTER_AND_ACCEPTED_MARKET_BINDING_ONLY",
            "assumptions": "VALUATION_SCENARIOS_EXPLICITLY_LABELLED",
            "inferences": "PORTFOLIO_ROLE_AND_DECISION_STATUS",
            "unsupported_fill": "PROHIBITED"
        },
        "research_grade": security["decision_interface"]["research_grade"],
        "decision_grade_limitations": security["decision_interface"]["required_before_ready"],
        "ready_for_user_decision": False,
        "trade_authority": "NONE"
    }
    deep_research["semantic_hash"] = canonical_hash(deep_research)

    real_context = config["portfolio_context"]["real_account"]
    supplemental = config["portfolio_context"]["supplemental_2026_07_20_composition"]
    if security["security_id"] == "000333.SZ":
        fit_effects = [
            "INCREASES_DIRECT_CHINA_EQUITY_EXPOSURE",
            "ADDS_GLOBAL_CONSUMER_AND_INDUSTRIAL_PLATFORM_EXPOSURE",
            "CAN_ADD_CYCLICAL_AND_TRADE_POLICY_RISK",
            "NOT_A_REPLACEMENT_FOR_EXECUTION_CASH_OR_BOND_FUND_LIQUIDITY"
        ]
        alternative_review = [
            "COMPARE_WITH_EXISTING_BROAD_EQUITY_ETF_EXPOSURE",
            "COMPARE_WITH_HOME_APPLIANCE_INDEX_OR_HAIER_PEER",
            "DO_NOT_SIZE_WITHOUT_POSITION_LEVEL_CURRENT"
        ]
    else:
        fit_effects = [
            "ADDS_DEFENSIVE_INFRASTRUCTURE_EQUITY_AND_CASH_YIELD",
            "MAY_REDUCE_EQUITY_VOLATILITY_RELATIVE_TO_GROWTH_NAMES",
            "ADDS_HYDROLOGY_POLICY_RATE_AND_VALUATION_DURATION_RISK",
            "MUST_NOT_BE_CLASSIFIED_AS_A_BOND_SUBSTITUTE"
        ]
        alternative_review = [
            "COMPARE_WITH_PUBLIC_UTILITY_INDEX_EXPOSURE",
            "COMPARE_WITH_BOND_FUND_YIELD_DURATION_AND_LIQUIDITY",
            "DO_NOT_SIZE_WITHOUT_POSITION_LEVEL_CURRENT"
        ]

    portfolio_fit = {
        "record_id": f"WP4-PF-{security['security_id']}",
        "security_id": security["security_id"],
        "security_name": security["security_name"],
        "portfolio_role": security["portfolio_role"],
        "account_context": config["portfolio_context"],
        "fit_grade": "DIRECTIONAL_ROLE_GRADE_NOT_POSITION_SIZING_GRADE",
        "fit_effects": fit_effects,
        "alternative_and_overlap_review": alternative_review,
        "concentration_assessment": "BLOCKED_POSITION_LEVEL_CURRENT_NOT_AVAILABLE",
        "liquidity_assessment": "NO_ACCOUNT_LIQUIDITY_ACTION_PROPOSED",
        "portfolio_decision": "NO_ALLOCATION_OR_MIGRATION_PROPOSAL",
        "limitations": [
            real_context["limitation"],
            "BROKER_VERIFIED_FALSE",
            "REAL_ACCOUNT_POSITION_LEVEL_CURRENT_NOT_AVAILABLE_TO_WP4",
            f"SUPPLEMENTAL_COMPOSITION_{supplemental['status']}"
        ],
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE"
    }
    portfolio_fit["semantic_hash"] = canonical_hash(portfolio_fit)

    valuation = {
        "record_id": f"WP4-VAL-{security['security_id']}",
        "security_id": security["security_id"],
        "security_name": security["security_name"],
        "as_of": config["market_price_as_of"],
        "current_price_rmb": price,
        "current_pe_ttm": market["pe_ttm"],
        "implied_ttm_eps_rmb": implied_eps(price, float(market["pe_ttm"])),
        "method": security["valuation"]["method"],
        "scenarios": scenarios,
        "cross_check_type": cross_key,
        "cross_checks": cross_checks,
        "valuation_band_rmb": {
            "bear": bear["fair_value_rmb"],
            "base": base["fair_value_rmb"],
            "bull": bull["fair_value_rmb"]
        },
        "base_case_upside_downside_pct": base["upside_downside_vs_current_pct"],
        "valuation_grade": security["decision_interface"]["valuation_grade"],
        "valuation_not_forecast": True,
        "assumption_change_requires_new_proposal": True,
        "trade_authority": "NONE"
    }
    valuation["semantic_hash"] = canonical_hash(valuation)

    interface = {
        "record_id": f"WP4-DI-{security['security_id']}",
        "security_id": security["security_id"],
        "security_name": security["security_name"],
        "current_price_rmb": price,
        "valuation_band_rmb": valuation["valuation_band_rmb"],
        "base_case_upside_downside_pct": valuation["base_case_upside_downside_pct"],
        "research_grade": security["decision_interface"]["research_grade"],
        "valuation_grade": security["decision_interface"]["valuation_grade"],
        "portfolio_fit_grade": portfolio_fit["fit_grade"],
        "decision_status": security["decision_interface"]["decision_status"],
        "ready_for_user_decision": False,
        "buy_signal": "NO",
        "add_signal": "NO",
        "reduce_signal": "NO",
        "sell_signal": "NO",
        "required_before_ready": security["decision_interface"]["required_before_ready"],
        "reason_not_ready": [
            "BASE_CASE_MARGIN_OF_SAFETY_NOT_SUFFICIENT_FOR_FORMAL_READY_STATE",
            "POSITION_LEVEL_PORTFOLIO_CONTEXT_NOT_CURRENT_AND_BROKER_VERIFIED",
            "LISTED_SOURCE_AND_RESEARCH_GAPS_REMAIN_OPEN"
        ],
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "automatic_trade": False,
        "trade_authority": "NONE"
    }
    interface["semantic_hash"] = canonical_hash(interface)
    return deep_research, portfolio_fit, valuation, interface


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp4/config.json")
    parser.add_argument(
        "--output-dir",
        default=(
            "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP4/PROPOSALS/"
            "WP4_CORE2_DECISION_INTERFACE_20260726_V1"
        ),
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    output = root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    candidate_path = root / "investment_os_runtime/30_STATE_CURRENT/40_CANDIDATE/CANDIDATE_CURRENT.json"
    candidate = read_json(candidate_path)
    core_ids = sorted(row["security_id"] for row in candidate["candidate_core_members"])
    configured_ids = sorted(row["security_id"] for row in config["securities"])
    assert candidate["status"] == "ACCEPTED_ON_MAIN"
    assert core_ids == configured_ids == ["000333.SZ", "600900.SH"]
    assert candidate["counts"]["ready_for_user_decision"] == 0

    sources = {source["source_id"]: source for source in config["sources"]}
    source_register = {
        "register_id": "WP4_CORE2_SOURCE_REGISTER_20260726_V1",
        "as_of_date": config["as_of_date"],
        "source_hierarchy": [
            "OFFICIAL_REGULATORY_FILINGS",
            "OFFICIAL_ISSUER_INVESTOR_RELATIONS",
            "ACCEPTED_GITHUB_MARKET_AND_CANDIDATE_CURRENT"
        ],
        "sources": config["sources"],
        "source_count": len(config["sources"]),
        "unsupported_fact_fill": "PROHIBITED",
        "trade_authority": "NONE"
    }
    source_register["semantic_hash"] = canonical_hash(source_register)

    research_rows: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    valuation_rows: list[dict[str, Any]] = []
    interface_rows: list[dict[str, Any]] = []
    for security in config["securities"]:
        research, fit, valuation, interface = build_security_record(security, sources, config)
        research_rows.append(research)
        fit_rows.append(fit)
        valuation_rows.append(valuation)
        interface_rows.append(interface)

    write_json(output / "WP4_SOURCE_REGISTER.json", source_register)
    write_jsonl(output / "WP4_DEEP_RESEARCH_CORE2.jsonl", research_rows)
    write_jsonl(output / "WP4_PORTFOLIO_FIT_CORE2.jsonl", fit_rows)
    write_jsonl(output / "WP4_DECISION_GRADE_VALUATION_CORE2.jsonl", valuation_rows)
    write_jsonl(output / "WP4_DECISION_INTERFACE_CORE2.jsonl", interface_rows)

    queue_rows: list[dict[str, Any]] = []
    for interface in interface_rows:
        for priority, requirement in enumerate(interface["required_before_ready"], start=1):
            queue_rows.append(
                {
                    "security_id": interface["security_id"],
                    "security_name": interface["security_name"],
                    "priority_within_security": priority,
                    "requirement": requirement,
                    "route": "WP6_OPERATING_RESEARCH_QUEUE_OR_NEW_GOVERNED_PROPOSAL",
                    "automatic_promotion": False,
                    "trade_authority": "NONE"
                }
            )
    queue_path = output / "WP4_RESEARCH_GAP_AND_PRIORITY_QUEUE.csv"
    with queue_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(queue_rows[0]))
        writer.writeheader()
        writer.writerows(queue_rows)

    research_current = {
        "state_id": "WP4_CORE2_RESEARCH_CURRENT_20260726_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "promotion_rule": config["promotion_rule"],
        "as_of_date": config["as_of_date"],
        "scope": config["scope"],
        "records": research_rows,
        "record_count": len(research_rows),
        "full_decision_ready_count": 0,
        "unsupported_fact_fill": "PROHIBITED",
        "trade_authority": "NONE"
    }
    research_current["semantic_hash"] = canonical_hash(research_current)
    write_json(
        root / "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/WP4_CORE2_RESEARCH_CURRENT.json",
        research_current,
    )

    decision_current = {
        "state_id": "WP4_DECISION_INTERFACE_CURRENT_20260726_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "promotion_rule": config["promotion_rule"],
        "as_of_date": config["as_of_date"],
        "scope": config["scope"],
        "records": interface_rows,
        "record_count": len(interface_rows),
        "ready_for_user_decision_count": 0,
        "buy_signal_count": 0,
        "portfolio_or_account_action_count": 0,
        "automatic_trade": False,
        "trade_authority": "NONE"
    }
    decision_current["semantic_hash"] = canonical_hash(decision_current)
    write_json(
        root / "investment_os_runtime/30_STATE_CURRENT/50_DECISION_INTERFACE/WP4_DECISION_INTERFACE_CURRENT.json",
        decision_current,
    )

    acceptance = {
        "acceptance_id": "WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_20260726_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "promotion_rule": config["promotion_rule"],
        "milestone_id": config["milestone_id"],
        "scope": config["scope"],
        "completion_rule": config["completion_rule"],
        "core_security_ids": configured_ids,
        "deep_research_records": 2,
        "portfolio_fit_records": 2,
        "decision_grade_valuation_records": 2,
        "decision_interface_records": 2,
        "ready_for_user_decision": 0,
        "research_queue_or_shadow_membership_mutations": 0,
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "next_gate": "WP5_PORTFOLIO_MIGRATION_AND_ACTION_REVIEW_WITH_ZERO_READY_DECISIONS"
    }
    write_json(
        root / "investment_os_runtime/00_CONTROL/WP4_CORE2_DECISION_INTERFACE_ACCEPTANCE_RECORD.json",
        acceptance,
    )

    register_path = root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"
    register = read_json(register_path)
    register.update(
        {
            "register_id": "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V4_WP4_CORE2",
            "status_date": "2026-07-26",
            "overall_status": "WP4_CORE2_COMPLETED_CURRENT_IF_PRESENT_ON_MAIN_WP5_READY",
            "current_step": "WP5_PORTFOLIO_MIGRATION_AND_ACTION_REVIEW",
            "next_task": "RUN_WP5_PORTFOLIO_MIGRATION_AND_ACTION_REVIEW_WITH_ZERO_READY_DECISIONS",
            "trade_authority": "NONE"
        }
    )
    register["wp4"] = {
        "status": "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN",
        "promotion_rule": config["promotion_rule"],
        "milestone_id": config["milestone_id"],
        "scope": config["scope"],
        "core_members": configured_ids,
        "deep_research_records": 2,
        "portfolio_fit_records": 2,
        "decision_grade_valuation_records": 2,
        "decision_interface_records": 2,
        "ready_for_user_decision": 0,
        "candidate_membership_mutations": 0,
        "real_account_mutations": 0,
        "simulation_trade_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "next_gate": acceptance["next_gate"]
    }
    write_json(register_path, register)

    master_plan = """# 股票投资助手｜Work Package Master Plan CURRENT

- 状态日期：2026-07-26
- Canonical状态源：`investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json`
- WP4晋级规则：仅当本文件及WP4资产经受治理PR合并进入`main`后生效
- File Library晋级：`PENDING_MANUAL_UPLOAD`
- 交易权限：`NONE`

## 当前阶段

| Work Package | 状态 | 当前结论 |
|---|---|---|
| WP1 | COMPLETED | Canonical、规则、Runtime与Clean-Room验收完成 |
| WP2 | COMPLETED | 账户、模拟盘、历史Candidate与市场诊断完成 |
| WP3 | COMPLETED / ACCEPTED ON MAIN | 2只Core、38只Shadow、33只Research Queue、0只Ready |
| WP4 | COMPLETED IF PRESENT ON MAIN | 美的集团、长江电力完成深研、组合适配、显式情景估值与Decision Interface；0只Ready |
| WP5 | READY AFTER WP4 MERGE | 在0只Ready前提下执行组合迁移和Action Review，允许结论为NO ACTION |
| WP6–WP7 | PLANNED | 周期运营、归因复盘和真实试点 |

## WP4集中里程碑

WP4仅覆盖已经接受的Candidate Core。Shadow Track和Research Queue继续保留研究队列身份，不因WP4自动晋级。

- 美的集团：2025年收入和利润创历史高位，但2026年一季度收入、归母利润增长放缓且扣非利润下降；估值情景明确区分事实与假设，当前结论为`WATCH_FOR_EVIDENCE_AND_PRICE`。
- 长江电力：2026年上半年总发电量增长，但来水结构分化，一季度利润增长包含金融资产浮盈影响；当前结论为`HOLD_FOR_EVIDENCE_OR_BETTER_ENTRY`。
- 两只标的均形成Decision-grade assumption-explicit valuation，但因安全边际、来源缺口及缺少可用于仓位设计的Position-level Current，Ready for User Decision仍为0。
- 没有生成BUY / ADD / REDUCE / SELL，没有真实账户、模拟盘或订单变更。

## 下一里程碑

`WP5 | Portfolio Migration and Action Review`

WP5必须接受“0只Ready → NO ACTION”作为合法结果，不得为了产生交易建议而降低门槛。任何Candidate、模拟盘或真实账户状态变化仍须独立受治理Proposal；系统不自动交易。
"""
    (root / "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md").write_text(
        master_plan, encoding="utf-8"
    )

    executive = """# WP4｜Core2 Deep Research、Portfolio Fit、Decision-grade Valuation与Decision Interface

## 结论

WP4以一个集中里程碑覆盖全部已接受Candidate Core：美的集团与长江电力。两只标的均完成来源注册、事实/假设/推断分层、组合角色分析、显式情景估值和Decision Interface。

- 美的集团：2026年一季度收入和归母利润增长放缓，扣非利润下降；当前价格接近Base情景与6.5% FCF收益率交叉验证值，安全边际不足以进入Ready。
- 长江电力：2026年上半年六座梯级电站发电量增长4.81%，但来水结构显著分化；当前价格接近Base情景和3.5%股息率交叉验证值，防御质量较强但估值补偿有限。

## 决策接口

| 标的 | 决策状态 | Ready | 交易信号 |
|---|---|---:|---|
| 美的集团 | WATCH_FOR_EVIDENCE_AND_PRICE | 否 | NO |
| 长江电力 | HOLD_FOR_EVIDENCE_OR_BETTER_ENTRY | 否 | NO |

两只标的的研究与估值可以支持明确的等待结论，但不能支持仓位设计或交易建议。真实账户Position-level Current不可用且`broker_verified=false`，因此Portfolio Fit仅达到方向性角色级，不能达到Position Sizing级。

## 权限边界

- Candidate membership mutations：0
- Real-account mutations：0
- Simulation-trade mutations：0
- Orders：0
- trade_authority：NONE

WP4完成不等于必须产生买入建议。当前正式结果是：研究完成、估值可审计、决策接口明确、0只Ready、0项交易行动。
"""
    (output / "WP4_EXECUTIVE_REVIEW.md").write_text(executive, encoding="utf-8")

    generated_files = sorted(path for path in output.iterdir() if path.is_file())
    manifest = {
        "manifest_id": "WP4_CORE2_DECISION_INTERFACE_MANIFEST_20260726_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "promotion_rule": config["promotion_rule"],
        "milestone_id": config["milestone_id"],
        "as_of_date": config["as_of_date"],
        "scope": config["scope"],
        "metrics": {
            "source_count": len(config["sources"]),
            "core_security_count": 2,
            "deep_research_records": 2,
            "portfolio_fit_records": 2,
            "decision_grade_valuation_records": 2,
            "decision_interface_records": 2,
            "priority_queue_rows": len(queue_rows),
            "ready_for_user_decision": 0,
            "buy_signals": 0,
            "candidate_membership_mutations": 0,
            "real_account_mutations": 0,
            "simulation_trade_mutations": 0,
            "orders": 0
        },
        "files": {
            path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
            for path in generated_files
        },
        "trade_authority": "NONE"
    }
    write_json(output / "WP4_MANIFEST.json", manifest)

    print(
        json.dumps(
            {
                "status": "PASS",
                "milestone_id": config["milestone_id"],
                "core": configured_ids,
                "ready_for_user_decision": 0,
                "wp5": "READY_AFTER_GOVERNED_MERGE",
                "trade_authority": "NONE"
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
