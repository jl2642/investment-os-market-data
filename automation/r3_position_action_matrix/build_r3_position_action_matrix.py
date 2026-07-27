from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_PR = 155
SOURCE_BRANCH = "agent/r3-position-action-matrix"
R2_MERGE_SHA = "fc57e7a08fee6870130871e8491bb2db59b70e54"
TRADE_AUTHORITY = "NONE"
AS_OF = "2026-07-27"


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


def money(value: float) -> float:
    return round(value, 2)


def pct(value: float) -> float:
    return round(value, 8)


def by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["security_id"]: row for row in rows}


def upsert_asset(registry: dict[str, Any], asset: dict[str, Any]) -> None:
    assets = registry.setdefault("assets", [])
    for i, row in enumerate(assets):
        if row.get("asset_id") == asset["asset_id"]:
            assets[i] = {**row, **asset}
            return
    assets.append(asset)


def real_record(
    holding: dict[str, Any],
    action: str,
    target_band: tuple[float, float],
    priority: str,
    rationale: list[str],
    amount_range: tuple[float, float] | None,
    gates: list[str],
    consequence: str,
    retained_exposure: str,
) -> dict[str, Any]:
    return {
        "account": "REAL",
        "security_id": holding["security_id"],
        "security_name": holding["security_name"],
        "current_weight": pct(float(holding["market_value"]) / float(holding["account_total_assets"])),
        "current_market_value_rmb": money(float(holding["market_value"])),
        "mark_as_of": holding.get("mark_as_of"),
        "recommended_action": action,
        "target_weight_band": [target_band[0], target_band[1]],
        "recommended_amount_range_rmb": None if amount_range is None else [money(amount_range[0]), money(amount_range[1])],
        "priority": priority,
        "rationale": rationale,
        "retained_exposure": retained_exposure,
        "implementation_gates": gates,
        "not_executing_consequence": consequence,
        "ready_for_user_decision": True,
        "implementation_ready": False,
        "position_change_authorized": False,
        "order_authorized": False,
        "trade_authority": TRADE_AUTHORITY,
    }


def simulation_record(
    holding: dict[str, Any],
    r1: dict[str, Any],
    action: str,
    target_band: tuple[float, float],
    priority: str,
    rationale: list[str],
    consequence: str,
) -> dict[str, Any]:
    current_weight = float(r1["current_weight"])
    band_status = "WITHIN_BAND" if target_band[0] <= current_weight <= target_band[1] else ("ABOVE_BAND" if current_weight > target_band[1] else "BELOW_BAND")
    return {
        "account": "SIMULATION",
        "security_id": holding["security_id"],
        "security_name": holding["security_name"],
        "current_weight": pct(current_weight),
        "current_market_value_rmb": money(float(holding["market_value"])),
        "current_unrealized_pnl_rmb": money(float(holding["unrealized_pnl"])),
        "current_unrealized_pnl_pct": pct(float(holding["unrealized_pnl_pct"])),
        "mark_as_of": holding.get("mark_as_of"),
        "recommended_action": action,
        "target_weight_band": [target_band[0], target_band[1]],
        "band_status": band_status,
        "priority": priority,
        "portfolio_role": r1.get("portfolio_role"),
        "rationale": rationale,
        "add_conditions": r1.get("add_conditions", []),
        "trim_conditions": r1.get("trim_conditions", []),
        "exit_conditions": r1.get("exit_conditions", []),
        "evidence_gaps": r1.get("evidence_gaps", []),
        "not_executing_consequence": consequence,
        "ready_for_user_decision": True,
        "implementation_ready": False,
        "position_change_authorized": False,
        "order_authorized": False,
        "trade_authority": TRADE_AUTHORITY,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    decisions = state / "60_DECISIONS"

    real_path = state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
    sim_path = state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
    candidate_path = state / "40_CANDIDATE/CANDIDATE_CURRENT.json"
    legacy_path = decisions / "DECISION_PROPOSALS_CURRENT.json"
    protected_hashes = {
        "real_account_positions_sha256": sha256(real_path),
        "simulation_positions_sha256": sha256(sim_path),
        "candidate_current_sha256": sha256(candidate_path),
        "legacy_decisions_sha256": sha256(legacy_path),
    }

    real = read_json(real_path)
    simulation = read_json(sim_path)
    r1 = read_json(state / "30_RESEARCH/R1_DECISION_COVERAGE_PACK_CURRENT.json")
    r2 = read_json(decisions / "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT.json")
    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    contract = read_json(control / "WP5_PORTFOLIO_DECISION_CONTRACT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")

    if r2["status"] != "PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_R3_NOT_STARTED":
        raise ValueError("R2 Current is not accepted for R3")
    if r1["simulation"]["holding_count"] != 16 or r1["real_account"]["holding_count"] != 7:
        raise ValueError("R1 coverage incomplete")

    real_total = float(real["summary"]["account_total_assets"])
    sim_total = float(simulation["summary"]["account_total_assets"])
    real_rows = by_id(real["holdings"])
    sim_rows = by_id(simulation["holdings"])
    r1_sim = by_id(r1["simulation"]["records"])
    if set(real_rows) != {"017534.OF", "110017.OF", "159352.SZ", "159612.SZ", "159655.SZ", "217003.OF", "510500.SH"}:
        raise ValueError("Real holding scope drift")
    if len(sim_rows) != 16 or set(sim_rows) != set(r1_sim):
        raise ValueError("Simulation holding scope drift")

    for row in real_rows.values():
        row["account_total_assets"] = real_total

    common_real_gates = [
        "user confirms zero transactions or reports deltas after 2026-07-24",
        "latest completed-close marks or fund NAV are refreshed",
        "user explicitly selects the relevant R3 decision item",
        "separate governed implementation proposal is created",
    ]
    etf_gates = common_real_gates + [
        "same-session bid-ask spread and traded value are acceptable",
        "premium/discount and tracking difference are acceptable",
        "subscription/redemption status and transaction costs are checked",
    ]

    hybrid_trim = (
        float(real_rows["110017.OF"]["market_value"]) - real_total * 0.17,
        float(real_rows["110017.OF"]["market_value"]) - real_total * 0.15,
    )
    csi_trim = (
        float(real_rows["510500.SH"]["market_value"]) - real_total * 0.09,
        float(real_rows["510500.SH"]["market_value"]) - real_total * 0.075,
    )
    a500_add = (30000.0, 40000.0)
    sp500_add = (13000.0, 19000.0)

    real_actions = [
        real_record(
            real_rows["017534.OF"], "HOLD_NO_ADD", (0.22, 0.25), "P3",
            ["pure fixed-income defensive anchor", "combined pure defensive sleeve is already near the R2 reference"],
            None, common_real_gates,
            "No material structural harm; adding would crowd out higher-priority equity-core repair.",
            "high-credit fixed-income defence",
        ),
        real_record(
            real_rows["217003.OF"], "HOLD_NO_ADD", (0.20, 0.23), "P3",
            ["government-bond-benchmark defensive role", "preserves diversification inside the defensive sleeve"],
            None, common_real_gates,
            "No immediate structural harm; adding would increase nominal bond concentration.",
            "government-bond-oriented active defence",
        ),
        real_record(
            real_rows["110017.OF"], "TRIM", (0.13, 0.17), "P1",
            ["22.23% exceeds the enhanced-bond risk budget", "equity and convertible-bond beta must not be counted as pure defence"],
            hybrid_trim, common_real_gates,
            "Hybrid beta remains oversized and delays A-share core and global-equity repair.",
            "a smaller enhanced-bond return sleeve",
        ),
        real_record(
            real_rows["510500.SH"], "TRIM", (0.075, 0.09), "P1",
            ["mid-cap satellite is larger than the A500 core", "cross-account CSI500 exposure already exists in Simulation"],
            csi_trim, etf_gates,
            "Core-satellite inversion and duplicated mid-cap beta remain unresolved.",
            "a controlled A-share mid-cap satellite",
        ),
        real_record(
            real_rows["159352.SZ"], "ADD", (0.15, 0.18), "P1",
            ["A500 is the designated broad-core sleeve", "phase-one funding should make the core not smaller than the satellite"],
            a500_add, etf_gates,
            "A-share exposure remains tilted toward satellite beta rather than broad-core compounding.",
            "A-share broad-core exposure",
        ),
        real_record(
            real_rows["159612.SZ"], "EXIT_MIGRATE_TO_159655", (0.0, 0.0), "P2",
            ["economic duplicate of 159655", "R1 selected 159655 as the conditional preferred single vehicle"],
            (float(real_rows["159612.SZ"]["market_value"]), float(real_rows["159612.SZ"]["market_value"])),
            etf_gates,
            "Duplicate fees, monitoring and execution complexity persist without strategic diversification benefit.",
            "S&P500 exposure retained through 159655",
        ),
        real_record(
            real_rows["159655.SZ"], "RETAIN_AND_ADD", (0.12, 0.16), "P2",
            ["preferred single S&P500 vehicle", "global-equity sleeve is below the balanced reference"],
            sp500_add, etf_gates,
            "Global diversification remains below the R2 reference and the duplicate vehicle remains unresolved.",
            "single-vehicle S&P500 exposure",
        ),
    ]

    sim_policy: dict[str, tuple[str, tuple[float, float], str, list[str], str]] = {
        "000333.SZ": ("HOLD", (0.06, 0.08), "P2", ["quality-core weight is appropriate", "add only after fresh 15% Base-return hurdle"], "No material consequence while thesis remains intact."),
        "002463.SZ": ("WAIT_EVIDENCE_NO_ADD", (0.015, 0.025), "P1", ["largest evidence-quality gap in the AI PCB sleeve", "loss alone is not an exit trigger"], "Additional capital would compound a weakly evidenced entry; passive holding risks opportunity cost."),
        "300124.SZ": ("OBSERVE_NO_ADD", (0.015, 0.025), "P1", ["already reduced to an observation position", "Base-return hurdle failed in P0 review"], "Premature averaging would raise exposure before thesis validation."),
        "300750.SZ": ("OBSERVE_NO_ADD", (0.03, 0.045), "P1", ["long-term leadership remains credible", "current position is a validation sample rather than a migration candidate"], "Premature averaging increases regulatory and valuation risk."),
        "510500.SH": ("HOLD_NO_TOP_UP", (0.05, 0.07), "P2", ["current benchmark satellite is already inside band", "historical 10% label is not a buying mandate"], "No material consequence; top-up would add unwanted beta and cross-account duplication."),
        "600036.SH": ("HOLD", (0.05, 0.07), "P2", ["quality financial core remains within band", "dividend/cash-flow cluster is near its cap"], "No material consequence; adding before NIM and asset-quality gates could crowd the factor budget."),
        "600276.SH": ("HOLD", (0.03, 0.05), "P2", ["position is within the medical-growth band", "pipeline and commercialization gates remain open"], "No material consequence; exit would lose optionality before a thesis kill trigger."),
        "600309.SH": ("HOLD", (0.04, 0.06), "P2", ["cycle sleeve is within band", "cost and technology advantage remain the retained alpha"], "No material consequence; adding at the wrong cycle point would reduce margin of safety."),
        "600406.SH": ("HOLD_NO_ADD", (0.03, 0.045), "P2", ["defensive-growth role is useful", "valuation and cash-conversion gates do not support adding"], "No material consequence; adding risks paying ahead of order conversion."),
        "600660.SH": ("HOLD_NO_ADD", (0.07, 0.09), "P2", ["largest position remains below the 10% hard cap", "already above its historical role reference"], "No material consequence; adding would create concentration and auto-cycle risk."),
        "600690.SH": ("HOLD", (0.03, 0.045), "P3", ["weight is appropriate", "Midea overlap review blocks new capital"], "No material consequence; exiting would remove a useful peer comparison prematurely."),
        "600900.SH": ("HOLD_NO_ADD", (0.05, 0.07), "P3", ["low-volatility utility role remains intact", "current mark did not clear the add hurdle"], "No material consequence; adding would further crowd the dividend factor."),
        "600938.SH": ("HOLD_NO_CHASE", (0.04, 0.06), "P2", ["position is near the upper half of its cycle band", "strong gains should not be converted into an automatic add"], "No material consequence; chasing would increase commodity-path dependence."),
        "600941.SH": ("HOLD_NO_ADD", (0.05, 0.07), "P2", ["cash-flow core remains within band", "dividend/cash-flow cluster is already 24.81%"], "No material consequence; adding risks breaching the theme cap."),
        "601138.SH": ("OBSERVE_CONDITIONAL_TRIM_NO_ADD", (0.025, 0.035), "P1", ["reduced-weight AI hardware validation position", "fresh weight above 3.5% would trigger a small trim"], "Without review, a high-valuation loss position may retain too much factor risk."),
        "601899.SH": ("HOLD", (0.03, 0.045), "P2", ["resource-growth position is inside band", "project execution and commodity assumptions remain the add gates"], "No material consequence; adding without project/cycle confirmation increases commodity concentration."),
    }

    sim_actions = []
    for sid in sorted(sim_rows):
        action, band, priority, rationale, consequence = sim_policy[sid]
        sim_actions.append(simulation_record(sim_rows[sid], r1_sim[sid], action, band, priority, rationale, consequence))

    user_decisions = [
        {
            "decision_id": "R3-D1",
            "title": "采用长期稳健成长作为真实账户第一阶段迁移基准",
            "recommendation": "APPROVE",
            "scope": ["R3-D2", "R3-D3", "R3-D4", "R3-D5", "R3-D6"],
            "default": True,
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D2",
            "title": "易方达增强回报债券A减持约¥2.4万–¥3.3万",
            "recommendation": "APPROVE_CONDITIONAL",
            "dependency": "R3-D1",
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D3",
            "title": "真实账户中证500ETF减持约¥1.9万–¥2.6万",
            "recommendation": "APPROVE_CONDITIONAL",
            "dependency": "R3-D1",
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D4",
            "title": "南方中证A500ETF增持约¥3万–¥4万",
            "recommendation": "APPROVE_CONDITIONAL",
            "dependency": "R3-D1",
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D5",
            "title": "159612迁移至159655，并向159655新增约¥1.3万–¥1.9万",
            "recommendation": "APPROVE_CONDITIONAL",
            "dependency": "R3-D1",
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D6",
            "title": "两只纯防御债基保持、不新增、不机械削减",
            "recommendation": "APPROVE",
            "dependency": "R3-D1",
            "implementation_ready": False,
        },
        {
            "decision_id": "R3-D7",
            "title": "模拟盘保持现有袖套结构，冻结亏损成长子集新增并保留15%–25%研究现金",
            "recommendation": "APPROVE",
            "default": True,
            "implementation_ready": False,
        },
    ]

    matrix = {
        "matrix_id": "R3_POSITION_ACTION_MATRIX_CURRENT_V1",
        "status": "R3_ACTION_MATRIX_AND_USER_DECISION_PACK_READY_CURRENT_IF_PRESENT_ON_MAIN_NO_IMPLEMENTATION",
        "as_of": AS_OF,
        "accepted_data_watermark": r2["accepted_data_watermark"],
        "position_continuity": "USER_CONFIRMED_THROUGH_2026_07_24_ONLY_LATER_DELTA_CONFIRMATION_REQUIRED",
        "r2_merge_sha": R2_MERGE_SHA,
        "decision_standard": {
            "allowed_actions": ["ADD", "HOLD", "TRIM", "EXIT", "OBSERVE", "WAIT_EVIDENCE"],
            "loss_is_not_an_exit_trigger": True,
            "fresh_mark_and_user_continuity_required_before_implementation": True,
        },
        "real_account": {
            "total_assets_rmb": money(real_total),
            "default_package": "SELF_FUNDED_PHASE_ONE_STRUCTURAL_REPAIR_PURE_DEFENSIVE_UNCHANGED",
            "actions": real_actions,
            "funding_reconciliation": {
                "expected_trim_proceeds_rmb": [money(hybrid_trim[0] + csi_trim[0]), money(hybrid_trim[1] + csi_trim[1])],
                "expected_add_uses_rmb": [money(a500_add[0] + sp500_add[0]), money(a500_add[1] + sp500_add[1])],
                "funding_policy": "Use trim proceeds first; stage additions or use an explicit external transfer only if the user chooses to accelerate. No strategic cash target is introduced.",
            },
        },
        "simulation": {
            "total_assets_rmb": money(sim_total),
            "architecture_action": "MAINTAIN_SLEEVE_STRUCTURE_REPAIR_SECURITY_SELECTION_NOT_WHOLESALE_REBUILD",
            "actions": sim_actions,
            "cash_policy": "KEEP_15_TO_25_PERCENT_RESEARCH_CASH_NO_FORCED_DEPLOYMENT",
        },
        "user_decisions": user_decisions,
        "ready_for_user_decision_count": len(user_decisions),
        "implementation_ready_count": 0,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0},
        "trade_authority": TRADE_AUTHORITY,
    }

    queue = {
        "queue_id": "R3_USER_DECISION_QUEUE_CURRENT_V1",
        "status": "READY_FOR_USER_REVIEW_NOT_IMPLEMENTATION_READY",
        "source_pr": SOURCE_PR,
        "data_watermark": r2["accepted_data_watermark"],
        "continuity_confirmed_through": "2026-07-24",
        "decision_items": user_decisions,
        "ready_for_user_decision_count": len(user_decisions),
        "implementation_ready_count": 0,
        "required_before_any_implementation_proposal": [
            "user selects approve/reject/modify for each relevant decision item",
            "user confirms zero transactions or provides deltas after 2026-07-24",
            "market marks and fund NAV are refreshed to the latest completed close",
            "same-session execution-quality checks pass for ETF migrations",
        ],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }

    real_by_action: dict[str, int] = {}
    sim_by_action: dict[str, int] = {}
    for row in real_actions:
        real_by_action[row["recommended_action"]] = real_by_action.get(row["recommended_action"], 0) + 1
    for row in sim_actions:
        sim_by_action[row["recommended_action"]] = sim_by_action.get(row["recommended_action"], 0) + 1

    acceptance = {
        "acceptance_id": "R3_POSITION_ACTION_MATRIX_ACCEPTANCE_V1",
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
        "source_branch": SOURCE_BRANCH,
        "source_head_sha": str(args.source_head_sha),
        "r2_merge_sha": R2_MERGE_SHA,
        "real_holding_coverage": len(real_actions),
        "simulation_holding_coverage": len(sim_actions),
        "real_action_counts": real_by_action,
        "simulation_action_counts": sim_by_action,
        "ready_for_user_decision_count": len(user_decisions),
        "implementation_ready_count": 0,
        "position_action_matrix_complete": True,
        "user_decision_pack_complete": True,
        "governed_implementation_started": False,
        "next_authorized_step": "USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL",
        "protected_state_hashes": protected_hashes,
        "economic_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0},
        "trade_authority": TRADE_AUTHORITY,
    }

    execution["current_step"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN"
    execution["latest_completed_main_pr"] = 154
    execution["latest_completed_main_merge_sha"] = R2_MERGE_SHA
    execution["latest_governed_merge_sha"] = R2_MERGE_SHA
    execution["github_merge_sha"] = R2_MERGE_SHA
    execution["development_roadmap"]["R2"] = {"status": "COMPLETED_ON_MAIN", "source_pr": 154, "merge_sha": R2_MERGE_SHA}
    execution["development_roadmap"]["R3"] = {"status": "CURRENT_IF_PRESENT_ON_MAIN", "source_pr": SOURCE_PR}
    execution["development_roadmap"]["R4"]["status"] = "NOT_STARTED"
    execution["next_task"] = "USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL"
    execution["overall_status"] = "R3_ACTION_MATRIX_AND_USER_DECISION_PACK_READY_CURRENT_IF_PRESENT_ON_MAIN_NO_IMPLEMENTATION"
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V9_R3_ACTION_MATRIX"
    execution["release_id"] = "INVESTMENT_OS_R19_20260727_R3_ACTION_MATRIX"
    execution["release_sequence"] = 19
    execution["wp5"]["portfolio_construction_synthesis_complete"] = True
    execution["wp5"]["position_action_matrix_complete"] = True
    execution["wp5"]["user_decision_pack_complete"] = True
    execution["wp5"]["ready_for_user_decision_count"] = len(user_decisions)
    execution["wp5"]["implementation_ready_count"] = 0
    execution["wp5"]["status"] = "USER_DECISION_PACK_READY_NO_IMPLEMENTATION"
    execution["wp5"]["r3_source_pr"] = SOURCE_PR
    execution["portfolio_r3"] = {
        "status": "CURRENT_IF_PRESENT_ON_MAIN",
        "real_positions": 7,
        "simulation_positions": 16,
        "decision_items": len(user_decisions),
        "implementation_ready": 0,
    }
    execution["trade_authority"] = TRADE_AUTHORITY

    contract["contract_id"] = "WP5_PORTFOLIO_DECISION_CONTRACT_V3_R3_ACTION_MATRIX"
    contract["fixed_workstreams"]["WP5-4"]["status"] = "COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    contract["fixed_workstreams"]["WP5-4"]["deliverables"] = ["R3_POSITION_ACTION_MATRIX_CURRENT", "R3_USER_DECISION_QUEUE_CURRENT"]
    contract["fixed_workstreams"]["WP5-5"]["status"] = "USER_DECISION_PACK_READY_PENDING_USER_SELECTION"
    contract["current_completion_state"]["position_action_matrix_delivered"] = True
    contract["current_completion_state"]["user_decision_pack_delivered"] = True
    contract["next_task"] = "USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL"
    contract["status"] = "WP5_USER_DECISION_PACK_READY_NO_IMPLEMENTATION"
    contract["current_stage"] = "WP5-5_USER_DECISION_REVIEW"
    contract["next_stage"] = "GOVERNED_IMPLEMENTATION_PROPOSAL_ONLY_AFTER_USER_SELECTION"
    contract["source_pr"] = SOURCE_PR
    contract["source_branch"] = SOURCE_BRANCH
    contract["source_head_sha"] = str(args.source_head_sha)

    asset_specs = [
        ("R3_POSITION_ACTION_MATRIX_CURRENT", "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_POSITION_ACTION_MATRIX_CURRENT.json", "Machine-readable 23-position action matrix"),
        ("R3_USER_DECISION_PACK_CURRENT", "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_PACK_CURRENT.md", "User-readable Real and Simulation decision pack"),
        ("R3_USER_DECISION_QUEUE_CURRENT", "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json", "Seven-item user decision queue"),
        ("R3_POSITION_ACTION_MATRIX_ACCEPTANCE", "investment_os_runtime/00_CONTROL/R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json", "Coverage, lineage and zero-mutation acceptance"),
        ("R3_STATUS_CURRENT", "investment_os_runtime/00_CONTROL/R3_STATUS_CURRENT.md", "Human-readable R3 status"),
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
    registry["active_branch_candidate"] = SOURCE_BRANCH
    registry["registry_status"] = "R3_ACTION_MATRIX_AND_USER_DECISION_PACK_CURRENT_IF_PRESENT_ON_MAIN"
    registry["status"] = "GITHUB_CURRENT_IF_PR155_MERGED_USER_DECISION_PACK_READY_NO_IMPLEMENTATION"

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = master.replace("- 最新已完成main合并：PR #153 / `39cc98578ff0324bb6a5602db527b0dd3e70a278`", f"- 最新已完成main合并：PR #154 / `{R2_MERGE_SHA}`")
    master = master.replace("| WP5 | 组合构建、动作矩阵和用户决策包 | `PARTIALLY_COMPLETE_NO_USER_ACTION_PACK` |", "| WP5 | 组合构建、动作矩阵和用户决策包 | `USER_DECISION_PACK_READY_NO_IMPLEMENTATION` |")
    master = master.replace("- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#154`。", "- 状态：`COMPLETED_ON_MAIN`；来源PR：`#154`。", 1)
    r3_anchor = "### R3｜Position Action Matrix & User Decision Pack\n\n"
    if r3_anchor in master and "- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`。" not in master:
        master = master.replace(r3_anchor, r3_anchor + "- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`。\n\n", 1)
    old_next = "`R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN`"
    master = master.replace(old_next, "`USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL`")
    if "## 十、R3验收结果" not in master:
        master += "\n\n## 十、R3验收结果\n\n- 真实账户7/7、模拟盘16/16形成逐仓动作矩阵。\n- 默认真实账户第一阶段采用自筹资金结构修复：增强债与中证500减持资金转向A500与单一标普500载体。\n- 模拟盘维持袖套结构，冻结沪电、汇川、宁德、工业富联新增资金；研究现金维持15%–25%。\n- 用户决策项7项，Implementation Ready为0；任何持仓、Candidate、旧决策或订单变更均为0。\n"

    summary_lines = [
        "# 股票投资助手｜R3 Position Action Matrix & User Decision Pack CURRENT",
        "",
        "- 状态：`CURRENT_IF_PRESENT_ON_MAIN`",
        "- 来源PR：`#155`",
        f"- R2合并SHA：`{R2_MERGE_SHA}`",
        f"- 数据水位：`{r2['accepted_data_watermark']}`",
        "- 用户持仓连续性：仅确认至`2026-07-24`",
        "- Ready for User Decision：`7`",
        "- Implementation Ready：`0`",
        "- 交易权限：`NONE`",
        "",
        "## 一、默认建议",
        "",
        "真实账户执行第一阶段自筹资金结构修复，纯防御债基保持不变：",
        "",
        "1. 易方达增强回报债券A减持约¥2.4万–¥3.3万；",
        "2. 真实账户中证500ETF减持约¥1.9万–¥2.6万；",
        "3. 南方中证A500ETF增持约¥3万–¥4万；",
        "4. 159612全部条件性迁移至159655，并向159655新增约¥1.3万–¥1.9万；",
        "5. 富国天利与招商安泰保持、不新增、不机械削减。",
        "",
        "该方案优先使用减持资金，不引入战略现金目标；若用户选择加速，可另行明确外部转入，否则分阶段完成。",
        "",
        "## 二、真实账户逐仓矩阵",
        "",
        "| 标的 | 动作 | 目标区间 | 优先级 |",
        "|---|---|---:|---|",
    ]
    for row in real_actions:
        band = f"{row['target_weight_band'][0]*100:.1f}%–{row['target_weight_band'][1]*100:.1f}%"
        summary_lines.append(f"| {row['security_id']} {row['security_name']} | {row['recommended_action']} | {band} | {row['priority']} |")
    summary_lines += [
        "",
        "## 三、模拟盘逐仓矩阵",
        "",
        "| 标的 | 动作 | 当前权重 | 目标区间 |",
        "|---|---|---:|---:|",
    ]
    for row in sim_actions:
        band = f"{row['target_weight_band'][0]*100:.1f}%–{row['target_weight_band'][1]*100:.1f}%"
        summary_lines.append(f"| {row['security_id']} {row['security_name']} | {row['recommended_action']} | {row['current_weight']*100:.2f}% | {band} |")
    summary_lines += [
        "",
        "模拟盘不整体推倒重来；沪电股份、汇川技术、宁德时代和工业富联在证据或估值门槛重新通过前不得新增。福耀玻璃、长江电力、中国海油和中国移动均不追涨。",
        "",
        "## 四、执行前硬门禁",
        "",
        "- 用户确认2026-07-24之后无交易，或完整报告交易Delta；",
        "- 更新至最新完整收盘价和基金净值；",
        "- ETF迁移完成同日成交、价差、折溢价、跟踪和申赎检查；",
        "- 用户逐项批准决策；",
        "- 另行建立Governed Implementation Proposal。",
        "",
        "本R3交付是完整用户决策包，不是订单。",
    ]

    status_text = f"""# 股票投资助手｜R3 CURRENT

- 状态：`CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#155`
- R2合并SHA：`{R2_MERGE_SHA}`
- 真实账户覆盖：`7/7`
- 模拟盘覆盖：`16/16`
- 用户决策项：`7`
- Ready for User Decision：`7`
- Implementation Ready：`0`
- Orders：`0`
- trade_authority：`NONE`

R3已完成逐仓动作矩阵与用户决策包。唯一下一步是用户审阅并选择决策项；未经选择、最新收盘刷新和持仓连续性确认，不得生成实施Proposal。
"""

    write_json(decisions / "R3_POSITION_ACTION_MATRIX_CURRENT.json", matrix)
    write_text(decisions / "R3_USER_DECISION_PACK_CURRENT.md", "\n".join(summary_lines))
    write_json(decisions / "R3_USER_DECISION_QUEUE_CURRENT.json", queue)
    write_json(control / "R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json", acceptance)
    write_text(control / "R3_STATUS_CURRENT.md", status_text)
    write_json(control / "EXECUTION_REGISTER_CURRENT.json", execution)
    write_json(control / "WP5_PORTFOLIO_DECISION_CONTRACT.json", contract)
    write_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json", registry)
    write_text(master_path, master)

    print({
        "real": len(real_actions),
        "simulation": len(sim_actions),
        "decision_items": len(user_decisions),
        "implementation_ready": 0,
        "mutations": 0,
        "orders": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
