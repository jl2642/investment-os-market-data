from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "fmdl3a_benchmark.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish accepted FMDL-3A benchmark.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_json(args.config)
    publication = cfg["publication"]
    candidate_root = ROOT / publication["candidate_root"]
    current_root = ROOT / publication["current_root"]
    archive_root = ROOT / publication["archive_root"]
    source_index_current = ROOT / publication["source_index_current_root"]
    last_success_path = ROOT / publication["last_success_path"]

    validation = load_json(candidate_root / "FMDL3A_VALIDATION.json")
    decision = load_json(candidate_root / "FMDL3A_SOURCE_DECISION.json")
    if validation.get("status") != "PASS":
        raise SystemExit("FMDL-3A validation is not PASS; publication blocked")
    if decision.get("status") != "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN":
        raise SystemExit("FMDL-3A source decision is not accepted; publication blocked")
    if decision.get("trade_authority") != "NONE":
        raise SystemExit("trade authority must remain NONE")

    required_candidate_files = [
        "FMDL3A_SOURCE_DECISION.json",
        "FMDL3A_SOURCE_SUMMARY.csv",
        "FMDL3A_COVERAGE_MAP.csv",
        "FMDL3A_POINT_IN_TIME_EVIDENCE.csv",
        "FMDL3A_SUPPORT_QUARANTINE_MAP.csv",
        "FMDL3A_CAPITALIZATION_EVIDENCE.csv",
        "FMDL3_SOURCE_INDEX.csv",
        "FMDL3A_VALIDATION.json",
        "FMDL3A_MANIFEST.json",
    ]
    missing = [name for name in required_candidate_files if not (candidate_root / name).exists()]
    if missing:
        raise SystemExit(f"accepted candidate missing required files: {missing}")

    release_id = decision["run_id"]
    archive_release = archive_root / release_id
    if archive_release.exists():
        raise SystemExit(f"immutable archive already exists: {archive_release}")

    published_at = now_iso()
    shutil.copytree(candidate_root, archive_release)
    if current_root.exists():
        shutil.rmtree(current_root)
    shutil.copytree(candidate_root, current_root)

    source_index_current.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_root / "FMDL3_SOURCE_INDEX.csv", source_index_current / "FMDL3_SOURCE_INDEX.csv")

    release = {
        "release_version": "1.1.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3A",
        "status": "FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN",
        "exit_gate": "SOURCE_ROUTE_AND_NUMERIC_COVERAGE_GATES_FROZEN",
        "source_decision_path": "outputs/financials/benchmark/current/FMDL3A_SOURCE_DECISION.json",
        "source_summary_path": "outputs/financials/benchmark/current/FMDL3A_SOURCE_SUMMARY.csv",
        "coverage_map_path": "outputs/financials/benchmark/current/FMDL3A_COVERAGE_MAP.csv",
        "support_quarantine_map_path": "outputs/financials/benchmark/current/FMDL3A_SUPPORT_QUARANTINE_MAP.csv",
        "capitalization_evidence_path": "outputs/financials/benchmark/current/FMDL3A_CAPITALIZATION_EVIDENCE.csv",
        "point_in_time_evidence_path": "outputs/financials/benchmark/current/FMDL3A_POINT_IN_TIME_EVIDENCE.csv",
        "source_index_path": "outputs/financials/source_index/current/FMDL3_SOURCE_INDEX.csv",
        "validation_path": "outputs/financials/benchmark/current/FMDL3A_VALIDATION.json",
        "archive_path": str(archive_release.relative_to(ROOT)),
        "measured_metrics": decision["measured_metrics"],
        "frozen_numeric_gates": decision["frozen_numeric_gates"],
        "frozen_point_in_time_contract": decision["frozen_point_in_time_contract"],
        "valuation_semantics": decision["valuation_semantics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": decision["authority"],
        "trade_authority": decision["trade_authority"],
        "next_phase": "FMDL-3B",
    }
    write_json(current_root / "FMDL3A_RELEASE.json", release)
    write_json(archive_release / "FMDL3A_RELEASE.json", release)

    for root in [current_root, archive_release]:
        manifest = load_json(root / "FMDL3A_MANIFEST.json")
        manifest["status"] = "PUBLISHED"
        manifest["published_at"] = published_at
        manifest["release_id"] = release_id
        write_json(root / "FMDL3A_MANIFEST.json", manifest)

    last_success = {
        "pointer_version": "1.1.0",
        "program_id": "FMDL-3A",
        "release_id": release_id,
        "published_at": published_at,
        "status": release["status"],
        "current_release_path": "outputs/financials/benchmark/current/FMDL3A_RELEASE.json",
        "source_index_path": release["source_index_path"],
        "support_quarantine_map_path": release["support_quarantine_map_path"],
        "capitalization_evidence_path": release["capitalization_evidence_path"],
        "validation_path": release["validation_path"],
        "next_phase": "FMDL-3B",
        "authority": decision["authority"],
        "trade_authority": decision["trade_authority"],
    }
    write_json(last_success_path, last_success)
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
