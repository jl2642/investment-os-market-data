from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl3efinal_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3efinal_operational_closure.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL3EFINAL_DECISION.json")
    validation = core.read_json(candidate / "FMDL3EFINAL_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-Final decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-Final independent validation not PASS")

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
        "program_id": cfg["program_id"],
        "status": cfg["exit_status"],
        "exit_gate": "UNIFIED_OPERATIONAL_ACCEPTANCE_AND_CANONICAL_CLOSURE_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "canonical_chain": decision["canonical_chain"],
        "baseline_id": decision["baseline_id"],
        "market_watermark": decision["market_watermark"],
        "unified_current_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_UNIFIED_CURRENT.parquet",
        "operational_state_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_OPERATIONAL_STATE.json",
        "limitation_register_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_LIMITATION_REGISTER.json",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_VALIDATION.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in (release_root, current_root, archive_root):
        core.write_json(root / "FMDL3EFINAL_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": cfg["program_id"],
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3EFINAL_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "canonical_chain": decision["canonical_chain"],
        "baseline_id": decision["baseline_id"],
        "market_watermark": decision["market_watermark"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(ROOT / cfg["publication"]["last_success"], pointer)
    core.write_json(ROOT / cfg["publication"]["canonical_last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
