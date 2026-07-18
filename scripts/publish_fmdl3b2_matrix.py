from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl3b2_matrix_core as matrix

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_matrix.json"
CANDIDATE = ROOT / "outputs/financials/full_build/matrix/candidate"


def copy_top_level_files(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if path.is_file():
            shutil.copy2(path, destination / path.name)


def main() -> int:
    cfg = matrix.load_json(CONFIG)
    decision = matrix.load_json(CANDIDATE / "FMDL3B2_MATRIX_DECISION.json")
    validation = matrix.load_json(CANDIDATE / "FMDL3B2_MATRIX_VALIDATION.json")
    accepted_status = "FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE"
    if decision.get("status") != accepted_status or validation.get("status") != "PASS":
        raise SystemExit("matrix publication blocked")

    release_id = decision["release_id"]
    release_root = ROOT / cfg["storage"]["release_root"] / release_id
    current_root = ROOT / cfg["storage"]["current_root"]
    archive_root = ROOT / cfg["storage"]["archive_root"] / release_id
    last_success = ROOT / cfg["storage"]["last_success_path"]

    if release_root.exists():
        raise SystemExit(f"immutable release exists: {release_root}")
    if archive_root.exists():
        raise SystemExit(f"immutable archive exists: {archive_root}")

    shutil.copytree(CANDIDATE, release_root)
    if current_root.exists():
        shutil.rmtree(current_root)
    copy_top_level_files(CANDIDATE, current_root)

    published_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    normalized_paths = [str(path.relative_to(ROOT)) for path in sorted((release_root / "normalized").glob("shard-*.parquet"))]
    revision_paths = [str(path.relative_to(ROOT)) for path in sorted((release_root / "revisions").glob("shard-*.parquet"))]
    source_paths = [str(path.relative_to(ROOT)) for path in sorted((release_root / "sources").glob("shard-*.parquet"))]
    candidate_manifest = CANDIDATE / "FMDL3B2_MATRIX_MANIFEST.json"

    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3B-2-MATRIX",
        "status": decision["status"],
        "exit_gate": "FULL_UNIVERSE_INITIAL_STATEMENT_BASE_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "decision_path": f"{cfg['storage']['current_root']}/FMDL3B2_MATRIX_DECISION.json",
        "validation_path": f"{cfg['storage']['current_root']}/FMDL3B2_MATRIX_VALIDATION.json",
        "membership_path": f"{cfg['storage']['current_root']}/FMDL3B2_MEMBERSHIP.csv",
        "shard_summary_path": f"{cfg['storage']['current_root']}/FMDL3B2_SHARD_SUMMARY.csv",
        "support_map_path": f"{cfg['storage']['current_root']}/FMDL3B2_SUPPORT_MAP.csv",
        "retry_ledger_path": f"{cfg['storage']['current_root']}/FMDL3B2_RETRY_LEDGER.csv",
        "coverage_path": f"{cfg['storage']['current_root']}/FMDL3B2_COVERAGE.csv",
        "field_frequency_path": f"{cfg['storage']['current_root']}/FMDL3B2_FIELD_FREQUENCY.csv",
        "conflict_log_path": f"{cfg['storage']['current_root']}/FMDL3B2_CONFLICT_LOG.csv",
        "ambiguity_path": f"{cfg['storage']['current_root']}/FMDL3B2_AMBIGUOUS_MAPPING_GROUPS.csv",
        "qa_flags_path": f"{cfg['storage']['current_root']}/FMDL3B2_QA_FLAGS.csv",
        "performed_checks_path": f"{cfg['storage']['current_root']}/FMDL3B2_VALIDATION_CHECKS.csv",
        "comparability_bridge_path": f"{cfg['storage']['current_root']}/FMDL3B2_COMPARABILITY_BRIDGE.csv",
        "raw_artifact_index_path": f"{cfg['storage']['current_root']}/FMDL3B2_RAW_ARTIFACT_INDEX.csv",
        "normalized_shards": normalized_paths,
        "revision_shards": revision_paths,
        "source_index_shards": source_paths,
        "candidate_manifest_sha256": matrix.file_sha256(candidate_manifest),
        "raw_artifact_retention_days": cfg["sharding"]["raw_artifact_retention_days"],
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }

    matrix.write_json(release_root / "FMDL3B2_RELEASE.json", release)
    matrix.write_json(current_root / "FMDL3B2_RELEASE.json", release)
    shutil.copytree(current_root, archive_root)
    matrix.write_json(
        last_success,
        {
            "pointer_version": "1.0.0",
            "program_id": "FMDL-3B-2-MATRIX",
            "release_id": release_id,
            "published_at": published_at,
            "status": release["status"],
            "current_release_path": f"{cfg['storage']['current_root']}/FMDL3B2_RELEASE.json",
            "validation_path": release["validation_path"],
            "release_root": release["release_root"],
            "next_gate": release["next_gate"],
            "authority": release["authority"],
            "trade_authority": "NONE",
        },
    )
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
