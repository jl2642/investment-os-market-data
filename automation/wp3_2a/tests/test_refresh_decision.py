from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "automation/wp3_2a/refresh_decision.py"


def run_decision(tmp_path: Path, incoming: str, current: str, open_count: int) -> dict:
    binding = tmp_path / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    binding.parent.mkdir(parents=True)
    binding.write_text(json.dumps({"as_of_date": current}), encoding="utf-8")
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--session",
            incoming,
            "--open-proposal-count",
            str(open_count),
            "--output",
            str(output),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    return json.loads(output.read_text(encoding="utf-8"))


def test_same_session_is_successful_noop(tmp_path: Path):
    result = run_decision(tmp_path, "2026-07-24", "2026-07-24", 0)
    assert result["status"] == "NO_OP"
    assert result["reason"] == "SESSION_NOT_NEWER_THAN_CURRENT"
    assert result["proceed"] is False
    assert result["trade_authority"] == "NONE"


def test_older_session_is_successful_noop(tmp_path: Path):
    result = run_decision(tmp_path, "2026-07-23", "2026-07-24", 0)
    assert result["reason"] == "SESSION_NOT_NEWER_THAN_CURRENT"
    assert result["proceed"] is False


def test_open_proposal_blocks_duplicate_proposal(tmp_path: Path):
    result = run_decision(tmp_path, "2026-07-25", "2026-07-24", 1)
    assert result["reason"] == "OPEN_PROPOSAL_ALREADY_EXISTS"
    assert result["proceed"] is False


def test_new_session_without_open_proposal_proceeds(tmp_path: Path):
    result = run_decision(tmp_path, "2026-07-25", "2026-07-24", 0)
    assert result["status"] == "PROCEED"
    assert result["reason"] == "NEW_SESSION_NO_OPEN_PROPOSAL"
    assert result["proceed"] is True
    assert result["orders"] == 0
