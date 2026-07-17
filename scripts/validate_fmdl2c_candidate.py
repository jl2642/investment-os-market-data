#!/usr/bin/env python3
"""Independently validate an FMDL-2C screening candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/screens/candidate"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path = ROOT) -> dict[str, Any]:
    base = root / CANDIDATE.relative_to(ROOT)
    config = read_json(root / "config/fmdl2_screening_funnel.json")
    manifest = read_json(base / "SCREENING_MANIFEST.json")
    quality = read_json(base / "SCREENING_QUALITY.json")
    failures: list[str] = []
    if manifest.get("status") != "CANDIDATE_GENERATED":
        failures.append("MANIFEST_NOT_GENERATED")
    if quality.get("hard_failures"):
        failures.append("QUALITY_HAS_HARD_FAILURES")
    artifact_map = {item["dataset_id"]: item for item in manifest.get("artifacts", [])}
    required = {
        "screening_universe",
        "screening_sleeve_detail",
        "screening_longlist",
        "screening_funnel",
        "screening_quality",
        "run_report",
    }
    if set(artifact_map) != required:
        failures.append("ARTIFACT_SET_MISMATCH")
    for dataset_id, item in artifact_map.items():
        path = root / item["path"]
        if not path.exists():
            failures.append(f"MISSING_{dataset_id}")
            continue
        if sha256_file(path) != item.get("sha256"):
            failures.append(f"HASH_MISMATCH_{dataset_id}")
    screen = pd.read_parquet(base / "SCREENING_UNIVERSE.parquet")
    detail = pd.read_parquet(base / "SCREENING_SLEEVE_DETAIL.parquet")
    longlist = pd.read_csv(base / "SCREENING_LONGLIST.csv", dtype={"symbol": str})
    funnel = pd.read_csv(base / "SCREENING_FUNNEL.csv")
    if screen["symbol"].astype(str).duplicated().any():
        failures.append("DUPLICATE_SCREEN_SYMBOL")
    if "name" not in screen.columns or screen["name"].isna().any():
        failures.append("SCREEN_SECURITY_NAME_MISSING")
    elif screen["name"].astype(str).str.strip().eq("").any():
        failures.append("SCREEN_SECURITY_NAME_EMPTY")
    if not detail.empty and detail.duplicated(["symbol", "sleeve_id"]).any():
        failures.append("DUPLICATE_SYMBOL_SLEEVE")
    if not detail.empty and (
        "name" not in detail.columns
        or detail["name"].isna().any()
        or detail["name"].astype(str).str.strip().eq("").any()
    ):
        failures.append("DETAIL_SECURITY_NAME_MISSING")
    if not longlist.empty and longlist["symbol"].astype(str).duplicated().any():
        failures.append("DUPLICATE_LONGLIST_SYMBOL")
    if len(longlist) > int(config["funnel"]["longlist_maximum"]):
        failures.append("LONGLIST_LIMIT")
    if not longlist.empty:
        if (
            "name" not in longlist.columns
            or longlist["name"].isna().any()
            or longlist["name"].astype(str).str.strip().eq("").any()
        ):
            failures.append("LONGLIST_SECURITY_NAME_MISSING")
        bad_quality = longlist["factor_record_quality"].isin(["SUSPECT", "BLOCKED"])
        if bad_quality.any():
            failures.append("BAD_QUALITY_IN_LONGLIST")
        if (longlist["investability_status"] == "EXCLUDED").any():
            failures.append("EXCLUDED_IN_LONGLIST")
        if longlist["aggregate_score"].isna().any():
            failures.append("MISSING_SCORE")
        ranks = longlist["overall_rank"].astype(int).tolist()
        if ranks != list(range(1, len(longlist) + 1)):
            failures.append("NON_CONTIGUOUS_RANKS")
        expected_method = config["funnel"]["cross_sleeve_comparison"]["method"]
        if set(longlist["score_basis"].astype(str)) != {expected_method}:
            failures.append("CROSS_SLEEVE_SCORE_BASIS_MISMATCH")
    expected_stages = [
        "01_UNIVERSE",
        "02_DATA_READY",
        "03_CORE_INVESTABLE",
        "04_WATCH_ELIGIBLE",
        "05_RAW_SLEEVE_HITS",
        "06_DISTINCT_SLEEVE_CANDIDATES",
        "07_RESEARCH_LONGLIST",
    ]
    if funnel["stage"].astype(str).tolist() != expected_stages:
        failures.append("FUNNEL_STAGE_MISMATCH")
    sleeve_counts = detail.groupby("sleeve_id").size().to_dict() if not detail.empty else {}
    primary_counts = (
        longlist["primary_sleeve"].value_counts().to_dict()
        if not longlist.empty
        else {}
    )
    for sleeve_id, sleeve in config["sleeves"].items():
        if int(sleeve_counts.get(sleeve_id, 0)) > int(sleeve["maximum_candidates"]):
            failures.append(f"SLEEVE_LIMIT_{sleeve_id}")
        if int(sleeve_counts.get(sleeve_id, 0)) > 0 and int(primary_counts.get(sleeve_id, 0)) == 0:
            failures.append(f"NO_PRIMARY_REPRESENTATION_{sleeve_id}")
    payload = {
        "validation_version": "1.0.0",
        "status": "PASS" if not failures else "FAIL",
        "as_of_date": manifest.get("as_of_date"),
        "hard_failures": failures,
        "metrics": {
            "screen_rows": len(screen),
            "named_screen_rows": int(screen["name"].notna().sum()) if "name" in screen else 0,
            "detail_rows": len(detail),
            "longlist_rows": len(longlist),
            "named_longlist_rows": int(longlist["name"].notna().sum()) if "name" in longlist else 0,
            "sleeve_counts": {str(key): int(value) for key, value in sleeve_counts.items()},
            "primary_sleeve_counts": {str(key): int(value) for key, value in primary_counts.items()},
        },
        "authority": "RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY",
    }
    (base / "SCREENING_VALIDATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        raise RuntimeError(";".join(failures))
    print(json.dumps(payload, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    validate()
