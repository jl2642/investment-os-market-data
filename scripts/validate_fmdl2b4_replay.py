#!/usr/bin/env python3
"""Validate same-date FMDL-2B-4 no-op replay and LKG identity."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> dict[str, Any]:
    last_run = read_json(root / "outputs/status/FMDL2B4_LAST_RUN.json")
    last_success = read_json(root / "outputs/status/FMDL2B4_LAST_SUCCESS.json")
    history = read_json(root / "outputs/history/current/HISTORY_CURRENT_RELEASE.json")
    factor = read_json(root / "outputs/factors/current/FACTOR_CURRENT_RELEASE.json")
    errors: list[str] = []
    if last_run.get("status") != "NO_OP_ALREADY_CURRENT":
        errors.append("LAST_RUN_NOT_NO_OP")
    if last_success.get("status") != "PUBLISHED":
        errors.append("LAST_SUCCESS_NOT_PUBLISHED")
    if str(last_run.get("as_of_date")) != str(history.get("as_of_date")):
        errors.append("NO_OP_HISTORY_AS_OF_MISMATCH")
    if str(history.get("as_of_date")) != str(factor.get("as_of_date")):
        errors.append("HISTORY_FACTOR_AS_OF_MISMATCH")
    if str(last_success.get("history_release_id")) != str(history.get("release_id")):
        errors.append("HISTORY_LKG_ID_CHANGED")
    if str(last_success.get("factor_release_id")) != str(factor.get("release_id")):
        errors.append("FACTOR_LKG_ID_CHANGED")
    if not last_run.get("history_current_preserved") or not last_run.get("factor_current_preserved"):
        errors.append("NO_OP_DID_NOT_DECLARE_CURRENT_PRESERVED")
    result = {
        "validation_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "as_of_date": history.get("as_of_date"),
        "history_release_id": history.get("release_id"),
        "factor_release_id": factor.get("release_id"),
        "last_run_status": last_run.get("status"),
        "authority": "VALIDATION_ONLY_NO_TRADE_AUTHORITY",
    }
    output = root / "diagnostics/FMDL2B4_REPLAY_VALIDATION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise RuntimeError(";".join(errors))
    return result


if __name__ == "__main__":
    try:
        validate(ROOT)
    except Exception as exc:
        print(f"FMDL-2B-4 replay validation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
