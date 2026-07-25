from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AUTO = ROOT / "automation/wp3_2a"


def test_self_test_ignores_untracked_runtime_cache() -> None:
    cache_dir = AUTO / "__pycache__"
    cache_dir.mkdir(exist_ok=True)
    marker = cache_dir / "wp3_2a_runtime_probe.pyc"
    marker.write_bytes(b"runtime-only ignored cache probe")

    try:
        run = subprocess.run(
            [
                sys.executable,
                str(AUTO / "self_test.py"),
                "--repo-root",
                str(ROOT),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        assert '"cache_scope": "TRACKED_REPOSITORY_PATHS"' in run.stdout
    finally:
        marker.unlink(missing_ok=True)
