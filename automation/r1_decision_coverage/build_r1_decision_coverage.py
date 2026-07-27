from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path("automation/r1_decision_coverage/build_r1_decision_coverage.py")
BRANCH = "agent/r3-position-action-matrix"
NORMALIZER = Path("automation/r3_position_action_matrix/normalize_r3_control.py")


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=False)
    parser.parse_args()

    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    run("python", str(NORMALIZER), "--repo-root", ".", "--source-head-sha", source_head)

    run("git", "fetch", "origin", "main")
    original = subprocess.check_output(["git", "show", f"origin/main:{SELF.as_posix()}"], cwd=ROOT)
    (ROOT / SELF).write_bytes(original)

    paths = [
        SELF,
        Path("investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"),
        Path("investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"),
        Path("investment_os_runtime/00_CONTROL/R3_POSITION_ACTION_MATRIX_ACCEPTANCE_RECORD.json"),
        Path("investment_os_runtime/00_CONTROL/WP5_PORTFOLIO_DECISION_CONTRACT.json"),
    ]
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", *[str(path) for path in paths])
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return 0
    run("git", "commit", "-m", "R3 normalize authoritative control metadata")
    run("git", "pull", "--rebase", "origin", BRANCH)
    run("git", "push", "origin", f"HEAD:{BRANCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
