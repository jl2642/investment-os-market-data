from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
import sys
from pathlib import Path

from automation.operating_current.publish_operating_current import build_index

ROOT = Path(__file__).resolve().parents[1]


def test_s2_publisher_direct_entrypoint_imports_repo_package() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "automation/investment_pipeline/publish_pipeline.py"),
            "--help",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "--stage" in result.stdout


def test_s3_publisher_direct_entrypoint_imports_repo_package() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "automation/product_surface/publish_product_surface.py"),
            "--help",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "--surface-json" in result.stdout


def test_s4_final_runtime_is_event_driven_with_bounded_d2_recovery_and_temporary_replay_removed() -> None:
    s2 = (ROOT / ".github/workflows/s2-investment-pipeline.yml").read_text(encoding="utf-8")
    d2 = (ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml").read_text(encoding="utf-8")
    assert "\n  schedule:\n" not in s2
    assert "\n  schedule:\n" in d2
    assert '- cron: "35 0 * * 1-5"' in d2
    assert "workflow_dispatch:" in s2
    assert "workflow_dispatch:" in d2
    assert d2.count("github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'") >= 5
    assert not (ROOT / ".github/workflows/s4-controlled-same-date-replay.yml").exists()


def test_s4_failure_receipt_tracks_exact_full_rebase_workflow_name() -> None:
    receipt = (ROOT / ".github/workflows/operating-current-failure-receipts.yml").read_text(encoding="utf-8")
    assert "FMDL 2B-4 Multi-Session Full Rebase Recovery" in receipt
    assert '"FMDL 2B-4 Multi-Session Recovery"' not in receipt


def test_s2_workflow_run_requires_main_source_branch() -> None:
    workflow = (ROOT / ".github/workflows/s2-investment-pipeline.yml").read_text(encoding="utf-8")
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert workflow.count("github.event.workflow_run.head_branch == 'main'") >= 2


def test_runtime_hygiene_retires_legacy_wp5_schedules() -> None:
    for rel in (
        ".github/workflows/wp5_e_post_close_action_gate.yml",
        ".github/workflows/wp5_f_position_continuity_interface.yml",
    ):
        workflow = (ROOT / rel).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in workflow
        assert "\n  schedule:\n" not in workflow
        assert "\n  push:\n" not in workflow
        assert "\n  pull_request:\n" not in workflow


def test_failure_receipt_maps_current_cross_market_run_name() -> None:
    receipt = (ROOT / ".github/workflows/operating-current-failure-receipts.yml").read_text(encoding="utf-8")
    assert "Round 3 bounded cross-market batch and research proposal" in receipt


def test_daily_runner_accepts_workflow_run_trigger() -> None:
    daily = (ROOT / "pipeline/run_daily.py").read_text(encoding="utf-8")
    assert '"workflow_run"' in daily


def test_cross_market_domains_are_explicit_non_blocking_support(tmp_path: Path) -> None:
    index = build_index(tmp_path)
    by_domain = {row["domain_id"]: row for row in index["domains"]}
    for domain in (
        "CROSS_MARKET_LIMITED",
        "US_BOUNDED_COVERAGE",
        "SEC_QUEUE_CONSUMER",
        "SEC_OFFICIAL_RETRIEVAL",
    ):
        assert by_domain[domain]["runtime_role"] == "SUPPORTING_NON_BLOCKING"
        assert by_domain[domain]["blocks_primary_investment_chain"] is False


def test_cross_market_us_bounded_coverage_fails_closed_when_capture_quality_is_blocked() -> None:
    workflow = (ROOT / ".github/workflows/round3-cross-market-limited-production.yml").read_text(encoding="utf-8")
    assert 'if [[ "${{ steps.operate.outputs.us_bounded_capture_quality }}" == BLOCKED* ]]' in workflow
    assert '--status "$US_STATUS"' in workflow
    assert '"${US_ADVANCE[@]}"' in workflow
    assert "runtime_role: SUPPORTING_NON_BLOCKING" in workflow


def test_a_share_long_holiday_uses_exchange_session_confirmation(tmp_path: Path) -> None:
    domains = tmp_path / "domains"
    runs = tmp_path / "runs" / "A_SHARE_FULL_MARKET"
    domains.mkdir(parents=True)
    runs.mkdir(parents=True)

    market_current = {
        "schema_version": "1.0.0",
        "domain_id": "A_SHARE_FULL_MARKET",
        "status": "PASS",
        "source_workflow": "test",
        "source_run_id": "1",
        "source_run_attempt": 1,
        "source_branch": "main",
        "source_commit_sha": "abc",
        "published_at_utc": "2026-10-02T00:00:00Z",
        "data_watermark": "2026-09-30",
        "watermark_sort_key": "2026-09-30",
        "qc_status": "PASS_CHAIN_COHERENT",
        "fail_closed": True,
        "protected_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0},
        "orders": 0,
        "trade_authority": "NONE",
    }
    marks_current = dict(market_current)
    marks_current.update({
        "domain_id": "PORTFOLIO_MARKS",
        "qc_status": "PASS_COMPLETE",
    })
    (domains / "A_SHARE_FULL_MARKET.json").write_text(
        json.dumps(market_current), encoding="utf-8"
    )
    (domains / "PORTFOLIO_MARKS.json").write_text(
        json.dumps(marks_current), encoding="utf-8"
    )

    noop = dict(market_current)
    noop.update({
        "status": "NO_OP",
        "source_run_id": "2",
        "published_at_utc": "2026-10-06T09:30:00Z",
        "qc_status": "NO_OP_EXCHANGE_SESSION_CONFIRMED",
        "advance_current_requested": False,
    })
    (runs / "2-a1-no_op.json").write_text(json.dumps(noop), encoding="utf-8")

    index = build_index(
        tmp_path,
        now=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
    )
    by_domain = {row["domain_id"]: row for row in index["domains"]}
    assert index["staleness_basis"] == "EXCHANGE_SESSION_REFERENCE_WITH_CALENDAR_FALLBACK"
    assert by_domain["A_SHARE_FULL_MARKET"]["watermark_age_calendar_days"] == 6
    assert by_domain["A_SHARE_FULL_MARKET"]["health"] == "CURRENT"
    assert by_domain["PORTFOLIO_MARKS"]["health"] == "CURRENT"
    assert by_domain["PORTFOLIO_MARKS"]["exchange_session_aligned"] is True


def test_a_share_old_watermark_stales_without_recent_session_confirmation(tmp_path: Path) -> None:
    domains = tmp_path / "domains"
    domains.mkdir(parents=True)
    current = {
        "schema_version": "1.0.0",
        "domain_id": "A_SHARE_FULL_MARKET",
        "status": "PASS",
        "source_workflow": "test",
        "source_run_id": "1",
        "source_run_attempt": 1,
        "source_branch": "main",
        "source_commit_sha": "abc",
        "published_at_utc": "2026-09-30T09:30:00Z",
        "data_watermark": "2026-09-30",
        "watermark_sort_key": "2026-09-30",
        "qc_status": "PASS_CHAIN_COHERENT",
        "fail_closed": True,
        "protected_mutations": {"real_account": 0, "simulation": 0, "candidate_membership": 0},
        "orders": 0,
        "trade_authority": "NONE",
    }
    (domains / "A_SHARE_FULL_MARKET.json").write_text(
        json.dumps(current), encoding="utf-8"
    )
    index = build_index(
        tmp_path,
        now=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
    )
    market = next(row for row in index["domains"] if row["domain_id"] == "A_SHARE_FULL_MARKET")
    assert market["health"] == "STALE_BY_CALENDAR_FALLBACK"


def test_daily_workflow_publishes_exchange_session_noop_confirmation() -> None:
    daily = (ROOT / ".github/workflows/fmdl-daily-production.yml").read_text(encoding="utf-8")
    assert "Publish exchange-session no-op confirmation" in daily
    assert "--qc-status NO_OP_EXCHANGE_SESSION_CONFIRMED" in daily
