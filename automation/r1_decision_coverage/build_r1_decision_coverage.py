from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SOURCE_PR = 153
SOURCE_BRANCH = "agent/r1-decision-coverage-completion"
R0_MERGE_SHA = "42b34c327fa5b1168c4e9d11846ba1e0f6712ac6"
TRADE_AUTHORITY = "NONE"
AS_OF = "2026-07-27"
CORE2 = {"000333.SZ", "600900.SH"}
P0 = {"300124.SZ", "300750.SZ", "601138.SH"}
EXPECTED_SIMULATION = {
    "000333.SZ", "002463.SZ", "300124.SZ", "300750.SZ", "510500.SH",
    "600036.SH", "600276.SH", "600309.SH", "600406.SH", "600660.SH",
    "600690.SH", "600900.SH", "600938.SH", "600941.SH", "601138.SH", "601899.SH",
}


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


def walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def record_code(record: dict[str, Any]) -> str | None:
    raw = record.get("security_id") or record.get("security_code") or record.get("stock_code") or record.get("code")
    if raw is None:
        return None
    text = str(raw)
    if "." in text:
        return text.split(".", 1)[0]
    return text.zfill(6) if text.isdigit() else text


def candidate_score(record: dict[str, Any]) -> int:
    fields = {
        "deep_refresh_summary": 20,
        "core_thesis": 16,
        "source_urls": 15,
        "key_risk": 10,
        "portfolio_role": 8,
        "source_as_of": 6,
        "stale_pe_20260624": 4,
        "stale_pb_20260624": 4,
        "attractiveness_score": 3,
        "evidence_score": 3,
    }
    return sum(weight for key, weight in fields.items() if record.get(key) not in (None, "", [], {}))


def best_candidate_record(candidate: dict[str, Any], security_id: str) -> dict[str, Any]:
    code = security_id.split(".", 1)[0]
    matches = [row for row in walk(candidate) if record_code(row) == code]
    return max(matches, key=candidate_score) if matches else {}


def parse_sources(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip().startswith("http")]
    return []


def find_position(rows: list[dict[str, Any]], security_id: str) -> dict[str, Any]:
    for row in rows:
        if row.get("security_id") == security_id:
            return row
    return {}


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    assets = registry.setdefault("assets", [])
    for index, existing in enumerate(assets):
        if existing.get("asset_id") == asset["asset_id"]:
            assets[index] = {**existing, **asset}
            return
    assets.append(asset)


def patch_lineage_test(root: Path) -> None:
    path = root / "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"
    text = path.read_text(encoding="utf-8")
    if "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN" in text:
        return
    needle = '    else:\n        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'
    block = '''    elif step == "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R0"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R1"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R2"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["decision_grade_coverage"]["simulation_complete"] == 16
        assert register["wp5"]["decision_grade_coverage"]["real_product_complete"] == 7
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is False
        assert register["next_task"] == "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN"
    else:
        assert step == "R2_PRODUCT_CAPABILITY_HARDENING_ACCEPTED_ON_MAIN"'''
    if needle not in text:
        raise ValueError("Unable to locate lineage insertion point")
    path.write_text(text.replace(needle, block), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    source_head = str(args.source_head_sha)

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json"
    protected_hashes = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }

    real = read_json(real_path)
    simulation = read_json(sim_path)
    candidate = read_json(candidate_path)
    external = read_json(root / "automation/r1_decision_coverage/r1_external_facts.json")
    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    contract = read_json(control / "WP5_PORTFOLIO_DECISION_CONTRACT.json")
    p0_action = read_json(state / "60_DECISIONS/WP5_P0_ACTION_REVIEW_CURRENT.json")

    sim_holdings = simulation["holdings"]
    real_holdings = real["holdings"]
    sim_ids = {row["security_id"] for row in sim_holdings}
    if sim_ids != EXPECTED_SIMULATION:
        raise ValueError(f"R1 simulation scope drift: {sorted(sim_ids ^ EXPECTED_SIMULATION)}")
    if len(real_holdings) != 7:
        raise ValueError("R1 requires exactly seven accepted Real holdings")

    total_sim_assets = float(simulation["summary"]["account_total_assets"])
    total_real_assets = float(real["summary"]["account_total_assets"])
    p0_positions = p0_action.get("positions", [])

    core_postures = {
        "000333.SZ": "HOLD_ADD_REVIEW_ONLY_AFTER_FRESH_MARK_EVENT_USER_GATES_AND_15_PERCENT_HURDLE",
        "600900.SH": "HOLD_NO_ADD_AT_CURRENT_MARK_UNDER_CURRENT_BASE_ASSUMPTIONS",
    }
    p0_fallback = {
        "300124.SZ": "HOLD_REDUCED_OBSERVATION_POSITION_NO_ADD",
        "300750.SZ": "HOLD_VALIDATION_POSITION_NO_ADD",
        "601138.SH": "HOLD_REDUCED_WEIGHT_NO_ADD",
    }

    simulation_records: list[dict[str, Any]] = []
    for holding in sim_holdings:
        sid = holding["security_id"]
        candidate_record = best_candidate_record(candidate, sid)
        sources = parse_sources(candidate_record.get("source_urls"))
        common = {
            "security_id": sid,
            "security_name": holding["security_name"],
            "current_mark": holding["mark"],
            "mark_as_of": holding["mark_as_of"],
            "market_value": holding["market_value"],
            "current_weight": round(float(holding["market_value"]) / total_sim_assets, 8),
            "portfolio_bucket": holding.get("portfolio_bucket"),
            "current_unrealized_pnl_pct": holding.get("unrealized_pnl_pct"),
            "base_case_hurdle": external["policy"]["base_case_hurdle"],
            "implementation_ready": False,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
        }
        if sid in CORE2:
            record = {
                **common,
                "coverage_source": "REUSED_WP4B_CORE2_HARDENED_RESEARCH",
                "coverage_status": "DECISION_COVERAGE_COMPLETE_REUSED_NOT_REBUILT",
                "portfolio_role": candidate_record.get("portfolio_role") or holding.get("portfolio_bucket"),
                "thesis_summary": candidate_record.get("deep_refresh_summary") or candidate_record.get("core_thesis") or "Existing WP4-B Core2 research remains the governing thesis.",
                "valuation_reference": {"stale_pe": candidate_record.get("stale_pe_20260624"), "stale_pb": candidate_record.get("stale_pb_20260624")},
                "posture": core_postures[sid],
                "add_conditions": ["fresh completed close", "current event classification", "user position continuity", "Base scenario expected return >=15%"],
                "trim_conditions": ["thesis deterioration", "portfolio role or risk budget breach"],
                "exit_conditions": ["core thesis structurally invalidated"],
                "evidence_gaps": ["fresh decision-date valuation and portfolio synthesis remain R2/R3 gates"],
                "confidence": "HIGH_FOR_COVERAGE_NOT_EXECUTION",
                "source_urls": sources,
            }
        elif sid in P0:
            p0 = find_position(p0_positions, sid)
            record = {
                **common,
                "coverage_source": "REUSED_WP5_P0_PRIMARY_SOURCE_REUNDERWRITE",
                "coverage_status": "DECISION_COVERAGE_COMPLETE_REUSED_NOT_REBUILT",
                "portfolio_role": holding.get("portfolio_bucket"),
                "thesis_summary": candidate_record.get("deep_refresh_summary") or candidate_record.get("core_thesis") or "Existing WP5 P0 primary-source re-underwrite remains governing.",
                "valuation_reference": {"stale_pe": candidate_record.get("stale_pe_20260624"), "stale_pb": candidate_record.get("stale_pb_20260624")},
                "posture": p0.get("conditional_posture") or p0.get("posture") or p0_fallback[sid],
                "add_conditions": ["fresh completed close", "current weight inside governed band", "Base scenario expected return >=15%", "user approval"],
                "trim_conditions": ["weight exceeds governed band", "research kill trigger"],
                "exit_conditions": ["primary thesis invalidated"],
                "evidence_gaps": ["fresh action-date mark and user continuity remain mandatory"],
                "confidence": "HIGH_FOR_COVERAGE_NOT_EXECUTION",
                "source_urls": sources,
            }
        else:
            policy = external["simulation_policies"][sid]
            summary = candidate_record.get("deep_refresh_summary") or candidate_record.get("core_thesis") or candidate_record.get("thesis_summary")
            record = {
                **common,
                "coverage_source": "R1_STANDARDIZED_FROM_CANDIDATE_PRIMARY_SOURCE_EVIDENCE_AND_PORTFOLIO_POLICY" if sid != "510500.SH" else "R1_ETF_ROLE_COVERAGE",
                "coverage_status": "DECISION_COVERAGE_COMPLETE_NOT_IMPLEMENTATION_READY",
                "portfolio_role": policy["role"],
                "thesis_summary": summary or ("中证500提供A股中盘卫星与基准暴露，不是因历史目标权重而自动补仓。" if sid == "510500.SH" else "Candidate evidence exists but remains insufficient for implementation-ready action."),
                "valuation_reference": {
                    "stale_pe": candidate_record.get("stale_pe_20260624"),
                    "stale_pb": candidate_record.get("stale_pb_20260624"),
                    "valuation_posture": "REQUIRES_FRESH_SCENARIO_AT_R3_ACTION_GATE",
                },
                "posture": policy["posture"],
                "add_conditions": policy["add_conditions"],
                "trim_conditions": policy["trim_conditions"],
                "exit_conditions": policy["exit_conditions"],
                "evidence_gaps": ["fresh scenario valuation", "R2 portfolio risk budget", "R3 unified action comparison"],
                "confidence": policy["confidence"],
                "candidate_evidence_as_of": candidate_record.get("source_as_of") or candidate.get("as_of"),
                "candidate_lane": candidate_record.get("lifecycle_state") or candidate_record.get("proposed_lifecycle_state") or "NOT_FOUND_OR_ETF",
                "key_risk": candidate_record.get("key_risk"),
                "source_urls": sources,
            }
        simulation_records.append(record)

    real_weights = {row["security_id"]: round(float(row["market_value"]) / total_real_assets, 8) for row in real_holdings}
    real_records: list[dict[str, Any]] = []
    for holding in real_holdings:
        sid = holding["security_id"]
        base = {
            "security_id": sid,
            "security_name": holding["security_name"],
            "asset_class": holding["asset_class"],
            "current_weight": real_weights[sid],
            "market_value": holding["market_value"],
            "mark_as_of": holding["mark_as_of"],
            "implementation_ready": False,
            "position_change_authorized": False,
            "order_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
        }
        if sid in external["bond_funds"]:
            fact = external["bond_funds"][sid]
            real_records.append({
                **base,
                "coverage_source": "OFFICIAL_FUND_REPORT_AND_PRODUCT_DISCLOSURE",
                "coverage_status": "DECISION_GRADE_LOOKTHROUGH_COMPLETE_WITH_DISCLOSED_SECURITY_OVERLAP_LIMITATION",
                "portfolio_role": fact["role"],
                "risk_style": fact["risk_style"],
                "posture": fact["posture"],
                "lookthrough": {k: v for k, v in fact.items() if k in {"latest_report", "equity_weight_pct", "fixed_income_asset_pct", "benchmark", "q2_return_pct"}},
                "add_conditions": ["cross-fund duration, credit and security overlap are acceptable", "R2 confirms defensive-sleeve need", "user approval"],
                "trim_conditions": ["overlap is high without differentiated role", "duration/credit/equity beta exceeds R2 budget", "inferior risk-adjusted role versus retained fund"],
                "exit_conditions": ["mandate drift or persistent risk-adjusted underperformance after full-cycle review"],
                "residual_evidence_limit": "Latest security-level common-holding percentage is not reliably quantified for all three funds; R1 therefore prohibits adding and passes aggregation risk to R2.",
                "source_urls": fact["source_urls"],
            })
        elif sid in {"159612.SZ", "159655.SZ"}:
            comparison = external["sp500_vehicle"]
            preferred = sid == comparison["preferred_vehicle"]
            real_records.append({
                **base,
                "coverage_source": "OFFICIAL_ETF_DISCLOSURE_AND_CURRENT_PCF_WITH_MARKET_LIQUIDITY_COMPARISON",
                "coverage_status": "DECISION_COVERAGE_COMPLETE_SINGLE_VEHICLE_SELECTION_CONDITIONAL",
                "portfolio_role": "单一标普500美国大盘权益袖套",
                "economic_duplicate": True,
                "preferred_vehicle": preferred,
                "posture": "CONDITIONAL_RETAIN_AS_SINGLE_VEHICLE" if preferred else "CONDITIONAL_CONSOLIDATION_SOURCE_VEHICLE",
                "fee_tie": comparison["fee_tie"],
                "selection_reasons": comparison["reasons"],
                "conditions_before_consolidation": comparison["conditions_before_consolidation"],
                "source_urls": comparison["source_urls"],
            })
        else:
            role = external["a_share_etf_roles"][sid]
            real_records.append({
                **base,
                "coverage_source": "R1_A_SHARE_CORE_SATELLITE_ROLE_CONFIRMATION",
                "coverage_status": "DECISION_COVERAGE_COMPLETE_ROLE_CONFIRMED",
                "portfolio_role": role["role"],
                "posture": role["policy"],
                "add_conditions": ["R2 confirms total A-share equity budget", "A500 core is not smaller than CSI500 satellite before further CSI500 adds", "user approval"],
                "trim_conditions": ["R2 lowers the sleeve budget or identifies excessive duplication"],
                "exit_conditions": ["the portfolio architecture no longer requires this sleeve"],
                "source_urls": [],
            })

    pack = {
        "pack_id": "R1_DECISION_COVERAGE_PACK_CURRENT_V1",
        "status": "DECISION_COVERAGE_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NOT_IMPLEMENTATION_READY",
        "as_of": AS_OF,
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head,
        "r0_merge_sha": R0_MERGE_SHA,
        "simulation": {
            "holding_count": len(simulation_records),
            "reused_core2_count": len([x for x in simulation_records if x["security_id"] in CORE2]),
            "reused_p0_count": len([x for x in simulation_records if x["security_id"] in P0]),
            "r1_new_standardized_count": len([x for x in simulation_records if x["security_id"] not in CORE2 | P0]),
            "records": simulation_records,
        },
        "real_account": {
            "holding_count": len(real_records),
            "bond_fund_count": 3,
            "sp500_vehicle_count": 2,
            "a_share_etf_count": 2,
            "records": real_records,
            "sp500_single_vehicle_selection": external["sp500_vehicle"],
            "a_share_core_satellite_roles": external["a_share_etf_roles"],
        },
        "coverage_definition": {
            "required_fields": ["portfolio_role", "posture", "add_conditions", "trim_conditions", "exit_conditions", "evidence_gaps_or_limits"],
            "coverage_is_not_execution": True,
            "portfolio_synthesis_deferred_to_r2": True,
            "action_matrix_deferred_to_r3": True,
        },
        "implementation_ready_count": 0,
        "ready_for_user_decision_count": 0,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0},
        "trade_authority": TRADE_AUTHORITY,
    }

    posture_counts: dict[str, int] = {}
    for row in simulation_records:
        posture_counts[row["posture"]] = posture_counts.get(row["posture"], 0) + 1
    summary = {
        "summary_id": "R1_DECISION_COVERAGE_SUMMARY_CURRENT_V1",
        "status": "R1_COMPLETE_COVERAGE_ONLY_R2_NOT_STARTED",
        "simulation_coverage": {"complete": 16, "total": 16, "posture_counts": posture_counts},
        "real_product_coverage": {"complete": 7, "total": 7},
        "bond_fund_conclusion": "Three products have differentiated risk roles: pure fixed income, enhanced bond with equity/convertible beta, and government-bond-benchmark active bond. Hold all; add to none until R2 aggregates overlap, duration, credit and beta.",
        "sp500_conclusion": "159655.SZ is the conditional preferred single vehicle because scale and trading activity are materially higher and current PCF is available. No consolidation is trade-ready before same-session spread/premium/tracking checks and user approval.",
        "a_share_etf_conclusion": "159352.SZ is broad-core; 510500.SH is mid-cap satellite. Future A-share contributions favor A500 until core is not smaller than satellite.",
        "next_stage": "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN",
        "implementation_ready_count": 0,
        "trade_authority": TRADE_AUTHORITY,
    }

    pack_path = state / "30_RESEARCH/R1_DECISION_COVERAGE_PACK_CURRENT.json"
    summary_path = state / "60_DECISIONS/R1_DECISION_COVERAGE_SUMMARY_CURRENT.json"
    write_json(pack_path, pack)
    write_json(summary_path, summary)

    contract["source_pr"] = SOURCE_PR
    contract["source_head_sha"] = source_head
    contract["status"] = "WP5_2_DECISION_GRADE_COVERAGE_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    contract["fixed_workstreams"]["WP5-2"]["status"] = "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    contract["fixed_workstreams"]["WP5-2"]["remaining"] = []
    contract["fixed_workstreams"]["WP5-2"]["completed"] = [
        "SIMULATION_DECISION_COVERAGE_16_OF_16",
        "REAL_PRODUCT_DECISION_COVERAGE_7_OF_7",
        "BOND_FUND_DECISION_GRADE_LOOKTHROUGH_3_WITH_DISCLOSED_SECURITY_OVERLAP_LIMITATION",
        "SP500_SINGLE_VEHICLE_CONDITIONAL_SELECTION_159655",
        "A500_CSI500_ROLE_CONFIRMATION",
    ]
    contract["next_task"] = "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN"
    contract["current_completion_state"] = {
        "all_current_positions_covered": True,
        "portfolio_construction_synthesis_delivered": False,
        "position_action_matrix_delivered": False,
        "user_decision_pack_delivered": False,
        "orders_created": 0,
    }
    write_json(control / "WP5_PORTFOLIO_DECISION_CONTRACT.json", contract)

    execution["current_step"] = "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN"
    execution["overall_status"] = "R1_DECISION_COVERAGE_COMPLETE_CONDITIONAL_ON_PR153_MERGE_R2_NOT_STARTED"
    execution["latest_completed_main_pr"] = 152
    execution["latest_completed_main_merge_sha"] = R0_MERGE_SHA
    execution["github_merge_sha"] = R0_MERGE_SHA
    execution["latest_governed_merge_sha"] = R0_MERGE_SHA
    execution["next_task"] = "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN"
    execution["development_roadmap"]["R0"]["status"] = "COMPLETED_ON_MAIN"
    execution["development_roadmap"]["R1"]["status"] = "CURRENT_IF_PRESENT_ON_MAIN"
    execution["development_roadmap"]["R2"]["status"] = "NOT_STARTED"
    execution["r1_decision_coverage"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head,
        "simulation_complete": 16,
        "simulation_total": 16,
        "real_product_complete": 7,
        "real_product_total": 7,
        "implementation_ready_count": 0,
        "trade_authority": TRADE_AUTHORITY,
    }
    execution["wp5"]["source_pr"] = SOURCE_PR
    execution["wp5"]["source_head_sha"] = source_head
    execution["wp5"]["status"] = "WP5_2_DECISION_GRADE_COVERAGE_COMPLETE_NO_USER_ACTION_PACK"
    execution["wp5"]["decision_grade_coverage"] = {
        "simulation_complete": 16,
        "simulation_total": 16,
        "real_product_complete": 7,
        "real_product_total": 7,
        "bond_fund_lookthrough_status": "DECISION_GRADE_COMPLETE_WITH_RESIDUAL_SECURITY_OVERLAP_LIMITATION",
        "sp500_preferred_vehicle": "159655.SZ_CONDITIONAL",
        "a_share_core_satellite_role_confirmed": True,
    }
    execution["wp5"]["portfolio_construction_synthesis_complete"] = False
    execution["wp5"]["position_action_matrix_complete"] = False
    execution["wp5"]["user_decision_pack_complete"] = False
    execution["wp5"]["ready_for_user_decision_count"] = 0
    execution["wp5"]["position_mutation_allowed"] = False
    execution["wp5"]["order_execution_allowed"] = False
    execution["trade_authority"] = TRADE_AUTHORITY
    write_json(control / "EXECUTION_REGISTER_CURRENT.json", execution)

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = master.replace("- 最新已完成main合并：PR #151 / `247203c005b76cfa32a0d04d31390631c304e738`", f"- 最新已完成main合并：PR #152 / `{R0_MERGE_SHA}`")
    master = master.replace("- 本轮治理来源：PR #152 /", "- R0治理来源：PR #152 /")
    master = master.replace("### R0｜Product Authority Freeze\n\n- 状态：`CURRENT_IF_PRESENT_ON_MAIN`", "### R0｜Product Authority Freeze\n\n- 状态：`COMPLETED_ON_MAIN`")
    master = master.replace("### R1｜Decision Coverage Completion\n", "### R1｜Decision Coverage Completion\n\n- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#153`。\n")
    master = master.replace("`R1_DECISION_COVERAGE_COMPLETION_AFTER_R0_PRESENT_ON_MAIN`", "`R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_AFTER_R1_PRESENT_ON_MAIN`")
    if "## 八、R1验收结果" not in master:
        master += """

## 八、R1验收结果

- 模拟盘决策覆盖：`16/16`；其中Core2复用2只、P0复用3只、R1新增标准化覆盖11只。
- 真实账户产品覆盖：`7/7`；三只债基形成差异化风险穿透，两只标普500ETF完成条件性单一载体选择，A500/中证500角色确认。
- R1完成不代表可交易；R2组合构建、R3动作矩阵与用户决策包仍未开始。
- 实际持仓、Candidate、旧决策和订单变更均为0。
"""
    write_text(master_path, master)

    acceptance = {
        "acceptance_id": "R1_DECISION_COVERAGE_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": source_head,
        "r0_merge_sha": R0_MERGE_SHA,
        "simulation_coverage_complete": 16,
        "simulation_total": 16,
        "real_product_coverage_complete": 7,
        "real_product_total": 7,
        "wp5_2_status": "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN",
        "wp5_3_status": "NOT_STARTED",
        "implementation_ready_count": 0,
        "ready_for_user_decision_count": 0,
        "residual_limitations": [
            "latest security-level overlap percentage is not reliably available for all three bond funds",
            "all position actions require fresh marks, R2 synthesis, R3 comparison and user approval",
        ],
        "protected_state_hashes": protected_hashes,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0},
        "next_authorized_stage": "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS",
        "trade_authority": TRADE_AUTHORITY,
    }
    write_json(control / "R1_DECISION_COVERAGE_ACCEPTANCE_RECORD.json", acceptance)

    table_rows = []
    for row in simulation_records:
        table_rows.append(f"| {row['security_id']} | {row['security_name']} | {row['portfolio_role']} | `{row['posture']}` | {row['confidence']} |")
    status_md = f"""# 股票投资助手｜R1 Decision Coverage CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#{SOURCE_PR}`
- R0合并SHA：`{R0_MERGE_SHA}`
- 模拟盘覆盖：`16/16`
- 真实账户产品覆盖：`7/7`
- Implementation Ready：`0`
- 交易权限：`NONE`

## 模拟盘统一覆盖

| 代码 | 标的 | 组合角色 | 当前条件判断 | 置信度 |
|---|---|---|---|---|
{chr(10).join(table_rows)}

## 真实账户结论

- 三只债基不是同一种风险：富国天利为纯固定收益锚；易方达增强回报含显著股票和可转债增强；招商安泰为国债基准导向的主动债券仓。当前统一为持有、不新增，逐券重合度限制转交R2聚合。
- `159655.SZ`列为标普500条件性优先保留载体；在同日价差、折溢价、跟踪偏离和申赎状态未复核前，不形成合并交易。
- `159352.SZ`为A股宽基核心，`510500.SH`为中盘卫星；未来A股新增资金优先A500，直至核心不小于卫星。

## 阶段边界

R1只完成研究与条件覆盖。R2尚未开始组合风险聚合，R3尚未形成统一动作矩阵和用户决策包，因此当前不产生交易建议或订单。
"""
    write_text(control / "R1_STATUS_CURRENT.md", status_md)

    for asset_id, location, role, fmt in [
        ("R1_DECISION_COVERAGE_PACK_CURRENT", "investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/R1_DECISION_COVERAGE_PACK_CURRENT.json", "All-current-position standardized decision coverage", "JSON"),
        ("R1_DECISION_COVERAGE_SUMMARY_CURRENT", "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R1_DECISION_COVERAGE_SUMMARY_CURRENT.json", "Coverage conclusions before R2 portfolio synthesis", "JSON"),
        ("R1_DECISION_COVERAGE_ACCEPTANCE", "investment_os_runtime/00_CONTROL/R1_DECISION_COVERAGE_ACCEPTANCE_RECORD.json", "R1 coverage, lineage and zero-mutation acceptance", "JSON"),
        ("R1_STATUS_CURRENT", "investment_os_runtime/00_CONTROL/R1_STATUS_CURRENT.md", "Human-readable R1 coverage status", "MD"),
    ]:
        upsert_asset(registry, {
            "asset_id": asset_id,
            "authority": "CANONICAL_CURRENT_IF_PRESENT_ON_MAIN",
            "format": fmt,
            "location": location,
            "promotion_evidence": "MERGED_PR_AND_FILE_PRESENCE",
            "role": role,
            "source_pr": SOURCE_PR,
            "source_head_sha": source_head,
            "status": "CURRENT_IF_PRESENT_ON_MAIN",
            "trade_authority": TRADE_AUTHORITY,
        })
    registry["active_branch_candidate"] = SOURCE_BRANCH
    registry["latest_completed_main_pr"] = 152
    registry["latest_completed_main_merge_sha"] = R0_MERGE_SHA
    registry["github_merge_sha"] = R0_MERGE_SHA
    registry["latest_governed_merge_sha"] = R0_MERGE_SHA
    registry["registry_status"] = "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN"
    registry["status"] = "GITHUB_CURRENT_IF_PR153_MERGED_R2_NOT_STARTED"
    registry["date"] = AS_OF
    registry["trade_authority"] = TRADE_AUTHORITY
    write_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json", registry)

    patch_lineage_test(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
