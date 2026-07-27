from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    control = root / "investment_os_runtime/00_CONTROL"
    state = root / "investment_os_runtime/30_STATE_CURRENT"
    products = root / "investment_os_runtime/50_OPERATING_PRODUCTS"
    samples = products / "DEVELOPMENT_SAMPLES"

    contract = read_json(control / "R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json")
    acceptance = read_json(control / "R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json")
    execution = read_json(control / "EXECUTION_REGISTER_CURRENT.json")
    registry = read_json(control / "AUTHORITATIVE_ASSET_REGISTRY.json")
    unified = read_json(samples / "R4_UNIFIED_OPERATING_STATUS_SAMPLE.json")

    expected_products = {"R4-STATUS", "R4-DAILY", "R4-WEEKLY", "R4-MONTHLY", "R4-QUARTERLY", "R4-ANNUAL", "R4-EVENT"}
    assert contract["status"] == "DEVELOPMENT_PRODUCT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN_NO_ACTIVATION"
    assert contract["development_mode"] is True
    assert contract["operating_activation"] is False
    assert contract["product_count"] == 7
    assert {row["product_id"] for row in contract["products"]} == expected_products
    assert all(row["operating_activation"] is False for row in contract["products"])
    assert all(row["required_sections"] for row in contract["products"])
    assert all(row["required_inputs"] for row in contract["products"])
    assert all(row["fail_closed_when"] for row in contract["products"])

    sample_files = [
        "R4_UNIFIED_OPERATING_STATUS_SAMPLE.json",
        "R4_DAILY_OPERATING_BRIEF_SAMPLE.md",
        "R4_WEEKLY_OPERATING_REVIEW_SAMPLE.md",
        "R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md",
        "R4_QUARTERLY_PORTFOLIO_REVIEW_SAMPLE.md",
        "R4_ANNUAL_STRATEGY_REVIEW_SAMPLE.md",
        "R4_EVENT_ALERT_SAMPLE.md",
    ]
    assert all((samples / name).exists() for name in sample_files)
    assert acceptance["product_count"] == 7
    assert acceptance["development_sample_count"] == 7
    assert acceptance["R5_attribution_started"] is False
    assert acceptance["R6_production_acceptance_started"] is False
    assert acceptance["operating_activation"] is False
    assert acceptance["schedule_activation_count"] == 0
    assert acceptance["ready_for_user_decision_count"] == 0
    assert acceptance["implementation_ready_count"] == 0
    assert acceptance["economic_mutations"] == {"real_account": 0, "simulation": 0, "candidate_membership": 0, "legacy_decisions": 0, "orders": 0}

    assert unified["status"] == "DEVELOPMENT_SAMPLE_READY_NOT_OPERATING"
    assert unified["operating_activation"] is False
    assert unified["real_account"]["holdings"] == 7
    assert unified["simulation"]["holdings"] == 16
    assert unified["simulation"]["cash_rmb"] == 219533.98
    assert unified["simulation"]["unrealized_pnl_rmb"] == 16388.9
    assert unified["simulation"]["cash_source_field"] == "summary.execution_cash_balance"
    assert unified["simulation"]["unrealized_pnl_source_field"] == "summary.open_unrealized_pnl"
    assert unified["candidate"]["core"] == 2
    assert unified["candidate"]["shadow_track"] == 38
    assert unified["candidate"]["research_queue"] == 33
    assert unified["candidate"]["ready_for_user_decision"] == 0
    assert unified["r3_scenarios"] == {"count": 7, "live_decisions": 0}
    assert unified["orders"] == 0

    assert execution["current_step"] == "R4_OPERATING_PRODUCTS_DEVELOPMENT_COMPLETE_CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["development_roadmap"]["R4"]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
    assert execution["development_roadmap"]["R5"]["status"] == "NOT_STARTED_NEXT_AUTHORIZED_STAGE"
    assert execution["development_roadmap"]["R6"]["status"] == "NOT_STARTED"
    assert execution["operating_products_r4"]["product_count"] == 7
    assert execution["operating_products_r4"]["development_samples"] == 7
    assert execution["operating_products_r4"]["operating_activation"] is False
    assert execution["operating_products_r4"]["schedule_activation_count"] == 0
    assert execution["next_task"] == "R5_ATTRIBUTION_AND_CALIBRATION_DEVELOPMENT_AFTER_R4_PRESENT_ON_MAIN"
    assert execution["ready_for_user_decision_count"] == 0
    assert execution["implementation_ready_count"] == 0
    assert execution["trade_authority"] == "NONE"

    registered = {row["asset_id"]: row for row in registry["assets"]}
    for asset_id in [
        "R4_OPERATING_PRODUCT_CONTRACT_CURRENT",
        "R4_OPERATING_PRODUCT_CATALOG_CURRENT",
        "R4_UNIFIED_OPERATING_STATUS_SAMPLE",
        "R4_OPERATING_PRODUCTS_ACCEPTANCE",
        "R4_STATUS_CURRENT",
    ]:
        assert registered[asset_id]["status"] == "CURRENT_IF_PRESENT_ON_MAIN"
        assert registered[asset_id]["source_pr"] == 158
    assert registry["latest_completed_main_pr"] == 157
    assert registry["release_sequence"] == 21

    daily = (samples / "R4_DAILY_OPERATING_BRIEF_SAMPLE.md").read_text(encoding="utf-8")
    monthly = (samples / "R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md").read_text(encoding="utf-8")
    annual = (samples / "R4_ANNUAL_STRATEGY_REVIEW_SAMPLE.md").read_text(encoding="utf-8")
    event = (samples / "R4_EVENT_ALERT_SAMPLE.md").read_text(encoding="utf-8")
    assert "研究现金约¥219,533.98" in daily
    assert "当前未实现盈亏约¥16,388.90" in monthly
    assert "NOT_AVAILABLE_UNTIL_R5" in monthly
    assert "NOT_AVAILABLE_UNTIL_R5_AND_R6" in annual
    assert "不得创建订单" in event

    path_map = {
        "real_account_positions_sha256": state / "10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json",
        "simulation_positions_sha256": state / "20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json",
        "candidate_current_sha256": state / "40_CANDIDATE/CANDIDATE_CURRENT.json",
        "legacy_decisions_sha256": state / "60_DECISIONS/DECISION_PROPOSALS_CURRENT.json",
    }
    for key, expected in acceptance["protected_state_hashes"].items():
        assert hashlib.sha256(path_map[key].read_bytes()).hexdigest() == expected

    subprocess.run(["python", "-m", "pytest", "-q", "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py"], cwd=root, check=True)

    changed = set(subprocess.check_output(["git", "diff", "--name-only", "origin/main"], cwd=root, text=True).splitlines())
    allowed = {
        ".github/workflows/r4_operating_products.yml",
        "automation/r4_operating_products/build_r4_operating_products.py",
        "automation/r4_operating_products/normalize_r4_samples.py",
        "automation/r4_operating_products/patch_forward_lineage.py",
        "automation/r4_operating_products/validate_r4_operating_products.py",
        "automation/wp3_2a/tests/test_operating_closure_and_wp3_2b.py",
        "investment_os_runtime/00_CONTROL/AUTHORITATIVE_ASSET_REGISTRY.json",
        "investment_os_runtime/00_CONTROL/CAPABILITY_REALITY_MATRIX_CURRENT.md",
        "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json",
        "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCT_CONTRACT_CURRENT.json",
        "investment_os_runtime/00_CONTROL/R4_OPERATING_PRODUCTS_ACCEPTANCE_RECORD.json",
        "investment_os_runtime/00_CONTROL/R4_STATUS_CURRENT.md",
        "investment_os_runtime/00_CONTROL/USER_OPERATING_GUIDE_CURRENT.md",
        "investment_os_runtime/00_CONTROL/WORK_PACKAGE_MASTER_PLAN_CURRENT.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/R4_OPERATING_PRODUCT_CATALOG_CURRENT.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_UNIFIED_OPERATING_STATUS_SAMPLE.json",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_DAILY_OPERATING_BRIEF_SAMPLE.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_WEEKLY_OPERATING_REVIEW_SAMPLE.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_MONTHLY_INVESTMENT_REVIEW_SAMPLE.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_QUARTERLY_PORTFOLIO_REVIEW_SAMPLE.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_ANNUAL_STRATEGY_REVIEW_SAMPLE.md",
        "investment_os_runtime/50_OPERATING_PRODUCTS/DEVELOPMENT_SAMPLES/R4_EVENT_ALERT_SAMPLE.md",
    }
    forbidden = sorted(changed - allowed)
    if forbidden:
        raise SystemExit("R4_SCOPE_VIOLATION:" + ",".join(forbidden))
    protected_paths = set(str(path.relative_to(root)) for path in path_map.values())
    leaked = sorted(changed & protected_paths)
    if leaked:
        raise SystemExit("R4_PROTECTED_STATE_MUTATION:" + ",".join(leaked))

    print({
        "products": 7,
        "samples": 7,
        "simulation_cash_rmb": 219533.98,
        "simulation_open_unrealized_pnl_rmb": 16388.9,
        "operating_activation": False,
        "schedule_activation_count": 0,
        "R5_started": False,
        "R6_started": False,
        "mutations": 0,
        "orders": 0,
        "scope": "R4_OPERATING_PRODUCTS_ONLY",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
