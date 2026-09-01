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
