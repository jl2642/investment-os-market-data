from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path("automation/r1_decision_coverage/build_r1_decision_coverage.py")
BRANCH = "agent/r4-operating-products"
NORMALIZER = Path("automation/r4_operating_products/normalize_r4_samples.py")
VALIDATOR = Path("automation/r4_operating_products/validate_r4_operating_products.py")


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=False)
    parser.parse_args()

    run("python", str(NORMALIZER))
    run("git", "fetch", "origin", "main")
    original = subprocess.check_output(["git", "show", f"origin/main:{SELF.as_posix()}"], cwd=ROOT)
    (ROOT / SELF).write_bytes(original)
    run("python", str(VALIDATOR))

    paths = [
        SELF,
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_UNIFIED_OPERATING_STATUS_SAMPLE.json"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_DAILY_OPERATING_BRIEF_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md"),
    ]
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", *[str(path) for path in paths])
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return 0
    run("git", "commit", "-m", "R4 normalize simulation cash and unrealized PnL in samples")
    run("git", "pull", "--rebase", "origin", BRANCH)
    run("git", "push", "origin", f"HEAD:{BRANCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
