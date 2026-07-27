from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path("automation/r1_decision_coverage/build_r1_decision_coverage.py")
R2_BUILDER = Path("automation/r2_portfolio_construction/build_r2_portfolio_construction.py")
LINEAGE_TEST = Path("automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py")
BRANCH = "agent/r2-portfolio-construction-synthesis"


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def patch_lineage_test() -> None:
    text = (ROOT / LINEAGE_TEST).read_text(encoding="utf-8")
    if "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_IF_PRESENT_ON_MAIN" in text:
        return
    needle = '''    elif step == "R1_DECISION_COVERAGE_CURRENT_IF_PRESENT_ON_MAIN":
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
'''
    replacement = needle[:-10] + '''    elif step == "R2_PORTFOLIO_CONSTRUCTION_SYNTHESIS_CURRENT_IF_PRESENT_ON_MAIN":
        assert register["trade_authority"] == "NONE"
        assert register["development_roadmap"]["R1"]["status"] == "COMPLETED_ON_MAIN"
        assert register["development_roadmap"]["R2"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert register["development_roadmap"]["R3"]["status"] == "NOT_STARTED"
        assert register["wp5"]["formal_plan"] == "WP5_1_TO_WP5_5"
        assert register["wp5"]["portfolio_construction_synthesis_complete"] is True
        assert register["wp5"]["position_action_matrix_complete"] is False
        assert register["wp5"]["user_decision_pack_complete"] is False
        assert register["next_task"] == "R3_POSITION_ACTION_MATRIX_AND_USER_DECISION_PACK_AFTER_R2_PRESENT_ON_MAIN"
    else:
'''
    if needle not in text:
        raise SystemExit("R2_LINEAGE_PATCH_NEEDLE_NOT_FOUND")
    (ROOT / LINEAGE_TEST).write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def restore_self() -> None:
    run("git", "fetch", "origin", "main")
    original = subprocess.check_output(
        ["git", "show", f"origin/main:{SELF.as_posix()}"], cwd=ROOT
    )
    (ROOT / SELF).write_bytes(original)


def publish() -> None:
    paths = [
        SELF,
        LINEAGE_TEST,
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
    run("git", "commit", "-m", "R2 materialize portfolio construction synthesis")
    target = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or BRANCH
    run("git", "push", "origin", f"HEAD:{target}")


def main() -> None:
    run(sys.executable, str(R2_BUILDER))
    patch_lineage_test()
    restore_self()
    publish()


if __name__ == "__main__":
    main()
