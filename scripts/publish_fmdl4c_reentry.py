from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4c_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4c_reentry_controls.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["overlay"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL4C_DECISION.json")
    validation = core.read_json(candidate / "FMDL4C_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4C decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4C validation not PASS")

    release_id = str(decision["release_id"])
    release_root = ROOT / cfg["overlay"]["release_root"] / release_id
    current_root = ROOT / cfg["overlay"]["current_root"]
    archive_root = ROOT / cfg["overlay"]["archive_root"] / release_id
    for destination in [release_root, current_root, archive_root]:
        copy_tree(candidate, destination)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "program_id": "FMDL-4C",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "exit_gate": "INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED",
        "composition_sequence": cfg["composition_inputs"]["release6_composition_sequence"],
        "composition_mode": cfg["composition_inputs"]["composition_mode"],
        "composed_canonical_state": "RELEASE4_EXTERNAL_BASE_PLUS_RELEASE5_ADAPTER_PLUS_FMDL4B_RESEARCH_PLUS_RELEASE6_STATE_OVERLAY",
        "external_canonical_base": cfg["composition_inputs"]["external_canonical_base"],
        "release5_adapter_release_id": decision["bindings"]["fmdl4a_release_id"],
        "fmdl4b_research_release_id": decision["bindings"]["fmdl4b_release_id"],
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "composition_manifest_path": f"{cfg['overlay']['current_root']}/FMDL4C_RELEASE6_COMPOSITION_MANIFEST.json",
        "overlay_package_path": f"{cfg['overlay']['current_root']}/FMDL4C_RELEASE6_STATE_OVERLAY.zip",
        "state_transitions_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_STATE_TRANSITIONS.jsonl",
        "reentry_queue_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_REENTRY_REVIEW_QUEUE.csv",
        "candidate_router_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_CANDIDATE_ROUTER.csv",
        "simulation_router_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_SIMULATION_ROUTER.csv",
        "real_account_router_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_REAL_ACCOUNT_ROUTER.csv",
        "versioned_diff_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_VERSIONED_DIFF.json",
        "rollback_and_lkg_path": f"{cfg['overlay']['current_root']}/{cfg['overlay']['namespace']}/STATE_CURRENT/FMDL4C_ROLLBACK_AND_LKG_PROOF.json",
        "decision_path": f"{cfg['overlay']['current_root']}/FMDL4C_DECISION.json",
        "validation_path": f"{cfg['overlay']['current_root']}/FMDL4C_VALIDATION.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "reentry_summary": decision["reentry_summary"],
        "state_mutation_status": "REENTRY_REVIEW_QUEUE_OVERLAY_ONLY",
        "actual_candidate_pool_mutation_count": 0,
        "actual_simulation_mutation_count": 0,
        "actual_real_account_mutation_count": 0,
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4C_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4C",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['overlay']['current_root']}/FMDL4C_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "composition_sequence": cfg["composition_inputs"]["release6_composition_sequence"],
        "external_base_release_sequence": cfg["composition_inputs"]["external_canonical_base"]["release_sequence"],
        "external_base_sha256": cfg["composition_inputs"]["external_canonical_base"]["package_sha256"],
        "fmdl4a_release_id": decision["bindings"]["fmdl4a_release_id"],
        "fmdl4b_release_id": decision["bindings"]["fmdl4b_release_id"],
        "reentry_transition_count": decision["metrics"]["reentry_transition_count"],
        "candidate_pool_reentry_review_count": decision["metrics"]["candidate_pool_reentry_review_count"],
        "shadow_track_reentry_review_count": decision["metrics"]["shadow_track_reentry_review_count"],
        "simulation_admission_count": 0,
        "real_account_admission_count": 0,
        "state_mutation_status": "REENTRY_REVIEW_QUEUE_OVERLAY_ONLY",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(ROOT / cfg["overlay"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
