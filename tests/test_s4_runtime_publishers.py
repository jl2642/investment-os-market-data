from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def test_s4_final_runtime_is_event_driven_and_temporary_replay_removed() -> None:
    s2 = (ROOT / ".github/workflows/s2-investment-pipeline.yml").read_text(encoding="utf-8")
    d2 = (ROOT / ".github/workflows/research-queue-d2-auto-consumer.yml").read_text(encoding="utf-8")
    assert "\n  schedule:\n" not in s2
    assert "\n  schedule:\n" not in d2
    assert "workflow_dispatch:" in s2
    assert "workflow_dispatch:" in d2
    assert not (ROOT / ".github/workflows/s4-controlled-same-date-replay.yml").exists()


def test_s4_failure_receipt_tracks_exact_full_rebase_workflow_name() -> None:
    receipt = (ROOT / ".github/workflows/operating-current-failure-receipts.yml").read_text(encoding="utf-8")
    assert "FMDL 2B-4 Multi-Session Full Rebase Recovery" in receipt
    assert '"FMDL 2B-4 Multi-Session Recovery"' not in receipt


def test_s2_workflow_run_requires_main_source_branch() -> None:
    workflow = (ROOT / ".github/workflows/s2-investment-pipeline.yml").read_text(encoding="utf-8")
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert workflow.count("github.event.workflow_run.head_branch == 'main'") >= 2
