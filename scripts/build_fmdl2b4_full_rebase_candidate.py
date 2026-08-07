#!/usr/bin/env python3
"""Governed FMDL-2B-4 recovery for multi-session history gaps."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl2b4_history import (
    ROOT, canonical_hash, component_entry, composite_metrics, load_current_manifest,
    read_json, relative_path, sha256_file,
)
from scripts.run_full_backfill_shard import shard_for_symbol
from scripts.run_incremental_history_refresh import completed_sessions_between, load_status

TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl2_incremental_refresh.json"
BACKFILL_PLAN = ROOT / "config/fmdl2_full_backfill_plan.json"
CURRENT_RELEASE = ROOT / "outputs/current/CURRENT_RELEASE.json"
UNIVERSE = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
SNAPSHOT = ROOT / "outputs/current/DAILY_MARKET_SNAPSHOT.csv"
CANDIDATE = ROOT / "outputs/history/refresh_candidate"
PLAN = ROOT / "outputs/status/FMDL2B4_FULL_REBASE_PLAN.json"
USABLE = {"READY", "PARTIAL_FALLBACK_PRICE_AMOUNT"}


def _bool(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "y"}


def validate_recovery_gap(previous: str, target: str, sessions: list[str]) -> None:
    if target <= previous:
        raise RuntimeError("FULL_REBASE_TARGET_NOT_AFTER_CURRENT")
    if len(sessions) < 2:
        raise RuntimeError(f"FULL_REBASE_NOT_REQUIRED_GAP_{len(sessions)}")
    if sessions[-1] != target:
        raise RuntimeError("FULL_REBASE_SESSION_CALENDAR_NOT_AT_TARGET")


def recovery_context(root: Path = ROOT) -> tuple[dict, dict, str, str, list[str]]:
    release = read_json(root / CURRENT_RELEASE.relative_to(ROOT))
    prior = load_current_manifest(root)
    target, previous = str(release["as_of_date"]), str(prior["as_of_date"])
    sessions = completed_sessions_between(previous, target)
    validate_recovery_gap(previous, target, sessions)
    return release, prior, target, previous, sessions


def build_plan(root: Path = ROOT) -> dict:
    _, prior, target, previous, sessions = recovery_context(root)
    payload = {
        "status": "RECOVERY_REQUIRED", "previous_release_id": prior.get("release_id"),
        "previous_as_of_date": previous, "target_as_of_date": target,
        "missing_completed_sessions": sessions, "missing_completed_session_count": len(sessions),
        "recovery_mode": "FULL_SERIES_REPAIR_OVERLAY", "daily_incremental_gate_relaxed": False,
        "current_preserved_until_validation": True, "trade_authority": "NONE",
    }
    path = root / PLAN.relative_to(ROOT); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False)); return payload


def artifact_dirs(incoming: Path) -> list[Path]:
    return sorted({p.parent for p in incoming.rglob("shard_*_manifest.json")})


def build_candidate(incoming: Path, release_id: str, root: Path = ROOT) -> dict:
    config = read_json(root / CONFIG.relative_to(ROOT)); plan = read_json(root / BACKFILL_PLAN.relative_to(ROOT))
    current, prior, target, previous, sessions = recovery_context(root)
    universe = pd.read_csv(root / UNIVERSE.relative_to(ROOT), dtype={"symbol": str})
    snapshot = pd.read_csv(root / SNAPSHOT.relative_to(ROOT), dtype={"symbol": str})
    prior_status = load_status(root)
    errors: list[str] = []
    required = {"symbol", "board", "list_date", "is_st", "is_suspended"}
    if required.difference(universe.columns): errors.append("UNIVERSE_SCHEMA_MISSING")
    if universe["symbol"].duplicated().any(): errors.append("DUPLICATE_UNIVERSE_SYMBOL")
    if set(snapshot["symbol"].astype(str)) != set(universe["symbol"].astype(str)): errors.append("SNAPSHOT_UNIVERSE_SYMBOL_SET_MISMATCH")
    if set(snapshot["as_of_date"].astype(str)) != {target}: errors.append("SNAPSHOT_AS_OF_MISMATCH")
    if current.get("hard_failures"): errors.append("FMDL1_CURRENT_HAS_HARD_FAILURES")
    shards = int(prior["logical_shards"])
    if shards != int(plan["sharding"]["logical_shards"]): errors.append("RECOVERY_SHARD_CONTRACT_MISMATCH")

    dirs = artifact_dirs(incoming)
    if len(dirs) != shards: errors.append(f"RECOVERY_SHARD_MANIFEST_COUNT_{len(dirs)}_EXPECTED_{shards}")
    statuses, sources, seen = [], [], set()
    for directory in dirs:
        mpaths = list(directory.glob("shard_*_manifest.json"))
        if len(mpaths) != 1: errors.append(f"INVALID_RECOVERY_MANIFEST_COUNT_{directory.name}"); continue
        manifest = json.loads(mpaths[0].read_text(encoding="utf-8")); sid = int(manifest["shard_id"])
        if sid in seen: errors.append(f"DUPLICATE_RECOVERY_SHARD_{sid}"); continue
        seen.add(sid)
        if manifest.get("release_id") != release_id: errors.append(f"RECOVERY_RELEASE_ID_MISMATCH_SHARD_{sid}")
        if manifest.get("as_of_date") != target: errors.append(f"RECOVERY_AS_OF_MISMATCH_SHARD_{sid}")
        if int(manifest.get("total_shards", -1)) != shards: errors.append(f"RECOVERY_TOTAL_SHARDS_MISMATCH_{sid}")
        hp, sp = directory / manifest["history_file"], directory / manifest["status_file"]
        if not hp.exists() or sha256_file(hp) != manifest.get("history_sha256"): errors.append(f"RECOVERY_HISTORY_HASH_MISMATCH_{sid}")
        if not sp.exists() or sha256_file(sp) != manifest.get("status_sha256"): errors.append(f"RECOVERY_STATUS_HASH_MISMATCH_{sid}")
        if sp.exists():
            sf = pd.read_csv(sp, dtype={"symbol": str}); sf["assigned_shard"] = sid; statuses.append(sf)
        sources.append((hp, manifest))
    status = pd.concat(statuses, ignore_index=True) if statuses else pd.DataFrame()
    expected, actual = set(universe["symbol"].astype(str)), set(status["symbol"].astype(str)) if not status.empty else set()
    if len(status) != len(universe): errors.append(f"RECOVERY_STATUS_ROWS_{len(status)}_EXPECTED_{len(universe)}")
    if not status.empty and status["symbol"].duplicated().any(): errors.append("RECOVERY_DUPLICATE_SYMBOL_STATUS")
    if actual != expected: errors.append(f"RECOVERY_SYMBOL_SET_MISMATCH_{len(expected-actual)}_{len(actual-expected)}")
    if not status.empty:
        bad = sum(int(r.assigned_shard) != shard_for_symbol(str(r.symbol), shards) for r in status[["symbol", "assigned_shard"]].itertuples(index=False))
        if bad: errors.append(f"RECOVERY_SHARD_ASSIGNMENT_ERRORS_{bad}")
    if errors: raise RuntimeError(";".join(errors))

    umap, smap = universe.set_index("symbol").to_dict("index"), snapshot.set_index("symbol")
    pmap, rmap = prior_status.set_index("symbol").to_dict("index"), status.set_index("symbol").to_dict("index")
    accepted, rows, stale = set(), [], 0
    for symbol in universe["symbol"].astype(str):
        u, s, src, old = umap[symbol], smap.loc[symbol], rmap[symbol], pmap.get(symbol, {})
        state, dstatus, latest = str(src.get("state", "QUARANTINED")), str(s.get("data_status", "UNKNOWN")), src.get("latest_valid_date")
        usable = state in USABLE; fresh = dstatus != "TRADED" or str(latest) == target; ok = usable and fresh
        if usable and dstatus == "TRADED" and not fresh: stale += 1
        if ok: accepted.add(symbol)
        rstate = "REPAIRED_FULL_HISTORY" if ok and dstatus == "TRADED" else "READY_SUSPENDED_NO_APPEND" if ok else "QUARANTINED"
        reason = f"MULTI_SESSION_GAP_{len(sessions)}_FULL_REBASE" if rstate == "REPAIRED_FULL_HISTORY" else f"FULL_REBASE_{dstatus}" if ok else str(src.get("quarantine_reason") or ("RECOVERY_SOURCE_STALE_AT_TARGET" if usable else "RECOVERY_SOURCE_UNUSABLE"))
        rows.append({
            "symbol": symbol, "board": str(u["board"]), "list_date": u.get("list_date"), "is_st": _bool(u.get("is_st")),
            "is_suspended": _bool(u.get("is_suspended")), "as_of_date": target, "previous_as_of_date": previous,
            "refresh_state": rstate, "refresh_reason": reason, "provider_id": str(src.get("provider_id") or old.get("provider_id") or "NONE"),
            "latest_history_date": str(latest) if ok else old.get("latest_history_date"), "last_close": old.get("last_close"),
            "continuity_expected_prior": None, "continuity_difference": None,
        })

    repair_root = root / config["composite_store"]["repair_path"] / release_id
    if repair_root.exists(): shutil.rmtree(repair_root)
    repair_root.mkdir(parents=True, exist_ok=True)
    new_entries, repair_rows = [], 0
    for hp, manifest in sorted(sources, key=lambda x: int(x[1]["shard_id"])):
        frame = pd.read_parquet(hp); frame["symbol"] = frame["symbol"].astype(str); frame = frame[frame["symbol"].isin(accepted)].copy()
        if frame.empty: continue
        sid = int(manifest["shard_id"]); out = repair_root / f"shard_{sid:02d}_full_rebase.parquet"; frame.to_parquet(out, index=False, compression="zstd")
        entry = component_entry(out, as_of_date=target, row_count=len(frame), kind="FULL_REBASE_REPAIR", root=root)
        entry.update({"logical_shard_id": sid, "recovery_release_id": release_id}); new_entries.append(entry); repair_rows += len(frame)

    sframe = pd.DataFrame(rows).sort_values(["board", "symbol"]).reset_index(drop=True)
    latest_map = {}
    for entry in new_entries:
        f = pd.read_parquet(root / entry["path"], columns=["symbol", "trade_date", "close"]); f["trade_date"] = pd.to_datetime(f["trade_date"], errors="coerce")
        for r in f.sort_values(["symbol", "trade_date"]).groupby("symbol", as_index=False).tail(1).itertuples(index=False):
            latest_map[str(r.symbol)] = (r.trade_date.date().isoformat(), None if pd.isna(r.close) else float(r.close))
    for i, r in sframe.iterrows():
        if str(r["symbol"]) in latest_map: sframe.at[i, "latest_history_date"], sframe.at[i, "last_close"] = latest_map[str(r["symbol"])]

    croot = root / CANDIDATE.relative_to(ROOT)
    if croot.exists(): shutil.rmtree(croot)
    croot.mkdir(parents=True, exist_ok=True)
    spath, dpath = croot / "HISTORY_CURRENT_STATUS.csv", croot / "HISTORY_CONTINUITY_DIAGNOSTICS.csv"
    sframe.to_csv(spath, index=False, encoding="utf-8-sig")
    sframe[["symbol", "as_of_date", "previous_as_of_date", "refresh_state", "refresh_reason", "provider_id", "latest_history_date"]].to_csv(dpath, index=False, encoding="utf-8-sig")
    repairs = [*prior.get("repair_files", []), *new_entries]; deltas = list(prior.get("delta_files", [])); generated = datetime.now(TZ).isoformat(timespec="seconds")
    manifest = {
        "manifest_version": "1.0.0", "release_id": release_id, "generated_at": generated, "as_of_date": target,
        "previous_release_id": prior.get("release_id"), "previous_as_of_date": previous, "base_release_id": prior["base_release_id"],
        "base_manifest_path": prior["base_manifest_path"], "base_manifest_sha256": prior["base_manifest_sha256"], "logical_shards": shards,
        "delta_files": deltas, "repair_files": repairs, "status_path": relative_path(spath, root), "status_sha256": sha256_file(spath),
        "continuity_diagnostics_path": relative_path(dpath, root), "continuity_diagnostics_sha256": sha256_file(dpath),
        "component_aggregate_sha256": canonical_hash([*deltas, *repairs]), "status": "CANDIDATE_BUILT",
        "recovery": {"mode": "FULL_SERIES_REPAIR_OVERLAY", "missing_completed_session_count": len(sessions), "missing_completed_sessions": sessions,
                     "new_repair_component_count": len(new_entries), "current_preserved_until_publication": True},
        "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }
    mpath = croot / "HISTORY_CURRENT_MANIFEST.json"; mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = composite_metrics(manifest, root=root)
    traded = set(snapshot.loc[snapshot["data_status"].astype(str) == "TRADED", "symbol"].astype(str)); repaired = set(sframe.loc[sframe["refresh_state"] == "REPAIRED_FULL_HISTORY", "symbol"].astype(str))
    ratio = len(traded & repaired) / len(traded) if traded else 1.0; unresolved = int(sframe["refresh_state"].isin(["QUARANTINED", "REPAIR_REQUIRED"]).sum()); suspended = int((sframe["refresh_state"] == "READY_SUSPENDED_NO_APPEND").sum())
    if ratio < float(config["daily_fast_path"]["minimum_market_append_ratio"]): errors.append(f"RECOVERY_CURRENT_SESSION_RATIO_{ratio:.6f}_BELOW_GATE")
    if metrics["duplicate_symbol_date_rows"]: errors.append("COMPOSITE_DUPLICATE_SYMBOL_DATE")
    if metrics["future_rows"]: errors.append("COMPOSITE_FUTURE_ROWS")
    if metrics["impossible_ohlc_rows"]: errors.append("COMPOSITE_IMPOSSIBLE_OHLC")
    for board, group in status.groupby("board"):
        bratio = float(group["state"].isin(USABLE).mean()) if len(group) else 1.0
        if bratio < float(plan["quality_gates"]["minimum_board_usable_ratio"]): errors.append(f"RECOVERY_BOARD_USABLE_RATIO_BELOW_GATE_{board}_{bratio:.6f}")
    warnings = [f"FULL_REBASE_GAP_SESSIONS_{len(sessions)}"] + ([f"UNRESOLVED_HISTORY_SYMBOLS_{unresolved}"] if unresolved else []) + ([f"SUSPENDED_NO_APPEND_{suspended}"] if suspended else []) + ([f"STALE_TRADED_SOURCE_SERIES_{stale}"] if stale else [])
    quality = {
        "quality_version": "1.0.0", "run_id": release_id, "generated_at": generated, "as_of_date": target, "previous_as_of_date": previous,
        "status": "FAIL" if errors else "PASS_WITH_WARNINGS", "hard_failures": errors, "controlled_warnings": warnings,
        "metrics": {**metrics, "universe_symbols": len(universe), "traded_snapshot_symbols": len(traded), "incremental_rows": 0,
                    "repaired_symbols": int((sframe["refresh_state"] == "REPAIRED_FULL_HISTORY").sum()), "repair_rows": int(repair_rows),
                    "suspended_no_append": suspended, "unresolved_history_symbols": unresolved, "accepted_current_session_ratio": round(ratio, 8),
                    "delta_file_count": len(deltas), "repair_file_count": len(repairs), "new_repair_file_count": len(new_entries),
                    "missing_completed_session_count": len(sessions)},
        "current_preserved_on_failure": True, "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }
    qpath = croot / "HISTORY_REFRESH_QUALITY.json"; qpath.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest.update({"quality_path": relative_path(qpath, root), "quality_sha256": sha256_file(qpath), "status": "CANDIDATE_PASS" if not errors else "CANDIDATE_FAIL"})
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"report_version": "1.0.0", "run_id": release_id, "as_of_date": target, "previous_as_of_date": previous,
              "status": quality["status"], "recovery_mode": "FULL_SERIES_REPAIR_OVERLAY", "metrics": quality["metrics"],
              "hard_failures": errors, "controlled_warnings": warnings, "history_candidate_manifest": relative_path(mpath, root),
              "non_claims": ["NO_DAILY_INCREMENTAL_GATE_RELAXATION", "NO_CANDIDATE_POOL_CHANGE", "NO_SIMULATION_OR_REAL_PORTFOLIO_CHANGE", "NO_TRADE_AUTHORITY"],
              "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY"}
    (croot / "FMDL2B4_HISTORY_REFRESH_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if errors: raise RuntimeError(";".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--incoming"); parser.add_argument("--release-id"); parser.add_argument("--plan-only", action="store_true"); args = parser.parse_args()
    try:
        if args.plan_only: build_plan(ROOT); return 0
        if not args.incoming or not args.release_id: parser.error("--incoming and --release-id are required unless --plan-only is used")
        build_candidate(Path(args.incoming), str(args.release_id), ROOT); return 0
    except Exception as exc:
        print(f"FMDL-2B-4 full rebase failed: {type(exc).__name__}: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": sys.exit(main())
