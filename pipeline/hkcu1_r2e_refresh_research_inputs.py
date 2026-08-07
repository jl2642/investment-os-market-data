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


def _date_leq(value: object, cutoff_iso: str, *, allow_blank: bool = False) -> bool:
    text = str(value or "").strip()
    if not text:
        return allow_blank
    try:
        return date.fromisoformat(text) <= date.fromisoformat(cutoff_iso)
    except ValueError:
        return False


def _filter_observation_rows(rows: list[dict], cutoff_iso: str) -> list[dict]:
    return [row for row in rows if _date_leq(row.get("observation_date"), cutoff_iso)]


def _filter_action_rows(rows: list[dict], cutoff_iso: str) -> list[dict]:
    return [row for row in rows if _date_leq(row.get("action_date"), cutoff_iso, allow_blank=False)]


def _refresh_summary(summary: dict, rows: list[dict], date_key: str, *, action_count: int | None = None) -> dict:
    out = dict(summary)
    out["row_count"] = len(rows)
    if rows:
        out["first_date"] = str(rows[0].get(date_key) or "")
        out["latest_date"] = str(rows[-1].get(date_key) or "")
    else:
        out["first_date"] = None
        out["latest_date"] = None
    if action_count is not None:
        out["action_count"] = action_count
    return out


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _apply_hkex_current_action_overlay(repo_root: Path, output: Path) -> dict:
    cmd = [sys.executable, "scripts/fmdl5c_apply_hkex_current_actions.py", "--candidate", str(output)]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    combined = f"{proc.stdout}\n{proc.stderr}"
    if proc.returncode == 0:
        return {
            "status": "PASS_OVERLAY_APPLIED",
            "exit_code": 0,
            "zero_relevant_events": False,
        }
    if "HKEX_CURRENT_ACTIONS_EMPTY_AFTER_SUCCESSFUL_PARSE" in combined:
        return {
            "status": "PASS_ZERO_RELEVANT_EVENTS",
            "exit_code": proc.returncode,
            "zero_relevant_events": True,
            "interpretation": "HKEX action table parsed successfully but contained no non-New-Listing event relevant to the current FMDL-5C universe; base accepted candidate remains unchanged.",
        }
    raise RuntimeError(f"HKEX_CURRENT_ACTION_OVERLAY_FAILED:{proc.returncode}:{combined[-2000:]}")


def _build_fmdl5c(repo_root: Path, output: Path, cutoff: date) -> tuple[dict, dict]:
    scripts = repo_root / "scripts"
    cutoff_iso = cutoff.isoformat()
    sys.path.insert(0, str(scripts))
    try:
        module = importlib.import_module("run_fmdl5c_market_store")
        original_date = module.date
        original_fetch_yahoo = module.fetch_yahoo
        original_fetch_eastmoney = module.fetch_eastmoney
        original_fetch_hkma_fx = module.fetch_hkma_fx
        original_fetch_hkex_actions = module.fetch_hkex_current_actions

        class CutoffDate(original_date):
            @classmethod
            def today(cls):
                return cls(cutoff.year, cutoff.month, cutoff.day)

        def fetch_yahoo_cutoff(security_id: str, code: str, start_date: str, end_date: str, retrieved_at_utc: str):
            rows, actions, summary = original_fetch_yahoo(security_id, code, start_date, end_date, retrieved_at_utc)
            rows = _filter_observation_rows(rows, cutoff_iso)
            actions = _filter_action_rows(actions, cutoff_iso)
            return rows, actions, _refresh_summary(summary, rows, "observation_date", action_count=len(actions))

        def fetch_eastmoney_cutoff(security_id: str, code: str, start_date: str, retrieved_at_utc: str):
            rows, summary = original_fetch_eastmoney(security_id, code, start_date, retrieved_at_utc)
            rows = _filter_observation_rows(rows, cutoff_iso)
            return rows, _refresh_summary(summary, rows, "observation_date")

        def fetch_hkma_fx_cutoff(start_date: str, retrieved_at_utc: str):
            rows, summary = original_fetch_hkma_fx(start_date, retrieved_at_utc)
            rows = _filter_observation_rows(rows, cutoff_iso)
            return rows, _refresh_summary(summary, rows, "observation_date")

        def fetch_hkex_actions_cutoff(universe_codes: set[str], retrieved_at_utc: str):
            rows, summary = original_fetch_hkex_actions(universe_codes, retrieved_at_utc)
            rows = _filter_action_rows(rows, cutoff_iso)
            out = dict(summary)
            out["row_count"] = len(rows)
            out["completed_session_cutoff"] = cutoff_iso
            return rows, out

        module.date = CutoffDate
        module.fetch_yahoo = fetch_yahoo_cutoff
        module.fetch_eastmoney = fetch_eastmoney_cutoff
        module.fetch_hkma_fx = fetch_hkma_fx_cutoff
        module.fetch_hkex_current_actions = fetch_hkex_actions_cutoff
        try:
            if output.exists():
                shutil.rmtree(output)
            output.mkdir(parents=True, exist_ok=True)
            module.build(output)
        finally:
            module.date = original_date
            module.fetch_yahoo = original_fetch_yahoo
            module.fetch_eastmoney = original_fetch_eastmoney
            module.fetch_hkma_fx = original_fetch_hkma_fx
            module.fetch_hkex_current_actions = original_fetch_hkex_actions
    finally:
        if str(scripts) in sys.path:
            sys.path.remove(str(scripts))

    overlay = _apply_hkex_current_action_overlay(repo_root, output)
    return _json(output / "FMDL5C_DECISION.json"), overlay


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
        fmdl5c, hkex_overlay = _build_fmdl5c(repo_root, fmdl5c_output, cutoff)
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

    price_path = fmdl5c_output / "FMDL5C_DAILY_PRICE_VOLUME.parquet"
    import pandas as pd
    prices = pd.read_parquet(price_path, columns=["observation_date"])
    if prices.empty:
        raise RuntimeError("FMDL5C_PRICE_STORE_EMPTY")
    actual_max = pd.to_datetime(prices["observation_date"], errors="coerce").max()
    if pd.isna(actual_max) or actual_max.date() > cutoff:
        raise RuntimeError(f"FMDL5C_PHYSICAL_PRICE_FILE_FUTURE_SESSION:{actual_max}:{cutoff}")

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
        "fmdl5c_physical_max_market_date": actual_max.date().isoformat(),
        "fmdl5c_source_security_count": (fmdl5c.get("metrics") or {}).get("source_security_count"),
        "fmdl5c_latest_price_success_ratio": (fmdl5c.get("metrics") or {}).get("latest_price_success_ratio"),
        "hkex_current_action_overlay": hkex_overlay,
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
