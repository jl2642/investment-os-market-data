#!/usr/bin/env python3
"""Operational FMDL-1D/E runner with trading-day and LKG controls."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.common import iso_shanghai, now_shanghai, write_json  # noqa: E402
from pipeline.publish import publish_candidate, validate_control_payload, write_failure_status  # noqa: E402
from scripts.a_share_chain_coherence import assess_chain_coherence  # noqa: E402

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def _confirmed_trade_day(current: datetime) -> tuple[bool, str]:
    """Confirm the current Chinese calendar date using the public trade calendar."""

    calendar = ak.tool_trade_date_hist_sina()
    if calendar is None or not isinstance(calendar, pd.DataFrame) or calendar.empty:
        raise RuntimeError("Trading calendar unavailable; scheduled publication is fail-closed")
    column = next((name for name in ("trade_date", "交易日", "date") if name in calendar.columns), None)
    if column is None:
        raise RuntimeError("Trading calendar has no recognized date column")
    dates = set(pd.to_datetime(calendar[column], errors="coerce").dropna().dt.date)
    current_date = current.astimezone(BUSINESS_TZ).date()
    return current_date in dates, current_date.isoformat()


def _current_as_of(root: Path) -> str | None:
    path = root / "outputs/current/CURRENT_RELEASE.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("as_of_date")


def _same_date_noop_eligibility(root: Path, target_date: str) -> tuple[bool, dict]:
    if _current_as_of(root) != target_date:
        return False, {
            "status": "MARKET_NOT_SAME_DATE",
            "target_as_of_date": target_date,
            "trade_authority": "NONE",
        }
    coherence = assess_chain_coherence(root, target_date=target_date)
    return coherence["status"] == "PASS_COHERENT", coherence


def _write_noop(root: Path, *, generated_at: str, as_of_date: str, reason: str) -> None:
    payload = {
        "run_id": f"NOOP_{as_of_date.replace('-', '')}",
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "status": "NO_OP",
        "action": reason,
        "current_preserved": True,
    }
    validate_control_payload(payload, "operating_status.schema.json")
    write_json(root / "outputs/status/LAST_RUN.json", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger", choices=["schedule", "workflow_dispatch", "workflow_run", "push", "pull_request", "manual"], default="manual")
    parser.add_argument("--force-run", action="store_true")
    parser.add_argument("--allow-same-date-refresh", action="store_true")
    args = parser.parse_args()

    current = now_shanghai()
    generated_at = iso_shanghai(current)
    fallback_run_id = current.strftime("FMDL1DE_%Y%m%dT%H%M%S%z")
    today = current.date().isoformat()

    try:
        if args.trigger == "schedule" and not args.force_run:
            is_trade_day, today = _confirmed_trade_day(current)
            if not is_trade_day:
                _write_noop(ROOT, generated_at=generated_at, as_of_date=today, reason="NO_OP_NON_TRADING_DAY")
                print(json.dumps({"status": "NO_OP_NON_TRADING_DAY", "as_of_date": today}, ensure_ascii=False))
                return 0
            if _current_as_of(ROOT) == today and not args.allow_same_date_refresh:
                noop_allowed, coherence = _same_date_noop_eligibility(ROOT, today)
                if noop_allowed:
                    _write_noop(ROOT, generated_at=generated_at, as_of_date=today, reason="NO_OP_ALREADY_CURRENT")
                    print(json.dumps(
                        {
                            "status": "NO_OP_ALREADY_CURRENT",
                            "as_of_date": today,
                            "chain_coherence": coherence,
                        },
                        ensure_ascii=False,
                    ))
                    return 0
                print(json.dumps(
                    {
                        "status": "SAME_DATE_CHAIN_INCOHERENT_CONTINUE",
                        "as_of_date": today,
                        "chain_coherence": coherence,
                    },
                    ensure_ascii=False,
                ))

        completed = subprocess.run(
            [sys.executable, str(ROOT / "pipeline/build_candidate.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        diagnostics = ROOT / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        (diagnostics / "FMDL_OPERATIONAL_BUILD_STDOUT.txt").write_text(completed.stdout, encoding="utf-8")
        (diagnostics / "FMDL_OPERATIONAL_BUILD_STDERR.txt").write_text(completed.stderr, encoding="utf-8")

        if completed.returncode != 0:
            report_path = ROOT / "outputs/candidate/FMDL_1BC_RUN_REPORT.json"
            run_id = fallback_run_id
            as_of_date = today
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                run_id = report.get("run_id", run_id)
                as_of_date = report.get("as_of_date", as_of_date)
            write_failure_status(
                root=ROOT,
                run_id=run_id,
                as_of_date=as_of_date,
                generated_at=generated_at,
                reason="CANDIDATE_BUILD_FAILED",
                error=(completed.stderr or completed.stdout)[-4000:],
            )
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode

        result = publish_candidate(root=ROOT, generated_at=generated_at)
        print(
            json.dumps(
                {
                    "action": result.action,
                    "run_id": result.run_id,
                    "as_of_date": result.as_of_date,
                    "current_preserved": result.current_preserved,
                    "hard_failures": result.hard_failures,
                    "soft_warnings": result.soft_warnings,
                    "release_path": result.release_path,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not result.hard_failures else 2

    except Exception as exc:
        write_failure_status(
            root=ROOT,
            run_id=fallback_run_id,
            as_of_date=today,
            generated_at=generated_at,
            reason="OPERATIONAL_EXCEPTION",
            error=f"{type(exc).__name__}: {exc}",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
