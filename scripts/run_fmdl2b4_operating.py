#!/usr/bin/env python3
"""Operate the complete FMDL-2B-4 incremental history and factor refresh chain."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from scripts.fmdl2b4_history import ROOT, read_json

STATUS_DIR = ROOT / "outputs/status"
HISTORY_REPORT = ROOT / "outputs/history/refresh_candidate/FMDL2B4_HISTORY_REFRESH_REPORT.json"


def _run(module: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    diagnostics = ROOT / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    stem = module.replace(".", "_").upper()
    (diagnostics / f"{stem}_STDOUT.txt").write_text(completed.stdout, encoding="utf-8")
    (diagnostics / f"{stem}_STDERR.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"{module}_FAILED_{completed.returncode}: {(completed.stderr or completed.stdout)[-2000:]}")


def _write_status(payload: dict[str, Any], success: bool = False) -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    (STATUS_DIR / "FMDL2B4_LAST_RUN.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if success:
        (STATUS_DIR / "FMDL2B4_LAST_SUCCESS.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def operate(root: Path = ROOT) -> dict[str, Any]:
    try:
        _run("scripts.run_incremental_history_refresh_v2")
        history_report = read_json(HISTORY_REPORT)
        if history_report.get("status") == "NO_OP_ALREADY_CURRENT":
            result = {
                "status": "NO_OP_ALREADY_CURRENT",
                "as_of_date": history_report["as_of_date"],
                "history_current_preserved": True,
                "factor_current_preserved": True,
                "trade_authority": "NONE",
            }
            _write_status(result, success=False)
            print(json.dumps(result, ensure_ascii=False))
            return result

        _run("scripts.finalize_b4_history_candidate")
        _run("scripts.run_b4_factor_refresh")
        _run("scripts.validate_fmdl2b4_candidate")
        _run("scripts.publish_fmdl2b4")
        history_release = read_json(ROOT / "outputs/history/current/HISTORY_CURRENT_RELEASE.json")
        factor_release = read_json(ROOT / "outputs/factors/current/FACTOR_CURRENT_RELEASE.json")
        result = {
            "status": "PUBLISHED",
            "as_of_date": history_release["as_of_date"],
            "history_release_id": history_release["release_id"],
            "factor_release_id": factor_release["release_id"],
            "history_current_preserved": False,
            "factor_current_preserved": False,
            "trade_authority": "NONE",
        }
        _write_status(result, success=True)
        print(json.dumps(result, ensure_ascii=False))
        return result
    except Exception as exc:
        failure = {
            "status": "FAILED_LKG_PRESERVED",
            "error": f"{type(exc).__name__}: {exc}",
            "history_current_preserved": True,
            "factor_current_preserved": True,
            "trade_authority": "NONE",
        }
        _write_status(failure, success=False)
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        raise


if __name__ == "__main__":
    try:
        operate(ROOT)
    except Exception:
        raise SystemExit(2)
