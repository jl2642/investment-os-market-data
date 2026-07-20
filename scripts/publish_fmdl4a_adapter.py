from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4a_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4a_research_handoff_adapter.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL4A_DECISION.json")
    validation = core.read_json(candidate / "FMDL4A_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4A decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4A independent validation not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / cfg["publication"]["release_root"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    archive_root = ROOT / cfg["publication"]["archive_root"] / release_id
    for destination in [release_root, current_root, archive_root]:
        copy_tree(candidate, destination)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-4A",
        "status": cfg["exit_status"],
        "exit_gate": "RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "external_canonical_base": decision["external_canonical_base"],
        "candidate_release_sequence": cfg["adapter"]["candidate_release_sequence"],
        "candidate_asset_architecture_version": cfg["adapter"]["candidate_asset_architecture_version"],
        "candidate_runtime_schema_version": cfg["adapter"]["candidate_runtime_schema_version"],
        "adapter_mode": cfg["adapter"]["mode"],
        "overlay_package_path": f"{cfg['publication']['current_root']}/FMDL4A_RELEASE5_ADAPTER_OVERLAY.zip",
        "overlay_manifest_path": f"{cfg['publication']['current_root']}/FMDL4A_RELEASE5_OVERLAY_MANIFEST.json",
        "evidence_envelope_path": f"{cfg['publication']['current_root']}/{cfg['adapter']['overlay_namespace']}/EVIDENCE/FMDL4A_EVIDENCE_ENVELOPE_CURRENT.parquet",
        "research_priority_registry_path": f"{cfg['publication']['current_root']}/{cfg['adapter']['overlay_namespace']}/EVIDENCE/FMDL4A_RESEARCH_PRIORITY_REGISTRY.csv",
        "binding_state_path": f"{cfg['publication']['current_root']}/{cfg['adapter']['overlay_namespace']}/STATE_CURRENT/FMDL4A_BINDING_STATE.json",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL4A_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL4A_VALIDATION.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "source_release_ids": decision["source_release_ids"],
        "controlled_limitations": decision["controlled_limitations"],
        "state_mutation_status": "NO_INVESTMENT_STATE_MUTATION",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4A_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4A",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL4A_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "external_base_release_sequence": cfg["external_canonical_base"]["release_sequence"],
        "candidate_release_sequence": cfg["adapter"]["candidate_release_sequence"],
        "external_base_sha256": cfg["external_canonical_base"]["package_sha256"],
        "adapter_mode": cfg["adapter"]["mode"],
        "universe_symbol_count": decision["metrics"]["universe_symbol_count"],
        "longlist_symbol_count": decision["metrics"]["longlist_symbol_count"],
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
