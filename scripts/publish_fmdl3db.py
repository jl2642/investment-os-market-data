from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.fmdl3db_core import ROOT, load_json, write_json

TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3db_engine.json"


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    config = load_json(CONFIG)
    candidate = ROOT / config["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3DB_DECISION.json")
    validation = load_json(candidate / "FMDL3DB_VALIDATION.json")
    if decision.get("status") != config["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-B decision is not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-B independent validation is not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / config["publication"]["release_root"] / release_id
    current_root = ROOT / config["publication"]["current_root"]
    archive_root = ROOT / config["publication"]["archive_root"] / release_id
    copy_tree(candidate, release_root)
    copy_tree(candidate, current_root)
    copy_tree(candidate, archive_root)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3D-B",
        "status": config["exit_status"],
        "exit_gate": "EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "capitalization_current_path": f"{config['publication']['current_root']}/FMDL3DB_CAPITALIZATION_CURRENT.parquet",
        "effective_share_ledger_path": f"{config['publication']['current_root']}/FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet",
        "coverage_path": f"{config['publication']['current_root']}/FMDL3DB_COVERAGE.csv",
        "quarantine_path": f"{config['publication']['current_root']}/FMDL3DB_QUARANTINE.csv",
        "retry_ledger_path": f"{config['publication']['current_root']}/FMDL3DB_RETRY_LEDGER.csv",
        "decision_path": f"{config['publication']['current_root']}/FMDL3DB_DECISION.json",
        "validation_path": f"{config['publication']['current_root']}/FMDL3DB_VALIDATION.json",
        "source_release": decision["source_release"],
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": config["authority"],
        "trade_authority": "NONE",
        "next_gate": config["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        write_json(root / "FMDL3DB_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3D-B",
        "release_id": release_id,
        "published_at": published_at,
        "status": config["exit_status"],
        "current_release_path": f"{config['publication']['current_root']}/FMDL3DB_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "source_market_release_id": decision["source_release"]["run_id"],
        "source_as_of_date": decision["source_release"]["as_of_date"],
        "next_gate": config["next_gate"],
        "authority": config["authority"],
        "trade_authority": "NONE",
    }
    write_json(ROOT / config["publication"]["last_success_path"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
