from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "outputs/architecture/candidate/FMDL3_ARCHITECTURE_VALIDATION.json"
CURRENT_DIR = ROOT / "outputs/architecture/current"
STATUS_PATH = ROOT / "outputs/status/FMDL3_ARCHITECTURE_LAST_SUCCESS.json"


def main() -> int:
    if not CANDIDATE.exists():
        raise FileNotFoundError(f"Missing architecture candidate: {CANDIDATE}")

    validation = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise RuntimeError("FMDL-3 architecture candidate did not pass validation")

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    release_id = f"FMDL3_ARCH_{now.strftime('%Y%m%dT%H%M%S%z')}"
    CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)

    current_validation = dict(validation)
    current_validation["published_at"] = now.isoformat(timespec="seconds")
    current_validation["release_id"] = release_id
    current_validation["publication_status"] = "PUBLISHED"
    current_validation_path = CURRENT_DIR / "FMDL3_ARCHITECTURE_VALIDATION.json"
    current_validation_path.write_text(
        json.dumps(current_validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": now.isoformat(timespec="seconds"),
        "program_id": "FMDL-3",
        "status": "FMDL3_ARCHITECTURE_ACCEPTED",
        "architecture_state": "FROZEN_FOR_FMDL3A_EXECUTION",
        "validation_path": "outputs/architecture/current/FMDL3_ARCHITECTURE_VALIDATION.json",
        "contract_path": "config/fmdl3_program_contract.json",
        "architecture_document": "docs/FMDL-3_ARCHITECTURE.md",
        "point_in_time_policy": "docs/FMDL-3_POINT_IN_TIME_POLICY.md",
        "phased_plan": "docs/FMDL-3_PHASED_PLAN.md",
        "next_phase": "FMDL-3A",
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }
    (CURRENT_DIR / "FMDL3_ARCHITECTURE_RELEASE.json").write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    STATUS_PATH.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive_dir = ROOT / "outputs/architecture/archive" / release_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current_validation_path, archive_dir / current_validation_path.name)
    shutil.copy2(CURRENT_DIR / "FMDL3_ARCHITECTURE_RELEASE.json", archive_dir / "FMDL3_ARCHITECTURE_RELEASE.json")

    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
