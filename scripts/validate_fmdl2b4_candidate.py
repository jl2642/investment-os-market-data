#!/usr/bin/env python3
"""Independently validate staged FMDL-2B-4 history and factor candidates."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

from scripts.fmdl2b4_history import ROOT, canonical_hash, composite_metrics, read_json, resolve_path, sha256_file, validate_manifest
from scripts.run_basic_factor_engine import EXPECTED_FACTOR_IDS

HISTORY_ROOT = ROOT / "outputs/history/refresh_candidate"
FACTOR_ROOT = ROOT / "outputs/factors/refresh_candidate"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"
FACTOR_REGISTRY_PATH = ROOT / "config/fmdl2_factor_registry.json"


def _recompute_row_hash(frame: pd.DataFrame, index: int) -> str:
    payload = frame.loc[index].drop(labels=["row_hash"]).to_dict()
    return canonical_hash(payload)


def _validate_component_row_hashes(path: Path, errors: list[str]) -> None:
    frame = pd.read_parquet(path)
    if "row_hash" not in frame.columns:
        errors.append(f"COMPONENT_MISSING_ROW_HASH_{path.name}")
        return
    for index in range(len(frame)):
        if str(frame.loc[index, "row_hash"]) != _recompute_row_hash(frame, index):
            errors.append(f"COMPONENT_ROW_HASH_MISMATCH_{path.name}_{index}")
            break


def _validate_artifacts(manifest: dict[str, Any], errors: list[str]) -> None:
    artifacts = manifest.get("artifacts", [])
    for item in artifacts:
        path = resolve_path(str(item["path"]))
        if not path.exists():
            errors.append(f"MISSING_FACTOR_ARTIFACT_{item['dataset_id']}")
            continue
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"FACTOR_ARTIFACT_HASH_MISMATCH_{item['dataset_id']}")
        if path.stat().st_size != int(item.get("bytes", -1)):
            errors.append(f"FACTOR_ARTIFACT_BYTES_MISMATCH_{item['dataset_id']}")
    if canonical_hash(artifacts) != manifest.get("aggregate_sha256"):
        errors.append("FACTOR_ARTIFACT_AGGREGATE_HASH_MISMATCH")


def main() -> int:
    history_manifest_path = HISTORY_ROOT / "HISTORY_CURRENT_MANIFEST.json"
    history_quality_path = HISTORY_ROOT / "HISTORY_REFRESH_QUALITY.json"
    history_status_path = HISTORY_ROOT / "HISTORY_CURRENT_STATUS.csv"
    factor_manifest_path = FACTOR_ROOT / "BASIC_FACTOR_MANIFEST.json"
    factor_quality_path = FACTOR_ROOT / "BASIC_FACTOR_QUALITY.json"
    factor_status_path = FACTOR_ROOT / "BASIC_FACTOR_STATUS.csv"
    factor_wide_path = FACTOR_ROOT / "BASIC_FACTOR_TABLE.parquet"
    factor_detail_path = FACTOR_ROOT / "BASIC_FACTOR_DETAIL.parquet"

    history_manifest = read_json(history_manifest_path)
    history_quality = read_json(history_quality_path)
    factor_manifest = read_json(factor_manifest_path)
    factor_quality = read_json(factor_quality_path)
    current_release = read_json(CURRENT_RELEASE_PATH)
    factor_registry = read_json(FACTOR_REGISTRY_PATH)
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})
    history_status = pd.read_csv(history_status_path, dtype={"symbol": str})
    factor_status = pd.read_csv(factor_status_path, dtype={"symbol": str})
    wide = pd.read_parquet(factor_wide_path)
    detail = pd.read_parquet(factor_detail_path)

    errors: list[str] = []
    warnings: list[str] = []
    try:
        validate_manifest(history_manifest)
    except Exception as exc:
        errors.append(f"HISTORY_MANIFEST_{type(exc).__name__}_{exc}")
    if history_manifest.get("status") != "CANDIDATE_PASS":
        errors.append("HISTORY_CANDIDATE_NOT_PASS")
    if history_quality.get("hard_failures"):
        errors.append("HISTORY_QUALITY_HAS_HARD_FAILURES")
    if factor_manifest.get("status") != "CANDIDATE_GENERATED":
        errors.append("FACTOR_CANDIDATE_NOT_GENERATED")
    if factor_quality.get("hard_failures"):
        errors.append("FACTOR_QUALITY_HAS_HARD_FAILURES")

    as_of = str(current_release["as_of_date"])
    if str(history_manifest.get("as_of_date")) != as_of:
        errors.append("HISTORY_AS_OF_NOT_CURRENT")
    if str(factor_manifest.get("as_of_date")) != as_of:
        errors.append("FACTOR_AS_OF_NOT_CURRENT")
    if str(factor_manifest.get("history_release_id")) != str(history_manifest.get("release_id")):
        errors.append("FACTOR_HISTORY_RELEASE_ID_MISMATCH")
    if sha256_file(history_manifest_path) != factor_manifest.get("history_manifest_sha256"):
        errors.append("FACTOR_HISTORY_MANIFEST_HASH_MISMATCH")

    universe_symbols = set(universe["symbol"].astype(str))
    for name, frame in (("history_status", history_status), ("factor_status", factor_status), ("wide", wide)):
        if len(frame) != len(universe):
            errors.append(f"{name.upper()}_ROW_COUNT_{len(frame)}_EXPECTED_{len(universe)}")
        if frame["symbol"].duplicated().any():
            errors.append(f"DUPLICATE_{name.upper()}_SYMBOL")
        if set(frame["symbol"].astype(str)) != universe_symbols:
            errors.append(f"{name.upper()}_UNIVERSE_SET_MISMATCH")

    factor_ids = {item["factor_id"] for item in factor_registry["factors"]}
    if factor_ids != EXPECTED_FACTOR_IDS:
        errors.append("FACTOR_REGISTRY_IMPLEMENTATION_MISMATCH")
    expected_detail = len(universe) * len(factor_ids)
    if len(detail) != expected_detail:
        errors.append(f"DETAIL_ROWS_{len(detail)}_EXPECTED_{expected_detail}")
    if detail.duplicated(["symbol", "factor_id"]).any():
        errors.append("DUPLICATE_SYMBOL_FACTOR")
    if set(detail["factor_id"].astype(str)) != factor_ids:
        errors.append("DETAIL_FACTOR_SET_MISMATCH")
    per_symbol = detail.groupby("symbol")["factor_id"].nunique()
    if not per_symbol.eq(len(factor_ids)).all():
        errors.append("INCOMPLETE_SYMBOL_FACTOR_MATRIX")

    missing = ~detail["availability_flag"].astype(bool)
    if detail.loc[missing, "factor_value"].notna().any():
        errors.append("MISSING_FACTOR_HAS_VALUE")
    if detail.loc[missing, "missing_reason_code"].isna().any():
        errors.append("MISSING_FACTOR_WITHOUT_REASON")
    for column in ("broad_market_percentile", "board_neutral_percentile", "winsorized_zscore"):
        if detail.loc[missing, column].notna().any():
            errors.append(f"MISSING_FACTOR_HAS_{column.upper()}")
    for column in ("broad_market_percentile", "board_neutral_percentile"):
        values = pd.to_numeric(detail[column], errors="coerce").dropna()
        if ((values <= 0) | (values > 1)).any():
            errors.append(f"PERCENTILE_OUT_OF_RANGE_{column}")
    zscores = pd.to_numeric(detail["winsorized_zscore"], errors="coerce").dropna()
    if not zscores.map(math.isfinite).all():
        errors.append("NON_FINITE_ZSCORE")

    blocked_history = set(history_status.loc[
        history_status["refresh_state"].isin(["QUARANTINED", "REPAIR_REQUIRED"]), "symbol"
    ].astype(str))
    blocked_factor = set(factor_status.loc[factor_status["factor_record_quality"] == "BLOCKED", "symbol"].astype(str))
    if blocked_history != blocked_factor:
        errors.append(
            f"BLOCKED_HISTORY_FACTOR_SET_MISMATCH_{len(blocked_history)}_{len(blocked_factor)}"
        )
    blocked_detail = detail.loc[detail["symbol"].astype(str).isin(blocked_factor)]
    if blocked_detail["availability_flag"].astype(bool).any():
        errors.append("BLOCKED_SYMBOL_HAS_AVAILABLE_FACTOR")

    metrics = composite_metrics(history_manifest)
    if metrics["duplicate_symbol_date_rows"]:
        errors.append("COMPOSITE_DUPLICATE_SYMBOL_DATE")
    if metrics["future_rows"]:
        errors.append("COMPOSITE_FUTURE_ROWS")
    if metrics["impossible_ohlc_rows"]:
        errors.append("COMPOSITE_IMPOSSIBLE_OHLC")
    if int(history_quality["metrics"]["history_rows"]) != metrics["history_rows"]:
        errors.append("COMPOSITE_ROW_COUNT_QUALITY_MISMATCH")
    if int(history_quality["metrics"]["history_symbols"]) != metrics["history_symbols"]:
        errors.append("COMPOSITE_SYMBOL_COUNT_QUALITY_MISMATCH")

    for entry in history_manifest.get("delta_files", []):
        _validate_component_row_hashes(resolve_path(str(entry["path"])), errors)
    for entry in history_manifest.get("repair_files", []):
        _validate_component_row_hashes(resolve_path(str(entry["path"])), errors)
    _validate_artifacts(factor_manifest, errors)

    wide_indexes = sorted(set([0, max(0, len(wide) // 2), max(0, len(wide) - 1)]))
    for index in wide_indexes:
        if str(wide.loc[index, "row_hash"]) != _recompute_row_hash(wide, index):
            errors.append(f"WIDE_ROW_HASH_MISMATCH_{index}")
    detail_indexes = sorted(set([0, max(0, len(detail) // 2), max(0, len(detail) - 1)]))
    for index in detail_indexes:
        if str(detail.loc[index, "row_hash"]) != _recompute_row_hash(detail, index):
            errors.append(f"DETAIL_ROW_HASH_MISMATCH_{index}")

    prohibited = ("buy_permission", "sell_permission", "add_permission", "trade_permission", "target_weight")
    columns = {str(column).lower() for column in [*history_status.columns, *factor_status.columns, *wide.columns, *detail.columns]}
    for fragment in prohibited:
        if any(fragment in column for column in columns):
            errors.append(f"PROHIBITED_OUTPUT_COLUMN_{fragment}")

    unresolved = int(history_status["refresh_state"].isin(["QUARANTINED", "REPAIR_REQUIRED"]).sum())
    partial = int((factor_status["factor_record_quality"] == "PARTIAL").sum())
    suspect = int((factor_status["factor_record_quality"] == "SUSPECT").sum())
    if unresolved:
        warnings.append(f"UNRESOLVED_HISTORY_SYMBOLS_{unresolved}")
    if partial:
        warnings.append(f"PARTIAL_FACTOR_SYMBOLS_{partial}")
    if suspect:
        warnings.append(f"SUSPECT_FACTOR_SYMBOLS_{suspect}")

    validation = {
        "validation_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "as_of_date": as_of,
        "history_release_id": history_manifest.get("release_id"),
        "factor_release_id": factor_manifest.get("run_id"),
        "errors": errors,
        "controlled_warnings": warnings,
        "metrics": {
            "universe_symbols": int(len(universe)),
            "history_rows": metrics["history_rows"],
            "history_symbols": metrics["history_symbols"],
            "wide_rows": int(len(wide)),
            "detail_rows": int(len(detail)),
            "factor_count": int(len(factor_ids)),
            "blocked_symbols": int(len(blocked_factor)),
            "partial_symbols": partial,
            "suspect_symbols": suspect,
            "available_factor_values": int(detail["availability_flag"].astype(bool).sum()),
            "missing_factor_values": int((~detail["availability_flag"].astype(bool)).sum()),
        },
        "authority": "VALIDATION_ONLY_NO_FACTOR_ALPHA_NO_TRADE_AUTHORITY",
    }
    output = ROOT / "diagnostics/FMDL2B4_CANDIDATE_VALIDATION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
