from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path("automation/r1_decision_coverage/build_r1_decision_coverage.py")
BRANCH = "agent/r4-operating-products"
BUILDER = Path("automation/r4_operating_products/build_r4_operating_products.py")
LINEAGE = Path("automation/r4_operating_products/patch_forward_lineage.py")
VALIDATOR = Path("automation/r4_operating_products/validate_r4_operating_products.py")


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-head-sha", required=False)
    parser.parse_args()

    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    run("python", str(BUILDER), "--repo-root", ".", "--source-head-sha", source_head)
    run("python", str(LINEAGE))

    run("git", "fetch", "origin", "main")
    original = subprocess.check_output(["git", "show", f"origin/main:{SELF.as_posix()}"], cwd=ROOT)
    (ROOT / SELF).write_bytes(original)

    run("python", str(VALIDATOR))

    paths = [
        SELF,
        Path("automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"),
        Path("investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json"),
        Path("investment_os_runtime/00_CONTROL/CAPABILITY_REALITY_MATRIX_CURRENT.md"),
        Path("investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json"),
        Path("investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json"),
        Path("investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json"),
        Path("investment_os_runtime/00_CONTROL/R4_STATUS_CURRENT.md"),
        Path("investment_os_runtime/00_CONTROL/USER_OPERATING_GUIDE_CURRENT.md"),
        Path("investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/R4_OPERATING_PRODUCT_CATALOG_CURRENT.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_UNIFIED_OPERATING_STATUS_SAMPLE.json"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_DAILY_OPERATING_BRIEF_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_WEEKLY_OPERATING_REVIEW_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_QUARTERLY_PORTFOLIO_REVIEW_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_ANNUAL_STRATEGY_REVIEW_SAMPLE.md"),
        Path("investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_EVENT_ALERT_SAMPLE.md"),
    ]
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", *[str(path) for path in paths])
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return 0
    run("git", "commit", "-m", "R4 materialize operating product system and development samples")
    run("git", "pull", "--rebase", "origin", BRANCH)
    run("git", "push", "origin", f"HEAD:{BRANCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
