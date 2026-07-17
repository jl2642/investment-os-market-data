#!/usr/bin/env python3
"""Independently validate an FMDL-2B-3 basic-factor candidate."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
import pandas as pd

from scripts.run_basic_factor_engine import (
    EXPECTED_FACTOR_IDS,
    ROOT,
    canonical_hash,
    read_json,
    sha256_file,
)

CANDIDATE = ROOT / "outputs/factors/candidate"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
HISTORY_STATUS_PATH = ROOT / "outputs/history/candidate/HISTORICAL_SYMBOL_STATUS.csv"
SCHEMA_PATH = ROOT / "schemas/fmdl2_basic_factor_manifest.schema.json"


def resolve_artifact(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def row_hash(frame: pd.DataFrame, index: int) -> str:
    row = frame.loc[index].drop(labels=["row_hash"]).to_dict()
    return canonical_hash(row)


def main() -> int:
    manifest = read_json(CANDIDATE / "BASIC_FACTOR_MANIFEST.json")
    quality = read_json(CANDIDATE / "BASIC_FACTOR_QUALITY.json")
    report = read_json(CANDIDATE / "FMDL2B3_RUN_REPORT.json")
    schema = read_json(SCHEMA_PATH)
    registry = read_json(ROOT / "config/fmdl2_factor_registry.json")
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": str})
    history_status = pd.read_csv(HISTORY_STATUS_PATH, dtype={"symbol": str})
    wide = pd.read_parquet(CANDIDATE / "BASIC_FACTOR_TABLE.parquet")
    detail = pd.read_parquet(CANDIDATE / "BASIC_FACTOR_DETAIL.parquet")
    status = pd.read_csv(CANDIDATE / "BASIC_FACTOR_STATUS.csv", dtype={"symbol": str})

    errors: list[str] = []
    warnings: list[str] = []

    schema_errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda item: list(item.path))
    errors.extend(f"MANIFEST_SCHEMA_{item.message}" for item in schema_errors)

    artifact_rows = {item["dataset_id"]: int(item["row_count"]) for item in manifest.get("artifacts", [])}
    for item in manifest.get("artifacts", []):
        path = resolve_artifact(str(item["path"]))
        if not path.exists():
            errors.append(f"MISSING_ARTIFACT_{item['dataset_id']}")
            continue
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"ARTIFACT_HASH_MISMATCH_{item['dataset_id']}")
        if path.stat().st_size != int(item.get("bytes", -1)):
            errors.append(f"ARTIFACT_BYTE_MISMATCH_{item['dataset_id']}")
    if canonical_hash(manifest.get("artifacts", [])) != manifest.get("aggregate_sha256"):
        errors.append("MANIFEST_AGGREGATE_HASH_MISMATCH")

    factor_ids = {item["factor_id"] for item in registry["factors"]}
    if factor_ids != EXPECTED_FACTOR_IDS:
        errors.append("REGISTRY_IMPLEMENTATION_FACTOR_SET_MISMATCH")
    if int(manifest.get("factor_count", -1)) != len(factor_ids):
        errors.append("MANIFEST_FACTOR_COUNT_MISMATCH")

    universe_symbols = set(universe["symbol"].astype(str))
    if len(wide) != len(universe) or set(wide["symbol"].astype(str)) != universe_symbols:
        errors.append("WIDE_UNIVERSE_COVERAGE_MISMATCH")
    if len(status) != len(universe) or set(status["symbol"].astype(str)) != universe_symbols:
        errors.append("STATUS_UNIVERSE_COVERAGE_MISMATCH")
    if wide["symbol"].duplicated().any():
        errors.append("DUPLICATE_WIDE_SYMBOL")
    if status["symbol"].duplicated().any():
        errors.append("DUPLICATE_STATUS_SYMBOL")

    expected_detail_rows = len(universe) * len(factor_ids)
    if len(detail) != expected_detail_rows:
        errors.append(f"DETAIL_ROW_COUNT_{len(detail)}_EXPECTED_{expected_detail_rows}")
    if detail.duplicated(["symbol", "factor_id"]).any():
        errors.append("DUPLICATE_SYMBOL_FACTOR")
    detail_factor_ids = set(detail["factor_id"].astype(str))
    if detail_factor_ids != factor_ids:
        errors.append("DETAIL_FACTOR_SET_MISMATCH")
    counts = detail.groupby("symbol")["factor_id"].nunique()
    if not counts.eq(len(factor_ids)).all():
        errors.append("NOT_EXACTLY_ONE_ROW_PER_SYMBOL_FACTOR")

    as_of = str(manifest.get("as_of_date"))
    if set(wide["as_of_date"].astype(str)) != {as_of}:
        errors.append("WIDE_AS_OF_MISMATCH")
    if set(detail["as_of_date"].astype(str)) != {as_of}:
        errors.append("DETAIL_AS_OF_MISMATCH")
    if report.get("as_of_date") != as_of or quality.get("as_of_date") != as_of:
        errors.append("REPORT_QUALITY_AS_OF_MISMATCH")

    quarantined = set(history_status.loc[history_status["state"] == "QUARANTINED", "symbol"].astype(str))
    blocked = set(status.loc[status["factor_record_quality"] == "BLOCKED", "symbol"].astype(str))
    if blocked != quarantined:
        errors.append(f"BLOCKED_QUARANTINE_SET_MISMATCH_BLOCKED_{len(blocked)}_QUARANTINED_{len(quarantined)}")
    blocked_detail = detail.loc[detail["symbol"].isin(blocked)]
    if blocked_detail["availability_flag"].astype(bool).any():
        errors.append("BLOCKED_SYMBOL_HAS_AVAILABLE_FACTOR")
    if blocked_detail["factor_value"].notna().any():
        errors.append("BLOCKED_SYMBOL_HAS_FACTOR_VALUE")
    if blocked_detail["broad_market_percentile"].notna().any() or blocked_detail["board_neutral_percentile"].notna().any():
        errors.append("BLOCKED_SYMBOL_HAS_PERCENTILE")

    missing = ~detail["availability_flag"].astype(bool)
    if detail.loc[missing, "factor_value"].notna().any():
        errors.append("UNAVAILABLE_FACTOR_HAS_VALUE")
    if detail.loc[missing, "missing_reason_code"].isna().any():
        errors.append("UNAVAILABLE_FACTOR_MISSING_REASON")
    if detail.loc[missing, "broad_market_percentile"].notna().any():
        errors.append("MISSING_FACTOR_ASSIGNED_BROAD_PERCENTILE")
    if detail.loc[missing, "board_neutral_percentile"].notna().any():
        errors.append("MISSING_FACTOR_ASSIGNED_BOARD_PERCENTILE")
    if detail.loc[missing, "winsorized_zscore"].notna().any():
        errors.append("MISSING_FACTOR_ASSIGNED_ZSCORE")

    for column in ("broad_market_percentile", "board_neutral_percentile"):
        values = pd.to_numeric(detail[column], errors="coerce").dropna()
        if ((values <= 0) | (values > 1)).any():
            errors.append(f"PERCENTILE_OUT_OF_RANGE_{column}")
    zscores = pd.to_numeric(detail["winsorized_zscore"], errors="coerce").dropna()
    if not zscores.map(math.isfinite).all():
        errors.append("NON_FINITE_ZSCORE")

    prohibited_fragments = ("buy_permission", "sell_permission", "add_permission", "trade_permission", "target_weight")
    output_columns = {str(column).lower() for column in [*wide.columns, *detail.columns, *status.columns]}
    for fragment in prohibited_fragments:
        if any(fragment in column for column in output_columns):
            errors.append(f"PROHIBITED_OUTPUT_COLUMN_{fragment}")

    sample_indexes = sorted(set([0, max(0, len(wide) // 2), max(0, len(wide) - 1)]))
    for index in sample_indexes:
        if str(wide.loc[index, "row_hash"]) != row_hash(wide, index):
            errors.append(f"WIDE_ROW_HASH_MISMATCH_{index}")
    detail_indexes = sorted(set([0, max(0, len(detail) // 2), max(0, len(detail) - 1)]))
    for index in detail_indexes:
        if str(detail.loc[index, "row_hash"]) != row_hash(detail, index):
            errors.append(f"DETAIL_ROW_HASH_MISMATCH_{index}")

    if artifact_rows.get("basic_factor_table") != len(wide):
        errors.append("MANIFEST_WIDE_ROW_COUNT_MISMATCH")
    if artifact_rows.get("basic_factor_detail") != len(detail):
        errors.append("MANIFEST_DETAIL_ROW_COUNT_MISMATCH")
    if artifact_rows.get("basic_factor_status") != len(status):
        errors.append("MANIFEST_STATUS_ROW_COUNT_MISMATCH")

    if quality.get("hard_failures"):
        errors.append("QUALITY_REPORT_HAS_HARD_FAILURES")
    if report.get("hard_failures"):
        errors.append("RUN_REPORT_HAS_HARD_FAILURES")
    if manifest.get("authority") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("MANIFEST_AUTHORITY_MISMATCH")
    if quality.get("authority") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("QUALITY_AUTHORITY_MISMATCH")
    if report.get("authority") != "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY":
        errors.append("REPORT_AUTHORITY_MISMATCH")

    if blocked:
        warnings.append(f"CONTROLLED_BLOCKED_SYMBOLS_{len(blocked)}")
    partial = int((status["factor_record_quality"] == "PARTIAL").sum())
    suspect = int((status["factor_record_quality"] == "SUSPECT").sum())
    if partial:
        warnings.append(f"PARTIAL_SYMBOLS_{partial}")
    if suspect:
        warnings.append(f"SUSPECT_SYMBOLS_{suspect}")

    validation = {
        "validation_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "controlled_warnings": warnings,
        "metrics": {
            "universe_symbols": int(len(universe)),
            "wide_rows": int(len(wide)),
            "detail_rows": int(len(detail)),
            "factor_count": int(len(factor_ids)),
            "blocked_symbols": int(len(blocked)),
            "partial_symbols": partial,
            "suspect_symbols": suspect,
            "available_factor_values": int(detail["availability_flag"].astype(bool).sum()),
            "missing_factor_values": int((~detail["availability_flag"].astype(bool)).sum()),
        },
        "authority": "VALIDATION_ONLY_NO_FACTOR_ALPHA_NO_TRADE_AUTHORITY",
    }
    output = ROOT / "diagnostics/FMDL2B3_CANDIDATE_VALIDATION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
