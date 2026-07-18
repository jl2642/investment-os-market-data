from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/financials/comparability/candidate"
RELEASES = ROOT / "datasets/financials/comparability/releases"
CURRENT = ROOT / "outputs/financials/comparability/current"
ARCHIVE = ROOT / "outputs/financials/comparability/archive"
LAST_SUCCESS = ROOT / "outputs/status/FMDL3B3_LAST_SUCCESS.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    decision = load_json(CANDIDATE / "FMDL3B3_DECISION.json")
    validation = load_json(CANDIDATE / "FMDL3B3_VALIDATION.json")
    if decision.get("status") != "FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED" or validation.get("status") != "PASS":
        raise SystemExit("FMDL-3B-3 publication blocked")
    release_id = decision["release_id"]
    release_root = RELEASES / release_id
    archive_root = ARCHIVE / release_id
    if release_root.exists() or archive_root.exists():
        raise SystemExit("immutable FMDL-3B-3 release already exists")
    shutil.copytree(CANDIDATE, release_root)
    if CURRENT.exists():
        shutil.rmtree(CURRENT)
    CURRENT.mkdir(parents=True)
    compact = [
        "FMDL3B3_DECISION.json",
        "FMDL3B3_VALIDATION.json",
        "FMDL3B3_MANIFEST.json",
        "FMDL3B3_DOCUMENT_CLASSIFICATION_SUMMARY.csv",
        "FMDL3B3_PERIOD_STATUS_SUMMARY.csv",
        "FMDL3B3_COMPARABILITY_SUMMARY.csv",
        "FMDL3B3_FACT_EXCEPTION_SUMMARY.csv"
    ]
    for name in compact:
        shutil.copy2(CANDIDATE / name, CURRENT / name)
    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3B-3",
        "status": decision["status"],
        "exit_gate": "COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(CURRENT.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "revision_lineage_path": f"{release_root.relative_to(ROOT)}/FMDL3B3_REVISION_LINEAGE.parquet",
        "period_revision_status_path": f"{release_root.relative_to(ROOT)}/FMDL3B3_PERIOD_REVISION_STATUS.parquet",
        "fact_exception_path": f"{release_root.relative_to(ROOT)}/FMDL3B3_FACT_COMPARABILITY_EXCEPTIONS.parquet",
        "comparability_bridge_path": f"{release_root.relative_to(ROOT)}/FMDL3B3_COMPARABILITY_BRIDGE.parquet",
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"]
    }
    write_json(release_root / "FMDL3B3_RELEASE.json", release)
    write_json(CURRENT / "FMDL3B3_RELEASE.json", release)
    shutil.copytree(CURRENT, archive_root)
    write_json(LAST_SUCCESS, {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3B-3",
        "release_id": release_id,
        "published_at": published_at,
        "status": decision["status"],
        "current_release_path": "outputs/financials/comparability/current/FMDL3B3_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "next_gate": decision["next_gate"],
        "authority": decision["authority"],
        "trade_authority": "NONE"
    })
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
