from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4_architecture_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl4_program_contract.json"


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    publication = cfg["publication_contract"]
    candidate = ROOT / publication["candidate_root"]
    decision = core.read_json(candidate / "FMDL4_ARCHITECTURE_DECISION.json")
    validation = core.read_json(candidate / "FMDL4_ARCHITECTURE_VALIDATION.json")
    independent = core.read_json(candidate / "FMDL4_ARCHITECTURE_INDEPENDENT_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4 architecture decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4 architecture validation not PASS")
    if independent.get("status") != "PASS" or independent.get("hard_failures") != []:
        raise SystemExit("FMDL-4 independent architecture validation not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / publication["release_root"] / release_id
    current_root = ROOT / publication["current_root"]
    archive_root = ROOT / publication["archive_root"] / release_id
    copy_tree(candidate, release_root)
    copy_tree(candidate, current_root)
    copy_tree(candidate, archive_root)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "program_id": "FMDL-4",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "architecture_state": cfg["architecture_state"],
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "contract_path": f"{publication['current_root']}/FMDL4_ARCHITECTURE_CONTRACT.json",
        "decision_path": f"{publication['current_root']}/FMDL4_ARCHITECTURE_DECISION.json",
        "validation_path": f"{publication['current_root']}/FMDL4_ARCHITECTURE_VALIDATION.json",
        "independent_validation_path": f"{publication['current_root']}/FMDL4_ARCHITECTURE_INDEPENDENT_VALIDATION.json",
        "bindings": decision["bindings"],
        "external_investment_os_baseline": cfg["external_investment_os_baseline"],
        "phase_sequence": cfg["phase_sequence"],
        "metrics": decision["metrics"],
        "controlled_limitations": cfg["controlled_limitations"],
        "contract_semantic_hash": decision["contract_semantic_hash"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4_ARCHITECTURE_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "architecture_state": cfg["architecture_state"],
        "current_release_path": f"{publication['current_root']}/FMDL4_ARCHITECTURE_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "bound_fmdl3e_release_id": decision["bindings"].get("fmdl3e_release_id"),
        "bound_fmdl2_release_id": decision["bindings"].get("fmdl2_release_id"),
        "bound_fmdl3cd_release_id": decision["bindings"].get("fmdl3cd_release_id"),
        "external_investment_os_release_sequence": cfg["external_investment_os_baseline"]["release_sequence"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    core.write_json(ROOT / publication["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
