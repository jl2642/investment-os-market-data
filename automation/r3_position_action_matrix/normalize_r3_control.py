from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

R2_MERGE_SHA = "fc57e7a08fee6870130871e8491bb2db59b70e54"
SOURCE_PR = 155
SOURCE_BRANCH = "agent/r3-position-action-matrix"
TRADE_AUTHORITY = "NONE"
NEXT_STAGE = "R4_OPERATING_PRODUCTS_DEVELOPMENT"
DEVELOPMENT_SCENARIO_COUNT = 7


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
    matrix["status"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_OPERATING_ACTIVATION"
    matrix["development_mode"] = True
    matrix["operating_activation"] = False
    matrix["decision_pack_role"] = "DEVELOPMENT_ACCEPTANCE_SAMPLE_NOT_LIVE_ACTION_REQUEST"
    matrix["development_decision_scenario_count"] = DEVELOPMENT_SCENARIO_COUNT
    matrix["ready_for_user_decision_count"] = 0
    matrix["implementation_ready_count"] = 0
    matrix["next_stage"] = NEXT_STAGE
    for section in ("real_account", "simulation"):
        for row in matrix[section]["actions"]:
            row["ready_for_user_decision"] = False
            row["development_scenario_only"] = True
            row["operating_activation_required_before_use"] = True
    for row in matrix.get("user_decisions", []):
        row["development_scenario_only"] = True
        row["approval_required_now"] = False
        row["implementation_ready"] = False
    write_json(matrix_path, matrix)

    queue_path = decisions / "R3_USER_DECISION_QUEUE_CURRENT.json"
    queue = read_json(queue_path)
    queue["status"] = "DEVELOPMENT_SCENARIO_LIBRARY_NOT_LIVE_USER_QUEUE"
    queue["development_mode"] = True
    queue["operating_activation"] = False
    queue["development_decision_scenario_count"] = DEVELOPMENT_SCENARIO_COUNT
    queue["ready_for_user_decision_count"] = 0
    queue["implementation_ready_count"] = 0
    queue["next_stage"] = NEXT_STAGE
    queue["required_before_any_implementation_proposal"] = [
        "R4 operating products are completed",
        "R5 attribution and calibration are completed",
        "R6 production acceptance passes",
        "the system is explicitly activated for operating observation",
        "the user later confirms current positions and approves a newly refreshed live decision pack",
    ]
    for row in queue.get("decision_items", []):
        row["development_scenario_only"] = True
        row["approval_required_now"] = False
        row["implementation_ready"] = False
    write_json(queue_path, queue)

    pack_path = decisions / "R3_USER_DECISION_PACK_CURRENT.md"
    pack = pack_path.read_text(encoding="utf-8")
    notice = "> **开发阶段说明**：本文件用于验证股票投资助手能否生成完整逐仓动作矩阵和用户决策包。以下7项均为开发验收样例，不是当前真实调仓请求；现阶段用户无需批准、拒绝或执行任何一项。系统下一步是R4、R5、R6开发与生产验收，R6通过并明确进入运营观察期后，才会基于届时真实持仓和最新行情重新生成正式决策包。\n\n"
    if "> **开发阶段说明**" not in pack:
        pack = pack.replace("# 股票投资助手｜R3 Position Action Matrix & User Decision Pack CURRENT\n\n", "# 股票投资助手｜R3 Position Action Matrix & User Decision Pack CURRENT\n\n" + notice, 1)
    pack = pack.replace("- Ready for User Decision：`7`", "- 开发验收决策场景：`7`\n- 当前Ready for User Decision：`0`")
    pack = pack.replace("## 四、执行前硬门禁", "## 四、未来运营激活与执行前硬门禁")
    pack = pack.replace("- 用户逐项批准决策；", "- R4、R5、R6开发与生产验收全部完成；\n- 系统被明确激活进入运营观察期；\n- 届时重新刷新真实持仓、模拟盘、行情与研究证据；\n- 用户对重新生成的正式决策包逐项批准；")
    pack = pack.replace("本R3交付是完整用户决策包，不是订单。", "本R3交付是开发验收产品，不是当前用户行动请求，更不是订单。下一阶段为`R4_OPERATING_PRODUCTS_DEVELOPMENT`。")
    write_text(pack_path, pack)

    status_path = control / "R3_STATUS_CURRENT.md"
    write_text(status_path, f"""# 股票投资助手｜R3 CURRENT

- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN`
- 来源PR：`#155`
- R2合并SHA：`{R2_MERGE_SHA}`
- 真实账户覆盖：`7/7`
- 模拟盘覆盖：`16/16`
- 开发验收决策场景：`7`
- 当前Ready for User Decision：`0`
- Implementation Ready：`0`
- Operating Activation：`false`
- Orders：`0`
- trade_authority：`NONE`
- 下一阶段：`{NEXT_STAGE}`

R3已验证系统能够生成完整逐仓动作矩阵与用户决策包。该产品仅用于开发验收，当前不要求用户批准或执行任何真实账户、模拟盘动作。R4、R5、R6完成并通过生产验收后，系统才可被明确激活进入运营观察期；正式投资建议必须届时基于最新持仓、最新行情和重新刷新后的研究证据生成。
""")

    execution_path = control / "EXECUTION_REGISTER_CURRENT.json"
    execution = read_json(execution_path)
    execution["portfolio_r2"] = {
        "status": "COMPLETED_ON_MAIN",
        "source_pr": 154,
        "merge_sha": R2_MERGE_SHA,
        "real_reference_architectures": 3,
        "simulation_sleeves": 6,
        "r3_started": True,
    }
    execution["development_roadmap"]["R3"] = {
        "status": "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN",
        "source_pr": SOURCE_PR,
    }
    execution["development_roadmap"]["R4"]["status"] = "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
    execution["next_task"] = NEXT_STAGE
    execution["overall_status"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE_NO_OPERATING_ACTIVATION_R4_NEXT"
    execution["portfolio_r3"] = {
        "status": "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN",
        "real_positions": 7,
        "simulation_positions": 16,
        "development_decision_scenarios": DEVELOPMENT_SCENARIO_COUNT,
        "ready_for_user_decision": 0,
        "implementation_ready": 0,
        "operating_activation": False,
        "next_stage": NEXT_STAGE,
    }
    wp5 = execution["wp5"]
    wp5["branch"] = SOURCE_BRANCH
    wp5["source_pr"] = SOURCE_PR
    wp5["source_head_sha"] = source_head
    wp5["reason"] = "R3_DEVELOPMENT_CAPABILITY_ACCEPTED_OPERATING_ACTIVATION_DEFERRED_UNTIL_R6"
    wp5["next_gate"] = NEXT_STAGE
    wp5["user_decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    wp5["r3_action_matrix_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_POSITION_ACTION_MATRIX_CURRENT.json"
    wp5["r3_user_decision_pack_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_PACK_CURRENT.md"
    wp5["development_decision_scenario_count"] = DEVELOPMENT_SCENARIO_COUNT
    wp5["ready_for_user_decision_count"] = 0
    wp5["implementation_ready_count"] = 0
    wp5["operating_activation"] = False
    wp5["position_mutation_allowed"] = False
    wp5["order_execution_allowed"] = False
    wp5["status"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE_R4_NEXT_NO_OPERATING_ACTIVATION"
    wp5["trade_authority"] = TRADE_AUTHORITY
    write_json(execution_path, execution)

    contract_path = control / "WP5_PORTFOLIO_DECISION_CONTRACT.json"
    contract = read_json(contract_path)
    contract["fixed_workstreams"]["WP5-3"]["status"] = "COMPLETED_ON_MAIN"
    contract["fixed_workstreams"]["WP5-3"]["source_pr"] = 154
    contract["fixed_workstreams"]["WP5-3"]["merge_sha"] = R2_MERGE_SHA
    contract["fixed_workstreams"]["WP5-4"]["status"] = "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    contract["fixed_workstreams"]["WP5-4"]["source_pr"] = SOURCE_PR
    contract["fixed_workstreams"]["WP5-5"]["status"] = "DEVELOPMENT_INTERFACE_COMPLETE_OPERATING_ACTIVATION_DEFERRED_UNTIL_R6"
    contract["current_stage"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE"
    contract["next_stage"] = NEXT_STAGE
    contract["next_task"] = NEXT_STAGE
    contract["source_head_sha"] = source_head
    contract["decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    contract["position_action_matrix_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_POSITION_ACTION_MATRIX_CURRENT.json"
    contract["user_decision_pack_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_PACK_CURRENT.md"
    contract["development_decision_scenario_count"] = DEVELOPMENT_SCENARIO_COUNT
    contract["ready_for_user_decision_count"] = 0
    contract["implementation_ready_count"] = 0
    contract["operating_activation"] = False
    contract["status"] = "R3_DEVELOPMENT_PRODUCT_COMPLETE_R4_NEXT_NO_OPERATING_ACTIVATION"
    contract["trade_authority"] = TRADE_AUTHORITY
    write_json(contract_path, contract)

    registry_path = control / "AUTHORITATIVE_ASSET_REGISTRY.json"
    registry = read_json(registry_path)
    registry["github_merge_sha"] = R2_MERGE_SHA
    registry["latest_completed_main_merge_sha"] = R2_MERGE_SHA
    registry["latest_completed_main_pr"] = 154
    registry["latest_governed_merge_sha"] = R2_MERGE_SHA
    registry["registry_id"] = "INVESTMENT_ASSISTANT_AUTHORITATIVE_ASSET_REGISTRY_V13_R3_DEVELOPMENT_PRODUCT"
    registry["release_id"] = "INVESTMENT_OS_R19_20260727_R3_DEVELOPMENT_PRODUCT"
    registry["release_sequence"] = 19
    registry["registry_status"] = "R3_DEVELOPMENT_PRODUCT_CURRENT_IF_PRESENT_ON_MAIN_R4_NEXT"
    registry["status"] = "GITHUB_MAIN_PR154_CURRENT_PR155_R3_DEVELOPMENT_CANDIDATE_NO_OPERATING_ACTIVATION"
    for row in registry.get("assets", []):
        asset_id = row.get("asset_id")
        if asset_id == "GITHUB_ACTIVE_RUNTIME":
            row["branch_candidate"] = SOURCE_BRANCH
            row["latest_governed_merge_sha"] = R2_MERGE_SHA
            row["role"] = "RULE_STATE_RESEARCH_DECISION_OPERATIONS_AND_CONTROL_RUNTIME"
            row["status"] = "GITHUB_MAIN_PR154_CURRENT_PR155_R3_DEVELOPMENT_CANDIDATE"
        if asset_id and asset_id.startswith("R2_PORTFOLIO_CONSTRUCTION_"):
            row["status"] = "COMPLETED_ON_MAIN"
            row["merge_sha"] = R2_MERGE_SHA
        if asset_id in {
            "R3_POSITION_ACTION_MATRIX_CURRENT",
            "R3_USER_DECISION_PACK_CURRENT",
            "R3_USER_DECISION_QUEUE_CURRENT",
            "R3_POSITION_ACTION_MATRIX_ACCEPTANCE",
            "R3_STATUS_CURRENT",
        }:
            row["source_head_sha"] = source_head
            row["operating_activation"] = False
            row["development_product"] = True
    write_json(registry_path, registry)

    acceptance_path = control / "R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json"
    acceptance = read_json(acceptance_path)
    acceptance["source_head_sha"] = source_head
    acceptance["control_metadata_normalized"] = True
    acceptance["development_stage"] = True
    acceptance["operating_activation"] = False
    acceptance["development_decision_scenario_count"] = DEVELOPMENT_SCENARIO_COUNT
    acceptance["ready_for_user_decision_count"] = 0
    acceptance["implementation_ready_count"] = 0
    acceptance["r2_registry_status"] = "COMPLETED_ON_MAIN"
    acceptance["decision_queue_path"] = "investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R3_USER_DECISION_QUEUE_CURRENT.json"
    acceptance["next_authorized_step"] = NEXT_STAGE
    write_json(acceptance_path, acceptance)

    master_path = control / "WORK_PACKAGE_MASTER_PLAN_CURRENT.md"
    master = master_path.read_text(encoding="utf-8")
    master = master.replace("`USER_REVIEW_R3_DECISION_PACK_BEFORE_ANY_IMPLEMENTATION_PROPOSAL`", f"`{NEXT_STAGE}`")
    master = master.replace("- 状态：`CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`。", "- 状态：`DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN`；来源PR：`#155`；Operating Activation：`false`。")
    if "R3仅为开发验收产品" not in master:
        master += f"\n\n## R3阶段边界纠正\n\n- R3仅为开发验收产品，7项决策为能力验证场景，不构成当前真实调仓请求。\n- 当前Ready for User Decision为`0`，Implementation Ready为`0`，Operating Activation为`false`。\n- 下一阶段固定为`{NEXT_STAGE}`；R4、R5、R6完成并通过生产验收后，才进入运营观察期。\n"
    write_text(master_path, master)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
