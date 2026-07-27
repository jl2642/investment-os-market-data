from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SOURCE_PR = 157
SOURCE_BRANCH = "agent/r3-development-boundary-correction"
R3_MERGE_SHA = "8682e4ae8ecd5860e1957efc12ba50645767c545"
TRADE_AUTHORITY = "NONE"
NEXT_STAGE = "R4_OPERATING_PRODUCTS_DEVELOPMENT"
SCENARIO_COUNT = 7


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    control = root / "investment_os_runtime/00_CONTROL"
    decisions = root / "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS"
    source_head = str(args.source_head_sha)

    matrix_path = decisions / "R3_POSITION_ACTION_MATRIX_CURRENT.json"
    matrix = read_json(matrix_path)
    matrix.update({
        "status": "R3_DEVELOPMENT_PRODUCT_COMPLETE_NO_OPERATING_ACTIVATION",
        "development_mode": True,
        "operating_activation": False,
        "decision_pack_role": "DEVELOPMENT_ACCEPTANCE_SAMPLE_NOT_LIVE_ACTION_REQUEST",
        "development_decision_scenario_count": SCENARIO_COUNT,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "next_stage": NEXT_STAGE,
    })
    for section in ("real_account", "simulation"):
        for row in matrix[section]["actions"]:
            row.update({
                "development_scenario_only": True,
                "ready_for_user_decision": False,
                "operating_activation_required_before_use": True,
                "implementation_ready": False,
                "position_change_authorized": False,
                "order_authorized": False,
            })
    for row in matrix.get("user_decisions", []):
        row.update({"development_scenario_only": True, "approval_required_now": False, "implementation_ready": False})
    write_json(matrix_path, matrix)

    queue_path = decisions / "R3_USER_DECISION_QUEUE_CURRENT.json"
    queue = read_json(queue_path)
    queue.update({
        "status": "DEVELOPMENT_SCENARIO_LIBRARY_NOT_LIVE_USER_QUEUE",
        "development_mode": True,
        "operating_activation": False,
        "development_decision_scenario_count": SCENARIO_COUNT,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "next_stage": NEXT_STAGE,
        "required_before_any_implementation_proposal": [
            "R4 operating products are complete",
            "R5 attribution and calibration are complete",
            "R6 production acceptance passes",
            "the system is explicitly activated for operating observation",
            "a fresh live decision pack is regenerated from then-current positions, marks and evidence",
            "the user explicitly approves that future live decision pack",
        ],
    })
    for row in queue["decision_items"]:
        row.update({"development_scenario_only": True, "approval_required_now": False, "implementation_ready": False})
    write_json(queue_path, queue)

    pack_path = decisions / "R3_USER_DECISION_PACK_CURRENT.md"
    pack = pack_path.read_text(encoding="utf-8")
    notice = "> **开发阶段说明**：以下7项仅用于验证系统能否形成完整决策包，不是当前真实调仓请求。现阶段用户无需批准、拒绝或执行任何一项。系统应继续完成R4、R5、R6；R6生产验收通过并明确进入运营观察期后，再基于届时真实持仓、模拟盘、最新行情和证据重新生成正式决策包。\n\n"
    if notice not in pack:
        pack = pack.replace("# 股票投资助手｜R3 Position Action Matrix & User Decision Pack CURRENT\n\n", "# 股票投资助手｜R3 Position Action Matrix & User Decision Pack CURRENT\n\n" + notice, 1)
    pack = pack.replace("- Ready for User Decision：`7`", "- 开发验收决策场景：`7`\n- 当前Ready for User Decision：`0`")
    pack = pack.replace("## 四、执行前硬门禁", "## 四、未来运营激活与执行前硬门禁")
    pack = pack.replace("- 用户逐项批准决策；", "- R4、R5、R6开发与生产验收全部完成；\n- 系统被明确激活进入运营观察期；\n- 届时重新刷新持仓、行情和研究证据；\n- 用户对重新生成的正式决策包逐项批准；")
    pack = pack.replace("本R3交付是完整用户决策包，不是订单。", "本R3交付是开发验收产品，不是当前行动请求，更不是订单。下一阶段为`R4_OPERATING_PRODUCTS_DEVELOPMENT`。")
    write_text(pack_path, pack)

    status_path = control / "R3_STATUS_CURRENT.md"
    write_text(status_path, f"""# 股票投资助手｜R3 CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN`
- 来源PR：`#155`
- 合并SHA：`{R3_MERGE_SHA}`
- 真实账户覆盖：`7/7`
- 模拟盘覆盖：`16/16`
- 开发验收决策场景：`7`
- 当前Ready for User Decision：`0`
- Implementation Ready：`0`
- Operating Activation：`false`
- Orders：`0`
- trade_authority：`NONE`
- 下一阶段：`{NEXT_STAGE}`

R3只证明系统已具备形成逐仓动作矩阵与用户决策包的能力。当前仍处于开发阶段，不要求用户批准或执行真实账户、模拟盘动作。R4、R5、R6完成并通过生产验收后，才进入运营观察期。
""")

    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    execution = read_json(execution_path)
    execution["development_roadmap"]["R3"] = {"status": "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN", "source_pr": 155, "merge_sha": R3_MERGE_SHA}
    execution["development_roadmap"]["R4"]["status"] = "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
    execution["next_task"] = NEXT_STAGE
    execution["overall_status"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE_NO_OPERATING_ACTIVATION_R4_NEXT"
    execution["portfolio_r3"] = {
        "status": "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN",
        "real_positions": 7,
        "simulation_positions": 16,
        "development_decision_scenarios": SCENARIO_COUNT,
        "ready_for_user_decision": 0,
        "implementation_ready": 0,
        "operating_activation": False,
        "next_stage": NEXT_STAGE,
    }
    wp5 = execution["wp5"]
    wp5.update({
        "branch": SOURCE_BRANCH,
        "source_pr": SOURCE_PR,
        "source_head_sha": source_head,
        "status": "R3_DEVELOPMENT_PRODUCT_COMPLETE_R4_NEXT_NO_OPERATING_ACTIVATION",
        "reason": "R3_CAPABILITY_ACCEPTED_OPERATING_ACTIVATION_DEFERRED_UNTIL_R6",
        "next_gate": NEXT_STAGE,
        "development_decision_scenario_count": SCENARIO_COUNT,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "operating_activation": False,
        "position_mutation_allowed": False,
        "order_execution_allowed": False,
        "trade_authority": TRADE_AUTHORITY,
    })
    write_json(execution_path, execution)

    contract_path = control / "WP5_PORTFOLIO_DECISION_CONTRACT.json"
    contract = read_json(contract_path)
    contract["fixed_workstreams"]["WP5-4"]["status"] = "DEVELOPMENT_PRODUCT_COMPLETE_ON_MAIN"
    contract["fixed_workstreams"]["WP5-4"]["source_pr"] = 155
    contract["fixed_workstreams"]["WP5-4"]["merge_sha"] = R3_MERGE_SHA
    contract["fixed_workstreams"]["WP5-5"]["status"] = "DEVELOPMENT_INTERFACE_COMPLETE_OPERATING_ACTIVATION_DEFERRED_UNTIL_R6"
    contract.update({
        "current_stage": "R3_DEVELOPMENT_PRODUCT_COMPLETE",
        "next_stage": NEXT_STAGE,
        "next_task": NEXT_STAGE,
        "source_branch": SOURCE_BRANCH,
        "source_pr": SOURCE_PR,
        "source_head_sha": source_head,
        "development_decision_scenario_count": SCENARIO_COUNT,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "operating_activation": False,
        "status": "R3_DEVELOPMENT_PRODUCT_COMPLETE_R4_NEXT_NO_OPERATING_ACTIVATION",
        "trade_authority": TRADE_AUTHORITY,
    })
    write_json(contract_path, contract)

    acceptance_path = control / "R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json"
    acceptance = read_json(acceptance_path)
    acceptance.update({
        "status": "DEVELOPMENT_PRODUCT_ACCEPTED_ON_MAIN",
        "development_stage": True,
        "operating_activation": False,
        "development_decision_scenario_count": SCENARIO_COUNT,
        "ready_for_user_decision_count": 0,
        "implementation_ready_count": 0,
        "next_authorized_step": NEXT_STAGE,
        "source_pr": 155,
        "merge_sha": R3_MERGE_SHA,
    })
    write_json(acceptance_path, acceptance)

    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    registry = read_json(registry_path)
    registry.update({
        "github_merge_sha": R3_MERGE_SHA,
        "latest_completed_main_merge_sha": R3_MERGE_SHA,
        "latest_completed_main_pr": 155,
        "latest_governed_merge_sha": R3_MERGE_SHA,
        "registry_id": "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V13_R3_DEVELOPMENT_PRODUCT",
        "registry_status": "R3_DEVELOPMENT_PRODUCT_ON_MAIN_R4_NEXT",
        "status": "R3_DEVELOPMENT_PRODUCT_CURRENT_NO_OPERATING_ACTIVATION",
    })
    for row in registry["assets"]:
        if row.get("asset_id") == "GITHUB_ACTIVE_RUNTIME":
            row.update({"branch_candidate": SOURCE_BRANCH, "latest_governed_merge_sha": R3_MERGE_SHA, "status": "GITHUB_MAIN_PR155_R3_DEVELOPMENT_PRODUCT_PR157_CORRECTION_CANDIDATE"})
        if row.get("asset_id", "").startswith("R3_"):
            row.update({"development_product": True, "operating_activation": False})
    write_json(registry_path, registry)

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = master.replace("`USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL`", f"`{NEXT_STAGE}`")
    if "R3仅为开发验收产品" not in master:
        master += f"\n\n## R3阶段边界纠正\n\n- R3仅为开发验收产品，7项决策为能力验证场景，不构成当前真实调仓请求。\n- 当前Ready for User Decision为`0`，Implementation Ready为`0`，Operating Activation为`false`。\n- 下一阶段固定为`{NEXT_STAGE}`；R4、R5、R6完成并通过生产验收后，才进入运营观察期。\n"
    write_text(master_path, master)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
