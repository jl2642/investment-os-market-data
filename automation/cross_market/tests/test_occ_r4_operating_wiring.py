from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_occ_r4_cross_market_policy_is_fail_closed_and_sec_consumer_is_live_wired() -> None:
    policy = json.loads((ROOT / "automation/cross_market/round3_policy.json").read_text(encoding="utf-8"))
    us = policy["united_states"]
    assert us["minimum_daily_rotation_success_ratio"] == 0.80
    assert us["minimum_daily_benchmark_success_count"] == 5
    assert us["sec_execution_mode"] == "QUEUE_FOR_CONTROLLED_OFFICIAL_RETRIEVAL"

    workflow = (ROOT / ".github/workflows/round3-cross-market-limited-production.yml").read_text(encoding="utf-8")
    assert "collect_round3_sec_official.py" in workflow
    assert "apply_round3_sec_observer_results.py" in workflow
    assert "--domain US_BOUNDED_COVERAGE" in workflow
    assert "--domain SEC_QUEUE_CONSUMER" in workflow
    assert "--domain SEC_OFFICIAL_RETRIEVAL" in workflow
    assert "BLOCKED_INADEQUATE_BOUNDED_CAPTURE" in (
        ROOT / "automation/cross_market/build_round3_limited_production.py"
    ).read_text(encoding="utf-8")
    assert "git push origin HEAD:main" not in workflow
    assert "TRADE_AUTHORITY: NONE" in workflow


def test_occ_r4_portfolio_freshness_workflow_is_governed_and_non_mutating() -> None:
    workflow = (ROOT / ".github/workflows/occ-r4-portfolio-decision-freshness.yml").read_text(encoding="utf-8")
    assert "RETIRED — OCC-R4 Portfolio Decision Freshness" in workflow
    assert "\n  schedule:" not in workflow
    assert "\n  workflow_run:" not in workflow
    assert "S3 Portfolio + Product Surface is the canonical portfolio/user product producer." in workflow
    assert "Historical automation/portfolio_freshness code remains for audit only." in workflow
    assert "git push origin HEAD:main" not in workflow
    assert "trade_authority=NONE" in workflow


def test_occ_r4_operating_current_health_registers_new_authorities() -> None:
    publisher = (ROOT / "automation/operating_current/publish_operating_current.py").read_text(encoding="utf-8")
    for domain in (
        "US_BOUNDED_COVERAGE",
        "SEC_QUEUE_CONSUMER",
        "SEC_OFFICIAL_RETRIEVAL",
        "PORTFOLIO_DECISION_FRESHNESS",
    ):
        assert f'"{domain}"' in publisher
