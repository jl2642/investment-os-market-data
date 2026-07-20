from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4_final_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4_final_operational_acceptance.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    publication = cfg["publication"]
    candidate = ROOT / publication["candidate_root"]
    decision = core.read_json(candidate / "FMDL4_FINAL_DECISION.json")
    validation = core.read_json(candidate / "FMDL4_FINAL_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4-FINAL decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4-FINAL independent validation not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / publication["release_root"] / release_id
    current_root = ROOT / publication["current_root"]
    archive_root = ROOT / publication["archive_root"] / release_id
    for destination in [release_root, current_root, archive_root]:
        copy_tree(candidate, destination)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "program_id": "FMDL-4-FINAL",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "exit_gate": "PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION_ACCEPTED",
        "composition_sequence": publication["composition_sequence"],
        "composition_mode": "IMMUTABLE_EXTERNAL_BASE_PLUS_VERSIONED_ADDITIVE_RELEASES",
        "composed_canonical_state": "RELEASE4_EXTERNAL_BASE_PLUS_FMDL4A_RELEASE5_PLUS_FMDL4B_RESEARCH_PLUS_FMDL4C_RELEASE6_PLUS_FMDL4D_RELEASE7_PLUS_FMDL4FINAL_RELEASE8",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "external_canonical_base": decision["external_canonical_base"],
        "component_release_ids": decision["component_release_ids"],
        "overlay_package_path": f"{publication['current_root']}/{publication['overlay_package_name']}",
        "manifest_path": f"{publication['current_root']}/FMDL4_FINAL_RELEASE8_MANIFEST.json",
        "lineage_registry_path": f"{publication['current_root']}/{publication['overlay_namespace']}/STATE_CURRENT/FMDL4_FINAL_CHAIN_REGISTRY.csv",
        "capability_matrix_path": f"{publication['current_root']}/{publication['overlay_namespace']}/CORE_STATIC/FMDL4_FINAL_CAPABILITY_MATRIX.json",
        "operational_state_audit_path": f"{publication['current_root']}/{publication['overlay_namespace']}/STATE_CURRENT/FMDL4_FINAL_OPERATIONAL_STATE_AUDIT.json",
        "file_library_maintenance_plan_path": f"{publication['current_root']}/{publication['overlay_namespace']}/EVIDENCE/FMDL4_FINAL_FILE_LIBRARY_MAINTENANCE_PLAN.json",
        "canonical_refresh_requirements_path": f"{publication['current_root']}/{publication['overlay_namespace']}/EVIDENCE/FMDL4_FINAL_CANONICAL_REFRESH_REQUIREMENTS.json",
        "decision_path": f"{publication['current_root']}/FMDL4_FINAL_DECISION.json",
        "validation_path": f"{publication['current_root']}/FMDL4_FINAL_VALIDATION.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "capability_summary": decision["capability_summary"],
        "file_library_single_package_status": "RELEASE4_ACTIVE_RELEASE8_REFRESH_REQUIRED",
        "real_account_simulation_candidate_reconciliation_status": "REQUIRED_POST_FMDL4_FINAL",
        "recommended_next_operation": cfg["recommended_next_operation"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4_FINAL_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4-FINAL",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{publication['current_root']}/FMDL4_FINAL_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "composition_sequence": publication["composition_sequence"],
        "external_file_library_release_sequence": cfg["external_canonical_base"]["release_sequence"],
        "universe_symbol_count": decision["metrics"]["universe_symbol_count"],
        "longlist_symbol_count": decision["metrics"]["longlist_symbol_count"],
        "research_object_count": decision["metrics"]["research_object_count"],
        "graduated_count": decision["metrics"]["graduated_count"],
        "lineage_record_count": decision["metrics"]["lineage_record_count"],
        "file_library_single_package_status": "RELEASE8_REFRESH_REQUIRED",
        "account_state_reconciliation_status": "REQUIRED",
        "recommended_next_operation": cfg["recommended_next_operation"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    core.write_json(ROOT / publication["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
