#!/usr/bin/env python3
"""Composite-history utilities for FMDL-2B-4.

The accepted FMDL-2B-2 base remains immutable. Current history is resolved as
base + validated incremental deltas + explicit full-series repair overrides.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.run_full_backfill_shard import shard_for_symbol

ROOT = Path(__file__).resolve().parents[1]
BASE_MANIFEST_PATH = ROOT / "outputs/history/candidate/HISTORICAL_STORE_MANIFEST.json"
BASE_RELEASE_PATH = ROOT / "outputs/history/candidate/HISTORICAL_STORE_RELEASE.json"
CURRENT_MANIFEST_PATH = ROOT / "outputs/history/current/HISTORY_CURRENT_MANIFEST.json"
CURRENT_RELEASE_PATH = ROOT / "outputs/history/current/HISTORY_CURRENT_RELEASE.json"
CURRENT_STATUS_PATH = ROOT / "outputs/history/current/HISTORY_CURRENT_STATUS.csv"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_path(value: str | Path, root: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def relative_path(path: Path, root: Path = ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def bootstrap_manifest(root: Path = ROOT) -> dict[str, Any]:
    base_manifest = read_json(root / BASE_MANIFEST_PATH.relative_to(ROOT))
    base_release = read_json(root / BASE_RELEASE_PATH.relative_to(ROOT))
    return {
        "manifest_version": "1.0.0",
        "release_id": f"FMDL2B4_BOOTSTRAP_{base_release['release_id']}",
        "as_of_date": base_release["as_of_date"],
        "base_release_id": base_release["release_id"],
        "base_manifest_path": relative_path(root / BASE_MANIFEST_PATH.relative_to(ROOT), root),
        "base_manifest_sha256": sha256_file(root / BASE_MANIFEST_PATH.relative_to(ROOT)),
        "logical_shards": int(base_manifest["shard_count"]),
        "delta_files": [],
        "repair_files": [],
        "status": "BOOTSTRAP_FROM_ACCEPTED_BASE",
        "authority": "HISTORICAL_AND_FACTOR_EVIDENCE_ONLY_NO_TRADE_AUTHORITY",
    }


def load_current_manifest(root: Path = ROOT) -> dict[str, Any]:
    path = root / CURRENT_MANIFEST_PATH.relative_to(ROOT)
    return read_json(path) if path.exists() else bootstrap_manifest(root)


def validate_component(entry: dict[str, Any], *, root: Path = ROOT) -> Path:
    path = resolve_path(str(entry["path"]), root)
    if not path.exists():
        raise RuntimeError(f"MISSING_HISTORY_COMPONENT_{entry.get('path')}")
    expected = str(entry.get("sha256", ""))
    if expected and sha256_file(path) != expected:
        raise RuntimeError(f"HISTORY_COMPONENT_HASH_MISMATCH_{entry.get('path')}")
    return path


def validate_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> None:
    base_manifest_path = resolve_path(str(manifest["base_manifest_path"]), root)
    if not base_manifest_path.exists():
        raise RuntimeError("MISSING_BASE_MANIFEST")
    if sha256_file(base_manifest_path) != manifest.get("base_manifest_sha256"):
        raise RuntimeError("BASE_MANIFEST_HASH_MISMATCH")
    base_manifest = read_json(base_manifest_path)
    if int(manifest.get("logical_shards", -1)) != int(base_manifest.get("shard_count", -2)):
        raise RuntimeError("LOGICAL_SHARD_COUNT_MISMATCH")
    for entry in [*manifest.get("delta_files", []), *manifest.get("repair_files", [])]:
        validate_component(entry, root=root)


def _base_shard_entry(manifest: dict[str, Any], shard_id: int, root: Path) -> dict[str, Any]:
    base_manifest = read_json(resolve_path(str(manifest["base_manifest_path"]), root))
    matches = [item for item in base_manifest["shards"] if int(item["shard_id"]) == shard_id]
    if len(matches) != 1:
        raise RuntimeError(f"BASE_SHARD_ENTRY_COUNT_{shard_id}_{len(matches)}")
    return matches[0]


def _read_component(entry: dict[str, Any], *, root: Path) -> pd.DataFrame:
    path = validate_component(entry, root=root)
    frame = pd.read_parquet(path)
    required = {
        "trade_date", "symbol", "open", "high", "low", "close", "volume_shares",
        "turnover_cny", "provider_id", "source_function", "adjustment_mode",
        "retrieved_at", "record_quality", "row_hash",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"HISTORY_COMPONENT_MISSING_COLUMNS_{sorted(missing)}")
    return frame


def load_composite_shard(
    manifest: dict[str, Any],
    shard_id: int,
    *,
    root: Path = ROOT,
) -> pd.DataFrame:
    """Resolve one shard: repair wins through its horizon; later deltas extend it."""

    validate_manifest(manifest, root=root)
    logical_shards = int(manifest["logical_shards"])
    base_entry = _base_shard_entry(manifest, shard_id, root)
    base_path = resolve_path(str(base_entry["path"]), root)
    if sha256_file(base_path) != base_entry.get("sha256"):
        raise RuntimeError(f"BASE_SHARD_HASH_MISMATCH_{shard_id}")
    base = pd.read_parquet(base_path)
    base = base.loc[
        base["symbol"].astype(str).map(lambda value: shard_for_symbol(value, logical_shards) == shard_id)
    ].copy()

    delta_frames: list[pd.DataFrame] = []
    for order, entry in enumerate(manifest.get("delta_files", []), start=1):
        frame = _read_component(entry, root=root)
        frame = frame.loc[
            frame["symbol"].astype(str).map(lambda value: shard_for_symbol(value, logical_shards) == shard_id)
        ].copy()
        if not frame.empty:
            frame["_precedence"] = 1_000_000 + order
            delta_frames.append(frame)

    repair_frames: list[pd.DataFrame] = []
    repair_cutoffs: dict[str, pd.Timestamp] = {}
    for order, entry in enumerate(manifest.get("repair_files", []), start=1):
        frame = _read_component(entry, root=root)
        frame = frame.loc[
            frame["symbol"].astype(str).map(lambda value: shard_for_symbol(value, logical_shards) == shard_id)
        ].copy()
        if not frame.empty:
            parsed_repair_dates = pd.to_datetime(frame["trade_date"], errors="coerce")
            if parsed_repair_dates.isna().any():
                raise RuntimeError(f"INVALID_REPAIR_DATE_SHARD_{shard_id}")
            local_cutoffs = pd.DataFrame({
                "symbol": frame["symbol"].astype(str),
                "trade_date": parsed_repair_dates,
            }).groupby("symbol")["trade_date"].max()
            for symbol, cutoff in local_cutoffs.items():
                previous = repair_cutoffs.get(str(symbol))
                if previous is None or cutoff > previous:
                    repair_cutoffs[str(symbol)] = cutoff
            frame["_precedence"] = 2_000_000 + order
            repair_frames.append(frame)

    base["_precedence"] = 0
    pieces = [base, *delta_frames]
    composite = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    if repair_cutoffs and not composite.empty:
        composite_dates = pd.to_datetime(composite["trade_date"], errors="coerce")
        if composite_dates.isna().any():
            raise RuntimeError(f"INVALID_COMPOSITE_DATE_SHARD_{shard_id}")
        cutoff_series = composite["symbol"].astype(str).map(repair_cutoffs)
        keep = cutoff_series.isna() | (composite_dates > cutoff_series)
        composite = composite.loc[keep].copy()
    if repair_frames:
        composite = pd.concat([composite, *repair_frames], ignore_index=True)
    if composite.empty:
        return composite

    composite["trade_date"] = pd.to_datetime(composite["trade_date"], errors="coerce")
    if composite["trade_date"].isna().any():
        raise RuntimeError(f"INVALID_COMPOSITE_DATE_SHARD_{shard_id}")
    composite = composite.sort_values(["symbol", "trade_date", "_precedence"])
    composite = composite.drop_duplicates(["symbol", "trade_date"], keep="last")
    composite = composite.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    composite["trade_date"] = composite["trade_date"].dt.date.astype(str)
    return composite.drop(columns=["_precedence"], errors="ignore")


def iter_composite_shards(
    manifest: dict[str, Any], *, root: Path = ROOT
) -> Iterable[tuple[int, pd.DataFrame]]:
    for shard_id in range(int(manifest["logical_shards"])):
        yield shard_id, load_composite_shard(manifest, shard_id, root=root)


def latest_observations(
    manifest: dict[str, Any], *, root: Path = ROOT
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, frame in iter_composite_shards(manifest, root=root):
        if frame.empty:
            continue
        local = frame.copy()
        local["trade_date"] = pd.to_datetime(local["trade_date"], errors="coerce")
        latest = local.sort_values(["symbol", "trade_date"]).groupby("symbol", as_index=False).tail(1)
        rows.append(latest)
    if not rows:
        return pd.DataFrame()
    output = pd.concat(rows, ignore_index=True)
    if output["symbol"].duplicated().any():
        raise RuntimeError("DUPLICATE_LATEST_OBSERVATION_SYMBOL")
    return output.sort_values("symbol").reset_index(drop=True)


def composite_metrics(manifest: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    total_rows = 0
    symbols: set[str] = set()
    duplicate_pairs = 0
    future_rows = 0
    impossible_ohlc = 0
    as_of = pd.Timestamp(manifest["as_of_date"])
    for _, frame in iter_composite_shards(manifest, root=root):
        total_rows += len(frame)
        symbols.update(frame["symbol"].astype(str))
        duplicate_pairs += int(frame.duplicated(["symbol", "trade_date"]).sum())
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        future_rows += int((dates > as_of).sum())
        prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").dropna()
        impossible_ohlc += int((
            (prices <= 0).any(axis=1)
            | (prices["high"] < prices[["open", "close", "low"]].max(axis=1))
            | (prices["low"] > prices[["open", "close", "high"]].min(axis=1))
        ).sum())
    return {
        "history_rows": int(total_rows),
        "history_symbols": int(len(symbols)),
        "duplicate_symbol_date_rows": int(duplicate_pairs),
        "future_rows": int(future_rows),
        "impossible_ohlc_rows": int(impossible_ohlc),
    }


def component_entry(path: Path, *, as_of_date: str, row_count: int, kind: str, root: Path = ROOT) -> dict[str, Any]:
    frame_symbols: list[str] = []
    if path.exists() and path.suffix == ".parquet":
        frame = pd.read_parquet(path, columns=["symbol"])
        frame_symbols = sorted(frame["symbol"].astype(str).unique().tolist())
    return {
        "kind": kind,
        "path": relative_path(path, root),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "row_count": int(row_count),
        "symbol_count": len(frame_symbols),
        "symbol_set_sha256": canonical_hash(frame_symbols),
        "as_of_date": as_of_date,
    }
