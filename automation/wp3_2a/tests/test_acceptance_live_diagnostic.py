from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROPOSAL = (
    "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/PROPOSALS/"
    "WP3_2A_UNIVERSE_PROPOSAL_20260724_30162751251_1"
)
THIS_TEST = "automation/wp3_2a/tests/test_acceptance_live_diagnostic.py"


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    return proc.returncode, proc.stdout


def tail(text: str, lines: int = 120) -> str:
    return "\n".join(text.splitlines()[-lines:])


def test_protected_acceptance_regression_diagnostic(tmp_path: Path) -> None:
    worktree = tmp_path / "acceptance-worktree"
    add = subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(worktree), "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert add.returncode == 0, add.stdout

    results: list[tuple[str, int, str]] = []
    try:
        results.append(
            (
                "stage_acceptance",
                *run(
                    [
                        sys.executable,
                        "automation/wp3_2a/accept_data_proposal.py",
                        "--repo-root",
                        ".",
                        "--proposal-path",
                        PROPOSAL,
                        "--confirmation",
                        "ACCEPT_UNIVERSE_PROPOSAL",
                        "--config",
                        "automation/wp3_2a/config.json",
                    ],
                    worktree,
                ),
            )
        )
        results.append(
            (
                "automation_self_test",
                *run(
                    [sys.executable, "automation/wp3_2a/self_test.py", "--repo-root", "."],
                    worktree,
                ),
            )
        )
        results.append(
            (
                "automation_pytest",
                *run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "automation/wp3_2a/tests",
                        f"--ignore={THIS_TEST}",
                    ],
                    worktree,
                ),
            )
        )
        runtime = worktree / "investment_os_runtime/80_EXECUTABLE_RUNTIME"
        results.append(
            (
                "runtime_requirements",
                *run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--retries",
                        "5",
                        "--timeout",
                        "30",
                        "-r",
                        "requirements.lock",
                    ],
                    runtime,
                ),
            )
        )
        results.append(
            (
                "runtime_pytest",
                *run([sys.executable, "-m", "pytest", "-q"], runtime),
            )
        )
    finally:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(worktree)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        shutil.rmtree(worktree, ignore_errors=True)

    failures = [(name, rc, output) for name, rc, output in results if rc != 0]
    if failures:
        report = [
            "WP3-2A protected acceptance diagnostic failed.",
            "trade_authority=NONE",
            "",
        ]
        for name, rc, output in results:
            report.extend(
                [
                    f"===== {name} rc={rc} =====",
                    tail(output),
                    "",
                ]
            )
        raise AssertionError("\n".join(report))
