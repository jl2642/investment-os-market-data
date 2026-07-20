from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4b_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4b_candidate_research.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL4B_DECISION.json")
    validation = core.read_json(candidate / "FMDL4B_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4B decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4B validation not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / cfg["publication"]["release_root"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    archive_root = ROOT / cfg["publication"]["archive_root"] / release_id
    for destination in [release_root, current_root, archive_root]:
        copy_tree(candidate, destination)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "program_id": "FMDL-4B",
        "release_id": release_id,
        "research_version": decision["research_version"],
        "published_at": published_at,
        "status": cfg["exit_status"],
        "exit_gate": "CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "research_objects_jsonl_path": f"{cfg['publication']['current_root']}/FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.jsonl",
        "research_objects_csv_path": f"{cfg['publication']['current_root']}/FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.csv",
        "stage_registry_path": f"{cfg['publication']['current_root']}/FMDL4B_RESEARCH_STAGE_REGISTRY.csv",
        "graduation_decisions_path": f"{cfg['publication']['current_root']}/FMDL4B_GRADUATION_DECISIONS.csv",
        "source_ledger_path": f"{cfg['publication']['current_root']}/FMDL4B_SOURCE_LEDGER.json",
        "raw_score_proof_path": f"{cfg['publication']['current_root']}/FMDL4B_NO_RAW_SCORE_PROMOTION_PROOF.json",
        "zero_state_mutation_proof_path": f"{cfg['publication']['current_root']}/FMDL4B_ZERO_STATE_MUTATION_PROOF.json",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL4B_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL4B_VALIDATION.json",
        "bindings": decision["bindings"],
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "controlled_limitations": decision["controlled_limitations"],
        "graduated_meaning": decision["graduated_meaning"],
        "state_mutation_status": "NO_INVESTMENT_STATE_MUTATION",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4B_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4B",
        "release_id": release_id,
        "research_version": decision["research_version"],
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL4B_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "total_registry_count": decision["metrics"]["total_registry_count"],
        "formal_research_object_count": decision["metrics"]["formal_research_object_count"],
        "graduated_count": decision["metrics"]["graduated_count"],
        "deferred_count": decision["metrics"]["deferred_count"],
        "rejected_count": decision["metrics"]["rejected_count"],
        "graduated_meaning": decision["graduated_meaning"],
        "state_mutation_status": "NO_INVESTMENT_STATE_MUTATION",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
