from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path("automation/r1_decision_coverage/build_r1_decision_coverage.py")
R2_BUILDER = Path("automation/r2_portfolio_construction/build_r2_portfolio_construction.py")
BRANCH = "agent/r2-portfolio-construction-synthesis"


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def patch_r2_builder() -> None:
    path = ROOT / R2_BUILDER
    text = path.read_text(encoding="utf-8")

    old_execution = '''    execution["next_task"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    execution.setdefault("development_roadmap", {})["R1"] = {"status": "COMPLETED_ON_MAIN", "source_pr": 153, "merge_sha": R1_MERGE_SHA}
'''
    new_execution = '''    execution["next_task"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    execution["overall_status"] = "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_R3_NOT_STARTED"
    execution["register_id"] = "INVESTMENT_ASSISTANT_EXECUTION_REGISTER_V8_R2_PORTFOLIO_CONSTRUCTION"
    execution["release_id"] = "INVESTMENT_OS_R18_20260727_R2_PORTFOLIO_CONSTRUCTION"
    execution["release_sequence"] = 18
    execution.setdefault("r1_decision_coverage", {})["status"] = "COMPLETED_ON_MAIN"
    execution["r1_decision_coverage"]["merge_sha"] = R1_MERGE_SHA
    execution.setdefault("development_roadmap", {})["R1"] = {"status": "COMPLETED_ON_MAIN", "source_pr": 153, "merge_sha": R1_MERGE_SHA}
'''
    if new_execution not in text:
        if old_execution not in text:
            raise SystemExit("R2_EXECUTION_ALIGNMENT_INSERTION_POINT_NOT_FOUND")
        text = text.replace(old_execution, new_execution, 1)

    old_contract = '''    contract["current_stage"] = "WP5-3_COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    contract["next_stage"] = "WP5-4_POSITION_ACTION_MATRIX"
    contract["trade_authority"] = "NONE"
'''
    new_contract = '''    contract["current_stage"] = "WP5-3_COMPLETED_CURRENT_IF_PRESENT_ON_MAIN"
    contract["next_stage"] = "WP5-4_POSITION_ACTION_MATRIX"
    contract["next_task"] = "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    contract["status"] = "WP5_3_PORTFOLIO_CONSTRUCTION_SYNTHESIS_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    contract["source_pr"] = SOURCE_PR
    contract["source_branch"] = SOURCE_BRANCH
    contract["source_head_sha"] = "GOVERNED_PR154_MATERIALIZATION"
    contract["trade_authority"] = "NONE"
'''
    if new_contract not in text:
        if old_contract not in text:
            raise SystemExit("R2_CONTRACT_ALIGNMENT_INSERTION_POINT_NOT_FOUND")
        text = text.replace(old_contract, new_contract, 1)

    path.write_text(text, encoding="utf-8")


def restore_self() -> None:
    run("git", "fetch", "origin", "main")
    original = subprocess.check_output(
        ["git", "show", f"origin/main:{SELF.as_posix()}"], cwd=ROOT
    )
    (ROOT / SELF).write_bytes(original)


def publish() -> None:
    paths = [
        SELF,
        R2_BUILDER,
        Path("investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"),
        Path("investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"),
        Path("investment_os_runtime/00_CONTROL/R2_PORTFOLIO_CONSTRUCTION_ACCEPTANCE_RECORD.json"),
        Path("investment_os_runtime/00_CONTROL/R2_STATUS_CURRENT.md"),
        Path("investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"),
        Path("investment_os_runtime/00_CONTROL/WP5_PORTFOLIO_DECISION_CONTRACT.json"),
        Path("investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT.json"),
        Path("investment_os_runtime/30_STATE_CURRENT/60_DECISIONS/R2_PORTFOLIO_CONSTRUCTION_SUMMARY_CURRENT.md"),
    ]
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", *[str(path) for path in paths])
    cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if cached.returncode == 0:
        return
    run("git", "commit", "-m", "R2 align authoritative portfolio-construction status")
    target = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or BRANCH
    run("git", "push", "origin", f"HEAD:{target}")


def main() -> None:
    patch_r2_builder()
    run(sys.executable, str(R2_BUILDER))
    restore_self()
    publish()


if __name__ == "__main__":
    main()
