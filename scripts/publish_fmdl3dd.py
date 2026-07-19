from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3dd_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3DD_DECISION.json")
    validation = load_json(candidate / "FMDL3DD_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-D decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-D validation not PASS")
    release_id = str(decision["release_id"])
    release_root = ROOT / cfg["publication"]["release_root"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    archive_root = ROOT / cfg["publication"]["archive_root"] / release_id
    copy_tree(candidate, release_root)
    copy_tree(candidate, current_root)
    copy_tree(candidate, archive_root)
    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3D-D",
        "status": cfg["exit_status"],
        "exit_gate": "SHAREHOLDER_RETURN_EVENT_CURRENT_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "shareholder_return_current_path": f"{cfg['publication']['current_root']}/FMDL3DD_SHAREHOLDER_RETURN_CURRENT.parquet",
        "event_ledger_path": f"{cfg['publication']['current_root']}/FMDL3DD_EVENT_LEDGER.parquet",
        "coverage_path": f"{cfg['publication']['current_root']}/FMDL3DD_COVERAGE.csv",
        "event_coverage_path": f"{cfg['publication']['current_root']}/FMDL3DD_EVENT_COVERAGE.csv",
        "quarantine_path": f"{cfg['publication']['current_root']}/FMDL3DD_QUARANTINE.csv",
        "attempts_path": f"{cfg['publication']['current_root']}/FMDL3DD_DIVIDEND_SOURCE_ATTEMPTS.csv",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3DD_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3DD_VALIDATION.json",
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        write_json(root / "FMDL3DD_RELEASE.json", release)
    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3D-D",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3DD_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "market_as_of_date": decision["metrics"]["market_as_of_date"],
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
