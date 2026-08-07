#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HK_TZ = ZoneInfo("Asia/Hong_Kong")
MARKET_CLOSE_BUFFER = time(16, 30)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _service_day(day: date, calendar: dict) -> bool:
    blocked = {date.fromisoformat(value) for value in calendar.get("full_day_non_service_dates", [])}
    return day.weekday() < 5 and day not in blocked


def latest_completed_service_date(calendar: dict, now_hk: datetime) -> date:
    local = now_hk.astimezone(HK_TZ) if now_hk.tzinfo else now_hk.replace(tzinfo=HK_TZ)
    candidate = local.date()
    if not (_service_day(candidate, calendar) and local.timetz().replace(tzinfo=None) >= MARKET_CLOSE_BUFFER):
        candidate -= timedelta(days=1)
    while not _service_day(candidate, calendar):
        candidate -= timedelta(days=1)
    return candidate


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _build_fmdl5c(repo_root: Path, output: Path, cutoff: date) -> dict:
    scripts = repo_root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        module = importlib.import_module("run_fmdl5c_market_store")
        original_date = module.date

        class CutoffDate(original_date):
            @classmethod
            def today(cls):
                return cls(cutoff.year, cutoff.month, cutoff.day)

        module.date = CutoffDate
        try:
            if output.exists():
                shutil.rmtree(output)
            output.mkdir(parents=True, exist_ok=True)
            module.build(output)
        finally:
            module.date = original_date
    finally:
        if str(scripts) in sys.path:
            sys.path.remove(str(scripts))
    _run(
        [sys.executable, "scripts/fmdl5c_apply_hkex_current_actions.py", "--candidate", str(output)],
        repo_root,
    )
    return _json(output / "FMDL5C_DECISION.json")


def _patch_fmdl5e_contract(repo_root: Path, fmdl5c_output: Path, fmdl5c_release_id: str) -> tuple[Path, bytes]:
    path = repo_root / "config/fmdl5e_hk_factor_screening_contract.json"
    original = path.read_bytes()
    contract = json.loads(original.decode("utf-8"))
    contract["source_release_ids"]["fmdl5c"] = fmdl5c_release_id
    prefix = fmdl5c_output.relative_to(repo_root).as_posix()
    inputs = contract["inputs"]
    inputs["market_decision"] = f"{prefix}/FMDL5C_DECISION.json"
    inputs["daily_price_volume"] = f"{prefix}/FMDL5C_DAILY_PRICE_VOLUME.parquet"
    inputs["latest_price_snapshot"] = f"{prefix}/FMDL5C_LATEST_PRICE_SNAPSHOT.csv"
    inputs["corporate_actions"] = f"{prefix}/FMDL5C_CORPORATE_ACTIONS.csv"
    inputs["fx_daily"] = f"{prefix}/FMDL5C_FX_DAILY.csv"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, original


def refresh(repo_root: Path, calendar_path: Path, eligibility_as_of: str, work_dir: Path, now_hk: datetime | None = None) -> dict:
    calendar = _json(calendar_path)
    now = now_hk or datetime.now(HK_TZ)
    cutoff = latest_completed_service_date(calendar, now)
    eligibility_date = date.fromisoformat(eligibility_as_of)
    if cutoff > eligibility_date:
        raise RuntimeError(f"MARKET_CUTOFF_AFTER_ELIGIBILITY:{cutoff}:{eligibility_date}")

    work_dir.mkdir(parents=True, exist_ok=True)
    fmdl5c_output = work_dir / "fmdl5c_fresh"
    env = os.environ.copy()
    env.setdefault("FMDL5C_WORKERS", "10")
    old_workers = os.environ.get("FMDL5C_WORKERS")
    os.environ["FMDL5C_WORKERS"] = env["FMDL5C_WORKERS"]
    try:
        fmdl5c = _build_fmdl5c(repo_root, fmdl5c_output, cutoff)
    finally:
        if old_workers is None:
            os.environ.pop("FMDL5C_WORKERS", None)
        else:
            os.environ["FMDL5C_WORKERS"] = old_workers
    if fmdl5c.get("status") != "FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED":
        raise RuntimeError(f"FMDL5C_REFRESH_REJECTED:{fmdl5c.get('hard_failures')}")
    market_max = str((fmdl5c.get("metrics") or {}).get("max_market_date") or "")
    if not market_max or date.fromisoformat(market_max) > cutoff:
        raise RuntimeError(f"FMDL5C_PARTIAL_OR_FUTURE_SESSION:{market_max}:{cutoff}")

    contract_path, original_contract = _patch_fmdl5e_contract(repo_root, fmdl5c_output, str(fmdl5c["release_id"]))
    fmdl5e_output = work_dir / "fmdl5e_fresh"
    try:
        if fmdl5e_output.exists():
            shutil.rmtree(fmdl5e_output)
        _run(
            [
                sys.executable,
                "scripts/run_fmdl5e_hk_factor_screening_r1.py",
                "--repo-root",
                ".",
                "--output",
                str(fmdl5e_output.relative_to(repo_root)),
            ],
            repo_root,
        )
    finally:
        contract_path.write_bytes(original_contract)
    fmdl5e = _json(fmdl5e_output / "FMDL5E_DECISION.json")
    if fmdl5e.get("status") != "FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED":
        raise RuntimeError(f"FMDL5E_REFRESH_REJECTED:{fmdl5e.get('hard_failures')}")
    fmdl5e_as_of = date.fromisoformat(str(fmdl5e["as_of_date"]))
    if fmdl5e_as_of > eligibility_date or fmdl5e_as_of > cutoff:
        raise RuntimeError(f"FMDL5E_FUTURE_INFORMATION:{fmdl5e_as_of}:{cutoff}:{eligibility_date}")

    result = {
        "program_id": "HKCU-1",
        "phase": "R2E_UPSTREAM_REFRESH",
        "status": "PASS",
        "eligibility_as_of_date": eligibility_as_of,
        "market_completed_session_cutoff": cutoff.isoformat(),
        "fmdl5c_release_id": fmdl5c.get("release_id"),
        "fmdl5c_max_market_date": market_max,
        "fmdl5c_source_security_count": (fmdl5c.get("metrics") or {}).get("source_security_count"),
        "fmdl5e_release_id": fmdl5e.get("release_id"),
        "fmdl5e_as_of_date": fmdl5e.get("as_of_date"),
        "fmdl5e_source_release_ids": fmdl5e.get("source_release_ids"),
        "candidate_pool_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "orders_created": 0,
        "trade_authority": "NONE",
    }
    (work_dir / "HKCU1_R2E_UPSTREAM_REFRESH_DECISION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--eligibility-as-of-date", required=True)
    p.add_argument("--work-dir", type=Path, required=True)
    a = p.parse_args()
    root = a.repo_root.resolve()
    calendar_path = a.calendar if a.calendar.is_absolute() else root / a.calendar
    work_dir = a.work_dir if a.work_dir.is_absolute() else root / a.work_dir
    result = refresh(root, calendar_path, a.eligibility_as_of_date, work_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
