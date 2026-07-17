#!/usr/bin/env python3
"""Atomically publish accepted FMDL-2B-4 history and factor Current releases."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zoneinfo import ZoneInfo

from scripts.fmdl2b4_history import ROOT, canonical_hash, read_json, relative_path, sha256_file

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
HISTORY_CANDIDATE = ROOT / "outputs/history/refresh_candidate"
FACTOR_CANDIDATE = ROOT / "outputs/factors/refresh_candidate"
HISTORY_CURRENT = ROOT / "outputs/history/current"
FACTOR_CURRENT = ROOT / "outputs/factors/current"
HISTORY_ARCHIVE = ROOT / "outputs/history/archive"
FACTOR_ARCHIVE = ROOT / "outputs/factors/archive"


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _rewrite_history_manifest(temp_dir: Path) -> dict[str, Any]:
    path = temp_dir / "HISTORY_CURRENT_MANIFEST.json"
    manifest = read_json(path)
    status_path = temp_dir / "HISTORY_CURRENT_STATUS.csv"
    quality_path = temp_dir / "HISTORY_REFRESH_QUALITY.json"
    continuity_path = temp_dir / "HISTORY_CONTINUITY_DIAGNOSTICS.csv"
    manifest.update({
        "status_path": relative_path(HISTORY_CURRENT / status_path.name),
        "status_sha256": sha256_file(status_path),
        "quality_path": relative_path(HISTORY_CURRENT / quality_path.name),
        "quality_sha256": sha256_file(quality_path),
        "continuity_diagnostics_path": relative_path(HISTORY_CURRENT / continuity_path.name),
        "continuity_diagnostics_sha256": sha256_file(continuity_path),
        "status": "PUBLISHED_CURRENT",
    })
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _rewrite_factor_manifest(temp_dir: Path, history_manifest: dict[str, Any], history_manifest_path: Path) -> dict[str, Any]:
    path = temp_dir / "BASIC_FACTOR_MANIFEST.json"
    manifest = read_json(path)
    artifacts: list[dict[str, Any]] = []
    mapping = {
        "basic_factor_table": temp_dir / "BASIC_FACTOR_TABLE.parquet",
        "basic_factor_detail": temp_dir / "BASIC_FACTOR_DETAIL.parquet",
        "basic_factor_status": temp_dir / "BASIC_FACTOR_STATUS.csv",
        "basic_factor_quality": temp_dir / "BASIC_FACTOR_QUALITY.json",
        "fmdl2b4_factor_refresh_report": temp_dir / "FMDL2B4_FACTOR_REFRESH_REPORT.json",
    }
    for item in manifest.get("artifacts", []):
        dataset_id = str(item["dataset_id"])
        local = mapping[dataset_id]
        artifacts.append({
            **item,
            "path": relative_path(FACTOR_CURRENT / local.name),
            "sha256": sha256_file(local),
            "bytes": local.stat().st_size,
        })
    manifest.update({
        "history_release_id": history_manifest["release_id"],
        "history_manifest_path": relative_path(HISTORY_CURRENT / history_manifest_path.name),
        "history_manifest_sha256": sha256_file(history_manifest_path),
        "artifacts": artifacts,
        "aggregate_sha256": canonical_hash(artifacts),
        "status": "PUBLISHED_CURRENT",
    })
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_release_files(history_temp: Path, factor_temp: Path, history_manifest: dict[str, Any], factor_manifest: dict[str, Any]) -> None:
    generated_at = datetime.now(tz=BUSINESS_TZ).isoformat(timespec="seconds")
    prior_history = read_json(HISTORY_CURRENT / "HISTORY_CURRENT_RELEASE.json") if (HISTORY_CURRENT / "HISTORY_CURRENT_RELEASE.json").exists() else None
    prior_factor = read_json(FACTOR_CURRENT / "FACTOR_CURRENT_RELEASE.json") if (FACTOR_CURRENT / "FACTOR_CURRENT_RELEASE.json").exists() else None
    history_release = {
        "release_version": "1.0.0",
        "release_id": history_manifest["release_id"],
        "as_of_date": history_manifest["as_of_date"],
        "published_at": generated_at,
        "status": "PUBLISHED_WITH_WARNINGS" if read_json(history_temp / "HISTORY_REFRESH_QUALITY.json").get("controlled_warnings") else "PUBLISHED",
        "manifest_path": relative_path(HISTORY_CURRENT / "HISTORY_CURRENT_MANIFEST.json"),
        "manifest_sha256": sha256_file(history_temp / "HISTORY_CURRENT_MANIFEST.json"),
        "status_path": relative_path(HISTORY_CURRENT / "HISTORY_CURRENT_STATUS.csv"),
        "quality_path": relative_path(HISTORY_CURRENT / "HISTORY_REFRESH_QUALITY.json"),
        "previous_release_id": prior_history.get("release_id") if prior_history else None,
        "trade_authority": "NONE",
    }
    factor_release = {
        "release_version": "1.0.0",
        "release_id": factor_manifest["run_id"],
        "as_of_date": factor_manifest["as_of_date"],
        "published_at": generated_at,
        "status": "PUBLISHED_WITH_WARNINGS" if read_json(factor_temp / "BASIC_FACTOR_QUALITY.json").get("controlled_warnings") else "PUBLISHED",
        "history_release_id": history_manifest["release_id"],
        "manifest_path": relative_path(FACTOR_CURRENT / "BASIC_FACTOR_MANIFEST.json"),
        "manifest_sha256": sha256_file(factor_temp / "BASIC_FACTOR_MANIFEST.json"),
        "previous_release_id": prior_factor.get("release_id") if prior_factor else None,
        "trade_authority": "NONE",
    }
    (history_temp / "HISTORY_CURRENT_RELEASE.json").write_text(
        json.dumps(history_release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (factor_temp / "FACTOR_CURRENT_RELEASE.json").write_text(
        json.dumps(factor_release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def publish(root: Path = ROOT) -> dict[str, Any]:
    history_quality = read_json(root / HISTORY_CANDIDATE.relative_to(ROOT) / "HISTORY_REFRESH_QUALITY.json")
    factor_quality = read_json(root / FACTOR_CANDIDATE.relative_to(ROOT) / "BASIC_FACTOR_QUALITY.json")
    history_manifest = read_json(root / HISTORY_CANDIDATE.relative_to(ROOT) / "HISTORY_CURRENT_MANIFEST.json")
    factor_manifest = read_json(root / FACTOR_CANDIDATE.relative_to(ROOT) / "BASIC_FACTOR_MANIFEST.json")
    validation_path = root / "diagnostics/FMDL2B4_CANDIDATE_VALIDATION.json"
    validation = read_json(validation_path)

    blockers: list[str] = []
    if history_quality.get("hard_failures"):
        blockers.append("HISTORY_HARD_FAILURES")
    if factor_quality.get("hard_failures"):
        blockers.append("FACTOR_HARD_FAILURES")
    if history_manifest.get("status") != "CANDIDATE_PASS":
        blockers.append("HISTORY_CANDIDATE_NOT_PASS")
    if factor_manifest.get("status") != "CANDIDATE_GENERATED":
        blockers.append("FACTOR_CANDIDATE_NOT_GENERATED")
    if validation.get("status") != "PASS":
        blockers.append("INDEPENDENT_VALIDATION_NOT_PASS")
    if history_manifest.get("as_of_date") != factor_manifest.get("as_of_date"):
        blockers.append("HISTORY_FACTOR_AS_OF_MISMATCH")
    if blockers:
        raise RuntimeError(";".join(blockers))

    history_temp = root / "outputs/history/.current_publish_tmp"
    factor_temp = root / "outputs/factors/.current_publish_tmp"
    history_backup = root / "outputs/history/.current_backup"
    factor_backup = root / "outputs/factors/.current_backup"
    for path in (history_temp, factor_temp, history_backup, factor_backup):
        if path.exists():
            shutil.rmtree(path)
    _copy_tree(root / HISTORY_CANDIDATE.relative_to(ROOT), history_temp)
    _copy_tree(root / FACTOR_CANDIDATE.relative_to(ROOT), factor_temp)

    history_manifest = _rewrite_history_manifest(history_temp)
    factor_manifest = _rewrite_factor_manifest(
        factor_temp,
        history_manifest,
        history_temp / "HISTORY_CURRENT_MANIFEST.json",
    )
    _write_release_files(history_temp, factor_temp, history_manifest, factor_manifest)

    try:
        history_current = root / HISTORY_CURRENT.relative_to(ROOT)
        factor_current = root / FACTOR_CURRENT.relative_to(ROOT)
        if history_current.exists():
            history_current.rename(history_backup)
        if factor_current.exists():
            factor_current.rename(factor_backup)
        history_temp.rename(history_current)
        factor_temp.rename(factor_current)
    except Exception:
        if (root / HISTORY_CURRENT.relative_to(ROOT)).exists():
            shutil.rmtree(root / HISTORY_CURRENT.relative_to(ROOT))
        if (root / FACTOR_CURRENT.relative_to(ROOT)).exists():
            shutil.rmtree(root / FACTOR_CURRENT.relative_to(ROOT))
        if history_backup.exists():
            history_backup.rename(root / HISTORY_CURRENT.relative_to(ROOT))
        if factor_backup.exists():
            factor_backup.rename(root / FACTOR_CURRENT.relative_to(ROOT))
        raise
    finally:
        for path in (history_backup, factor_backup, history_temp, factor_temp):
            if path.exists():
                shutil.rmtree(path)

    history_archive = root / HISTORY_ARCHIVE.relative_to(ROOT) / str(history_manifest["release_id"])
    factor_archive = root / FACTOR_ARCHIVE.relative_to(ROOT) / str(factor_manifest["run_id"])
    history_archive.mkdir(parents=True, exist_ok=True)
    factor_archive.mkdir(parents=True, exist_ok=True)
    for name in ("HISTORY_CURRENT_RELEASE.json", "HISTORY_CURRENT_MANIFEST.json", "HISTORY_REFRESH_QUALITY.json", "FMDL2B4_HISTORY_REFRESH_REPORT.json"):
        shutil.copy2(root / HISTORY_CURRENT.relative_to(ROOT) / name, history_archive / name)
    for name in ("FACTOR_CURRENT_RELEASE.json", "BASIC_FACTOR_MANIFEST.json", "BASIC_FACTOR_QUALITY.json", "FMDL2B4_FACTOR_REFRESH_REPORT.json"):
        shutil.copy2(root / FACTOR_CURRENT.relative_to(ROOT) / name, factor_archive / name)

    result = {
        "status": "PUBLISHED",
        "history_release_id": history_manifest["release_id"],
        "factor_release_id": factor_manifest["run_id"],
        "as_of_date": history_manifest["as_of_date"],
        "history_current": relative_path(root / HISTORY_CURRENT.relative_to(ROOT)),
        "factor_current": relative_path(root / FACTOR_CURRENT.relative_to(ROOT)),
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    try:
        publish(ROOT)
    except Exception as exc:
        print(f"FMDL-2B-4 publication failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
