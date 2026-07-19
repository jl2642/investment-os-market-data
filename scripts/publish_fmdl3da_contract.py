from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3da_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3DA_DECISION.json")
    validation = load_json(candidate / "FMDL3DA_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"]:
        raise SystemExit("FMDL-3D-A decision not accepted")
    if decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-A hard failures present")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3D-A independent validation not PASS")

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
        "program_id": "FMDL-3D-A",
        "status": cfg["exit_status"],
        "exit_gate": "VALUATION_AND_SHAREHOLDER_RETURN_CONTRACT_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "capitalization_pilot_path": f"{cfg['publication']['current_root']}/FMDL3DA_CAPITALIZATION_PILOT.csv",
        "valuation_detail_path": f"{cfg['publication']['current_root']}/FMDL3DA_VALUATION_METRIC_DETAIL.parquet",
        "valuation_pilot_current_path": f"{cfg['publication']['current_root']}/FMDL3DA_VALUATION_PILOT_CURRENT.parquet",
        "shareholder_event_contract_samples_path": f"{cfg['publication']['current_root']}/FMDL3DA_SHAREHOLDER_EVENT_CONTRACT_SAMPLES.csv",
        "coverage_path": f"{cfg['publication']['current_root']}/FMDL3DA_PILOT_COVERAGE.csv",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3DA_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3DA_VALIDATION.json",
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        write_json(root / "FMDL3DA_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3D-A",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3DA_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
