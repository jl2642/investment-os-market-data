#!/usr/bin/env python3
"""Calculate an FMDL-2B-4 factor candidate from staged composite history."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl2b4_history import ROOT, canonical_hash, iter_composite_shards, read_json, relative_path, sha256_file
from scripts.run_basic_factor_engine import (
    EXPECTED_FACTOR_IDS,
    add_cross_sectional_fields,
    add_row_hashes,
    build_wide_table,
    compute_symbol_factor_values,
    quality_payload,
)

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
HISTORY_CANDIDATE = ROOT / "outputs/history/refresh_candidate/HISTORY_CURRENT_MANIFEST.json"
HISTORY_QUALITY = ROOT / "outputs/history/refresh_candidate/HISTORY_REFRESH_QUALITY.json"
HISTORY_STATUS = ROOT / "outputs/history/refresh_candidate/HISTORY_CURRENT_STATUS.csv"
UNIVERSE_PATH = ROOT / "outputs/current/A_SHARE_UNIVERSE.csv"
CURRENT_RELEASE_PATH = ROOT / "outputs/current/CURRENT_RELEASE.json"
FACTOR_REGISTRY_PATH = ROOT / "config/fmdl2_factor_registry.json"
FACTOR_ENGINE_CONFIG_PATH = ROOT / "config/fmdl2_factor_engine.json"
OUTPUT_DIR = ROOT / "outputs/factors/refresh_candidate"


def _history_state_for_factor(refresh_state: str, provider_id: str) -> str:
    if refresh_state in {"READY_INCREMENTAL", "READY_SUSPENDED_NO_APPEND", "REPAIRED_FULL_HISTORY"}:
        return "PARTIAL_FALLBACK_PRICE_AMOUNT" if provider_id == "tencent_hist" else "READY"
    return "QUARANTINED"


def _market_calendar(history_manifest: dict[str, Any], root: Path) -> pd.DatetimeIndex:
    date_parts: list[pd.Series] = []
    for _, frame in iter_composite_shards(history_manifest, root=root):
        if not frame.empty:
            parsed = pd.to_datetime(frame["trade_date"], errors="coerce")
            date_parts.append(parsed.dropna())
    if not date_parts:
        raise RuntimeError("EMPTY_COMPOSITE_HISTORY_CALENDAR")
    return pd.DatetimeIndex(pd.concat(date_parts, ignore_index=True).drop_duplicates().sort_values())


def _normalize_composite_lineage(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Keep source lineage in history while presenting an explicit validated composite to factors."""
    output = frame.copy()
    providers = set(output["provider_id"].dropna().astype(str))
    adjustments = set(output["adjustment_mode"].dropna().astype(str))
    allowed_adjustments = {"qfq", "qfq_current_session_equivalent"}
    allowed_incremental = output.loc[
        output["adjustment_mode"].astype(str).eq("qfq_current_session_equivalent"), "record_quality"
    ].astype(str).isin({"VALIDATED_INCREMENTAL"}).all()
    if not adjustments.issubset(allowed_adjustments) or not allowed_incremental:
        return output, "UNVALIDATED_COMPOSITE_LINEAGE"
    if len(providers) > 1 or len(adjustments) > 1:
        output["provider_id"] = "COMPOSITE_VALIDATED"
        output["adjustment_mode"] = "qfq"
        return output, "COMPOSITE_VALIDATED"
    return output, "SINGLE_SERIES"


def _write_outputs(
    output_dir: Path,
    wide: pd.DataFrame,
    detail: pd.DataFrame,
    status: pd.DataFrame,
    quality: dict[str, Any],
    *,
    history_manifest: dict[str, Any],
    history_manifest_path: Path,
    factor_registry: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    wide_path = output_dir / "BASIC_FACTOR_TABLE.parquet"
    detail_path = output_dir / "BASIC_FACTOR_DETAIL.parquet"
    status_path = output_dir / "BASIC_FACTOR_STATUS.csv"
    quality_path = output_dir / "BASIC_FACTOR_QUALITY.json"
    report_path = output_dir / "FMDL2B4_FACTOR_REFRESH_REPORT.json"

    wide.to_parquet(wide_path, index=False, compression="zstd")
    detail.to_parquet(detail_path, index=False, compression="zstd")
    status.to_csv(status_path, index=False, encoding="utf-8-sig")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run_id = datetime.now(tz=BUSINESS_TZ).strftime("FMDL2B4_FACTOR_%Y%m%dT%H%M%S%z")
    report = {
        "report_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "as_of_date": history_manifest["as_of_date"],
        "history_release_id": history_manifest["release_id"],
        "factor_contract_version": factor_registry["contract_version"],
        "status": quality["status"],
        "metrics": quality["metrics"],
        "hard_failures": quality["hard_failures"],
        "controlled_warnings": quality["controlled_warnings"],
        "non_claims": [
            "NO_FACTOR_ALPHA_CLAIM",
            "NO_SCREENING_SLEEVE_AUTHORITY",
            "NO_CANDIDATE_POOL_CHANGE",
            "NO_SIMULATION_OR_REAL_PORTFOLIO_CHANGE",
            "NO_TRADE_AUTHORITY",
        ],
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    artifacts: list[dict[str, Any]] = []
    for dataset_id, path, rows in (
        ("basic_factor_table", wide_path, len(wide)),
        ("basic_factor_detail", detail_path, len(detail)),
        ("basic_factor_status", status_path, len(status)),
        ("basic_factor_quality", quality_path, 1),
        ("fmdl2b4_factor_refresh_report", report_path, 1),
    ):
        artifacts.append({
            "dataset_id": dataset_id,
            "path": relative_path(path),
            "sha256": sha256_file(path),
            "row_count": int(rows),
            "bytes": path.stat().st_size,
        })
    manifest = {
        "manifest_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "as_of_date": history_manifest["as_of_date"],
        "history_release_id": history_manifest["release_id"],
        "history_manifest_path": relative_path(history_manifest_path),
        "history_manifest_sha256": sha256_file(history_manifest_path),
        "factor_contract_version": factor_registry["contract_version"],
        "factor_registry_sha256": sha256_file(FACTOR_REGISTRY_PATH),
        "factor_count": len(EXPECTED_FACTOR_IDS),
        "universe_symbols": int(len(wide)),
        "artifacts": artifacts,
        "aggregate_sha256": canonical_hash(artifacts),
        "status": "CANDIDATE_GENERATED" if not quality["hard_failures"] else "CANDIDATE_REJECTED",
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }
    (output_dir / "BASIC_FACTOR_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run(root: Path = ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    history_manifest_path = root / HISTORY_CANDIDATE.relative_to(ROOT)
    history_quality_path = root / HISTORY_QUALITY.relative_to(ROOT)
    history_status_path = root / HISTORY_STATUS.relative_to(ROOT)
    history_manifest = read_json(history_manifest_path)
    history_quality = read_json(history_quality_path)
    current_release = read_json(root / CURRENT_RELEASE_PATH.relative_to(ROOT))
    factor_registry = read_json(root / FACTOR_REGISTRY_PATH.relative_to(ROOT))
    engine_config = read_json(root / FACTOR_ENGINE_CONFIG_PATH.relative_to(ROOT))
    universe = pd.read_csv(root / UNIVERSE_PATH.relative_to(ROOT), dtype={"symbol": str})
    history_status = pd.read_csv(history_status_path, dtype={"symbol": str})

    errors: list[str] = []
    if history_manifest.get("status") != "CANDIDATE_PASS":
        errors.append("HISTORY_CANDIDATE_NOT_PASS")
    if history_quality.get("hard_failures"):
        errors.append("HISTORY_CANDIDATE_HAS_HARD_FAILURES")
    if str(history_manifest.get("as_of_date")) != str(current_release.get("as_of_date")):
        errors.append("HISTORY_CURRENT_AS_OF_MISMATCH")
    if set(history_status["symbol"].astype(str)) != set(universe["symbol"].astype(str)):
        errors.append("HISTORY_STATUS_UNIVERSE_MISMATCH")
    if history_status["symbol"].duplicated().any():
        errors.append("DUPLICATE_HISTORY_STATUS_SYMBOL")
    if {item["factor_id"] for item in factor_registry["factors"]} != EXPECTED_FACTOR_IDS:
        errors.append("FACTOR_REGISTRY_IMPLEMENTATION_MISMATCH")
    if errors:
        raise RuntimeError(";".join(errors))

    as_of_date = str(history_manifest["as_of_date"])
    market_calendar = _market_calendar(history_manifest, root)
    if market_calendar[-1] != pd.Timestamp(as_of_date):
        raise RuntimeError("COMPOSITE_CALENDAR_NOT_CURRENT")
    universe_map = universe.set_index("symbol").to_dict(orient="index")
    history_status_map = history_status.set_index("symbol").to_dict(orient="index")
    status_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    processed: set[str] = set()

    for _, shard in iter_composite_shards(history_manifest, root=root):
        for symbol, group in shard.groupby("symbol", sort=True):
            symbol = str(symbol)
            if symbol not in universe_map:
                continue
            if symbol in processed:
                raise RuntimeError(f"SYMBOL_PRESENT_IN_MULTIPLE_COMPOSITE_SHARDS_{symbol}")
            processed.add(symbol)
            normalized, lineage_state = _normalize_composite_lineage(group)
            hstatus = history_status_map[symbol]
            provider_id = str(hstatus.get("provider_id", "NONE"))
            factor_state = _history_state_for_factor(str(hstatus.get("refresh_state")), provider_id)
            event_count = 1 if str(hstatus.get("refresh_state")) in {"READY_SUSPENDED_NO_APPEND", "REPAIR_REQUIRED"} else 0
            base, details = compute_symbol_factor_values(
                normalized,
                {"symbol": symbol, **universe_map[symbol]},
                {"symbol": symbol, "state": factor_state, "provider_id": provider_id},
                factor_registry,
                engine_config,
                market_calendar,
                as_of_date,
                event_count,
            )
            base["history_refresh_state"] = hstatus.get("refresh_state")
            base["history_lineage_state"] = lineage_state
            if lineage_state == "UNVALIDATED_COMPOSITE_LINEAGE":
                base["factor_record_quality"] = "SUSPECT"
                base["confidence_grade"] = "D"
            for row in details:
                row["history_refresh_state"] = hstatus.get("refresh_state")
                row["history_lineage_state"] = lineage_state
                if lineage_state == "UNVALIDATED_COMPOSITE_LINEAGE":
                    row["factor_record_quality"] = "SUSPECT"
                    row["confidence_grade"] = "D"
            status_rows.append(base)
            detail_rows.extend(details)

    for symbol in sorted(set(universe_map).difference(processed)):
        hstatus = history_status_map[symbol]
        provider_id = str(hstatus.get("provider_id", "NONE"))
        base, details = compute_symbol_factor_values(
            None,
            {"symbol": symbol, **universe_map[symbol]},
            {"symbol": symbol, "state": "QUARANTINED", "provider_id": provider_id},
            factor_registry,
            engine_config,
            market_calendar,
            as_of_date,
            1,
        )
        base["history_refresh_state"] = hstatus.get("refresh_state")
        base["history_lineage_state"] = "NO_COMPOSITE_HISTORY"
        for row in details:
            row["history_refresh_state"] = hstatus.get("refresh_state")
            row["history_lineage_state"] = "NO_COMPOSITE_HISTORY"
        status_rows.append(base)
        detail_rows.extend(details)

    status_frame = pd.DataFrame(status_rows).sort_values(["board", "symbol"]).reset_index(drop=True)
    detail_frame = pd.DataFrame(detail_rows).sort_values(["factor_id", "board", "symbol"]).reset_index(drop=True)
    detail_frame = add_cross_sectional_fields(detail_frame, engine_config)
    detail_frame["history_release_id"] = history_manifest["release_id"]
    detail_frame["factor_contract_version"] = factor_registry["contract_version"]
    detail_frame = add_row_hashes(detail_frame)
    wide_frame = build_wide_table(status_frame, detail_frame)
    quality = quality_payload(
        wide_frame,
        detail_frame,
        len(universe),
        as_of_date,
        history_manifest["release_id"],
        factor_registry["contract_version"],
    )
    lineage_suspect = int((status_frame["history_lineage_state"] == "UNVALIDATED_COMPOSITE_LINEAGE").sum())
    if lineage_suspect:
        quality["hard_failures"].append(f"UNVALIDATED_COMPOSITE_LINEAGE_{lineage_suspect}")
        quality["status"] = "FAIL"
    quality["history_refresh_run_id"] = history_manifest["release_id"]
    quality["history_refresh_quality"] = history_quality["status"]
    quality["authority"] = "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY"

    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    manifest = _write_outputs(
        output_dir,
        wide_frame,
        detail_frame,
        status_frame,
        quality,
        history_manifest=history_manifest,
        history_manifest_path=history_manifest_path,
        factor_registry=factor_registry,
        generated_at=generated_at,
    )
    if quality["hard_failures"]:
        raise RuntimeError(";".join(quality["hard_failures"]))
    result = {"manifest": manifest, "quality": quality}
    print(json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    try:
        run(ROOT, Path(args.output_dir))
    except Exception as exc:
        print(f"FMDL-2B-4 factor refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
