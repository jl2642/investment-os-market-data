"""Last-known-good publication and quarantine controls for FMDL-1D."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

from pipeline.common import file_sha256, write_json
from pipeline.event_flags import build_market_event_flags


CANDIDATE_FILES = [
    "A_SHARE_UNIVERSE.csv",
    "DAILY_MARKET_SNAPSHOT.csv",
    "A_SHARE_UNIVERSE_MANIFEST.json",
    "DAILY_MARKET_SNAPSHOT_MANIFEST.json",
    "A_SHARE_UNIVERSE_QUALITY.json",
    "DAILY_MARKET_SNAPSHOT_QUALITY.json",
    "FMDL_1BC_RUN_REPORT.json",
    "FMDL_1BC_RUN_REPORT.md",
]


@dataclass
class PublicationResult:
    action: str
    run_id: str
    as_of_date: str
    current_preserved: bool
    hard_failures: list[str]
    soft_warnings: list[str]
    release_path: str | None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _verify_candidate(candidate_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    missing = [name for name in CANDIDATE_FILES if not (candidate_dir / name).exists()]
    if missing:
        raise RuntimeError(f"Candidate package incomplete: {missing}")

    report = _load_json(candidate_dir / "FMDL_1BC_RUN_REPORT.json")
    universe_manifest = _load_json(candidate_dir / "A_SHARE_UNIVERSE_MANIFEST.json")
    snapshot_manifest = _load_json(candidate_dir / "DAILY_MARKET_SNAPSHOT_MANIFEST.json")
    manifests = [universe_manifest, snapshot_manifest]

    run_ids = {report["run_id"], *(manifest["run_id"] for manifest in manifests)}
    as_of_dates = {report["as_of_date"], *(manifest["as_of_date"] for manifest in manifests)}
    if len(run_ids) != 1 or len(as_of_dates) != 1:
        raise RuntimeError("Candidate run_id/as_of_date is inconsistent across manifests")

    expected = {
        "a_share_universe": candidate_dir / "A_SHARE_UNIVERSE.csv",
        "daily_market_snapshot": candidate_dir / "DAILY_MARKET_SNAPSHOT.csv",
    }
    for manifest in manifests:
        dataset_id = manifest["dataset_id"]
        path = expected[dataset_id]
        if manifest["file"]["sha256"] != file_sha256(path):
            raise RuntimeError(f"Candidate hash mismatch for {dataset_id}")
        if manifest["row_count"] <= 0:
            raise RuntimeError(f"Candidate row_count is zero for {dataset_id}")

    return report, universe_manifest, snapshot_manifest


def _load_previous_release(current_dir: Path) -> dict[str, Any] | None:
    path = current_dir / "CURRENT_RELEASE.json"
    return _load_json(path) if path.exists() else None


def _published_manifest(
    manifest: dict[str, Any],
    *,
    current_path: str,
    quality_path: str,
    previous_version: str | None,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(manifest))
    updated["publication_status"] = "PUBLISHED"
    updated["file"]["path"] = current_path
    updated["quality"]["gate_results_path"] = quality_path
    updated["lineage"] = {
        "parent_dataset_version": previous_version,
        "last_known_good_dataset_version": previous_version,
    }
    updated["notes"] = "Published by FMDL-1D last-known-good controls."
    return updated


def _archive_release_metadata(
    *,
    root: Path,
    candidate_dir: Path,
    report: dict[str, Any],
    event_flags_path: Path,
) -> Path:
    archive_dir = root / "outputs/archive" / report["as_of_date"] / report["run_id"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    for name in CANDIDATE_FILES:
        if name.endswith(".csv"):
            continue
        _copy_file(candidate_dir / name, archive_dir / name)
    _copy_file(event_flags_path, archive_dir / "MARKET_EVENT_FLAGS.csv")
    return archive_dir


def quarantine_candidate(
    *,
    root: Path,
    run_id: str,
    as_of_date: str,
    reason: str,
    hard_failures: list[str] | None = None,
) -> PublicationResult:
    candidate_dir = root / "outputs/candidate"
    quarantine_dir = root / "outputs/quarantine" / run_id
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    for name in CANDIDATE_FILES:
        source = candidate_dir / name
        if source.exists():
            _copy_file(source, quarantine_dir / name)
    payload = {
        "run_id": run_id,
        "as_of_date": as_of_date,
        "status": "QUARANTINED",
        "reason": reason,
        "hard_failures": hard_failures or [],
        "current_preserved": True,
    }
    write_json(quarantine_dir / "FAILURE_REPORT.json", payload)
    return PublicationResult(
        action="QUARANTINED",
        run_id=run_id,
        as_of_date=as_of_date,
        current_preserved=True,
        hard_failures=hard_failures or [],
        soft_warnings=[],
        release_path=str(quarantine_dir.relative_to(root)),
    )


def publish_candidate(*, root: Path, generated_at: str) -> PublicationResult:
    candidate_dir = root / "outputs/candidate"
    current_dir = root / "outputs/current"
    status_dir = root / "outputs/status"
    report, universe_manifest, snapshot_manifest = _verify_candidate(candidate_dir)

    hard_failures = list(report["universe"]["hard_failures"]) + list(report["snapshot"]["hard_failures"])
    soft_warnings = list(report["universe"]["soft_warnings"]) + list(report["snapshot"]["soft_warnings"])
    if hard_failures:
        return quarantine_candidate(
            root=root,
            run_id=report["run_id"],
            as_of_date=report["as_of_date"],
            reason="HARD_QUALITY_GATE_FAILURE",
            hard_failures=hard_failures,
        )

    previous = _load_previous_release(current_dir)
    previous_versions = {}
    if previous:
        previous_versions = previous.get("dataset_versions", {})

    snapshot = pd.read_csv(candidate_dir / "DAILY_MARKET_SNAPSHOT.csv")
    event_flags = build_market_event_flags(snapshot)
    candidate_event_path = candidate_dir / "MARKET_EVENT_FLAGS.csv"
    event_flags.to_csv(candidate_event_path, index=False, encoding="utf-8-sig", lineterminator="\n")

    archive_dir = _archive_release_metadata(
        root=root,
        candidate_dir=candidate_dir,
        report=report,
        event_flags_path=candidate_event_path,
    )

    stage_dir = root / "outputs/.current_stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    for name in [
        "A_SHARE_UNIVERSE.csv",
        "DAILY_MARKET_SNAPSHOT.csv",
        "A_SHARE_UNIVERSE_QUALITY.json",
        "DAILY_MARKET_SNAPSHOT_QUALITY.json",
        "FMDL_1BC_RUN_REPORT.json",
        "FMDL_1BC_RUN_REPORT.md",
        "MARKET_EVENT_FLAGS.csv",
    ]:
        _copy_file(candidate_dir / name, stage_dir / name)

    published_universe = _published_manifest(
        universe_manifest,
        current_path="outputs/current/A_SHARE_UNIVERSE.csv",
        quality_path="outputs/current/A_SHARE_UNIVERSE_QUALITY.json",
        previous_version=previous_versions.get("a_share_universe"),
    )
    published_snapshot = _published_manifest(
        snapshot_manifest,
        current_path="outputs/current/DAILY_MARKET_SNAPSHOT.csv",
        quality_path="outputs/current/DAILY_MARKET_SNAPSHOT_QUALITY.json",
        previous_version=previous_versions.get("daily_market_snapshot"),
    )
    write_json(stage_dir / "A_SHARE_UNIVERSE_MANIFEST.json", published_universe)
    write_json(stage_dir / "DAILY_MARKET_SNAPSHOT_MANIFEST.json", published_snapshot)

    release = {
        "release_version": "1.0.0",
        "run_id": report["run_id"],
        "as_of_date": report["as_of_date"],
        "published_at": generated_at,
        "status": "PUBLISHED_WITH_WARNINGS" if soft_warnings else "PUBLISHED",
        "qa_status": "PASS_WITH_WARNINGS" if soft_warnings else "PASS",
        "hard_failures": [],
        "soft_warnings": sorted(set(soft_warnings)),
        "market_wide_provider": report["market_wide_provider"],
        "market_wide_source_function": report["market_wide_source_function"],
        "dataset_versions": {
            "a_share_universe": published_universe["dataset_version"],
            "daily_market_snapshot": published_snapshot["dataset_version"],
        },
        "current_files": {
            "a_share_universe": {
                "path": "outputs/current/A_SHARE_UNIVERSE.csv",
                "sha256": file_sha256(stage_dir / "A_SHARE_UNIVERSE.csv"),
            },
            "daily_market_snapshot": {
                "path": "outputs/current/DAILY_MARKET_SNAPSHOT.csv",
                "sha256": file_sha256(stage_dir / "DAILY_MARKET_SNAPSHOT.csv"),
            },
            "market_event_flags": {
                "path": "outputs/current/MARKET_EVENT_FLAGS.csv",
                "sha256": file_sha256(stage_dir / "MARKET_EVENT_FLAGS.csv"),
                "row_count": len(event_flags),
            },
        },
        "archive_metadata_path": str(archive_dir.relative_to(root)).replace("\\", "/"),
        "previous_release_run_id": None if previous is None else previous.get("run_id"),
        "authority_boundary": "DATA_EVIDENCE_ONLY_NO_INVESTMENT_DECISION",
    }
    write_json(stage_dir / "CURRENT_RELEASE.json", release)

    current_dir.mkdir(parents=True, exist_ok=True)
    for existing in current_dir.iterdir():
        if existing.is_file():
            existing.unlink()
    for source in stage_dir.iterdir():
        _copy_file(source, current_dir / source.name)
    shutil.rmtree(stage_dir)

    status_payload = {
        "run_id": report["run_id"],
        "as_of_date": report["as_of_date"],
        "generated_at": generated_at,
        "status": release["status"],
        "action": "PROMOTED_CURRENT",
        "current_preserved": False,
        "hard_failures": [],
        "soft_warnings": release["soft_warnings"],
        "current_release_path": "outputs/current/CURRENT_RELEASE.json",
    }
    write_json(status_dir / "LAST_RUN.json", status_payload)
    write_json(status_dir / "LAST_SUCCESS.json", status_payload)

    return PublicationResult(
        action="PROMOTED_CURRENT",
        run_id=report["run_id"],
        as_of_date=report["as_of_date"],
        current_preserved=False,
        hard_failures=[],
        soft_warnings=release["soft_warnings"],
        release_path="outputs/current/CURRENT_RELEASE.json",
    )


def write_failure_status(
    *,
    root: Path,
    run_id: str,
    as_of_date: str,
    generated_at: str,
    reason: str,
    error: str,
) -> None:
    payload = {
        "run_id": run_id,
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "status": "FAILED",
        "action": "RETAIN_LAST_KNOWN_GOOD",
        "reason": reason,
        "error": error,
        "current_preserved": True,
    }
    write_json(root / "outputs/status/LAST_RUN.json", payload)
    quarantine_dir = root / "outputs/quarantine" / run_id
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    write_json(quarantine_dir / "FAILURE_REPORT.json", payload)
