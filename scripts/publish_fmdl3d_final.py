from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3d_final_contract.json"
TZ = ZoneInfo("Asia/Shanghai")


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
    decision = load_json(candidate / "FMDL3D_FINAL_DECISION.json")
    validation = load_json(candidate / "FMDL3D_FINAL_VALIDATION.json")
    interface = load_json(candidate / "FMDL3D_UNIFIED_CURRENT_INTERFACE.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3D Final decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3D Final independent validation not PASS")
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
        "program_id": "FMDL-3D-FINAL",
        "status": cfg["exit_status"],
        "exit_gate": "VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "market_as_of_date": interface["market_as_of_date"],
        "unified_current_path": f"{cfg['publication']['current_root']}/FMDL3D_UNIFIED_CURRENT.parquet",
        "unified_interface_path": f"{cfg['publication']['current_root']}/FMDL3D_UNIFIED_CURRENT_INTERFACE.json",
        "unified_release_index_path": f"{cfg['publication']['current_root']}/FMDL3D_UNIFIED_RELEASE_INDEX.json",
        "component_release_matrix_path": f"{cfg['publication']['current_root']}/FMDL3D_COMPONENT_RELEASE_MATRIX.csv",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3D_FINAL_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3D_FINAL_VALIDATION.json",
        "component_release_ids": decision["component_release_ids"],
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        write_json(root / "FMDL3D_FINAL_RELEASE.json", release)
    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3D-FINAL",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3D_FINAL_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "market_as_of_date": interface["market_as_of_date"],
        "component_release_ids": decision["component_release_ids"],
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
