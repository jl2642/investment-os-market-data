from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl4d_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4d_thesis_attribution.json"
TZ = ZoneInfo("Asia/Shanghai")


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL4D_DECISION.json")
    validation = core.read_json(candidate / "FMDL4D_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-4D decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-4D validation not PASS")

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
        "program_id": "FMDL-4D",
        "status": cfg["exit_status"],
        "exit_gate": "THESIS_ATTRIBUTION_AND_FEEDBACK_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "composition_sequence": cfg["tracking"]["composition_sequence"],
        "composition_mode": "IMMUTABLE_BASE_PLUS_VERSIONED_ADDITIVE_STATE_OVERLAYS",
        "composed_canonical_state": "RELEASE4_EXTERNAL_BASE_PLUS_RELEASE5_ADAPTER_PLUS_FMDL4B_RESEARCH_PLUS_RELEASE6_STATE_PLUS_RELEASE7_THESIS_ATTRIBUTION_OVERLAY",
        "fmdl4c_release_id": decision["bindings"]["fmdl4c_release_id"],
        "fmdl4b_release_id": decision["bindings"]["fmdl4b_release_id"],
        "fmdl4a_release_id": decision["bindings"]["fmdl4a_release_id"],
        "external_base_sha256": decision["bindings"]["external_base_sha256"],
        "thesis_version": cfg["tracking"]["thesis_version"],
        "overlay_package_path": f"{cfg['publication']['current_root']}/FMDL4D_RELEASE7_THESIS_ATTRIBUTION_OVERLAY.zip",
        "composition_manifest_path": f"{cfg['publication']['current_root']}/FMDL4D_RELEASE7_COMPOSITION_MANIFEST.json",
        "thesis_records_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/STATE_CURRENT/FMDL4D_THESIS_RECORDS.jsonl",
        "catalyst_registry_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/STATE_CURRENT/FMDL4D_CATALYST_REGISTRY.csv",
        "prove_kill_registry_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/STATE_CURRENT/FMDL4D_PROVE_KILL_REGISTRY.csv",
        "attribution_registry_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/STATE_CURRENT/FMDL4D_ATTRIBUTION_REGISTRY.csv",
        "decision_log_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/STATE_CURRENT/FMDL4D_DECISION_LOG.csv",
        "feedback_proposals_path": f"{cfg['publication']['current_root']}/{cfg['tracking']['overlay_namespace']}/EVIDENCE/FMDL4D_FEEDBACK_PROPOSALS.jsonl",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL4D_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL4D_VALIDATION.json",
        "metrics": decision["metrics"],
        "thesis_summary": decision["thesis_summary"],
        "semantic_hashes": decision["semantic_hashes"],
        "controlled_limitations": decision["controlled_limitations"],
        "observable_return_status": "NOT_YET_OBSERVABLE_NO_POSITION",
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "rule_mutation_count": 0,
        "state_mutation_status": "THESIS_AND_ATTRIBUTION_OVERLAY_ONLY",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL4D_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-4D",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL4D_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "composition_sequence": cfg["tracking"]["composition_sequence"],
        "fmdl4c_release_id": decision["bindings"]["fmdl4c_release_id"],
        "thesis_version": cfg["tracking"]["thesis_version"],
        "thesis_record_count": decision["metrics"]["thesis_record_count"],
        "catalyst_count": decision["metrics"]["catalyst_count"],
        "prove_kill_count": decision["metrics"]["prove_kill_count"],
        "observable_return_count": decision["metrics"]["observable_return_count"],
        "feedback_proposal_count": decision["metrics"]["feedback_proposal_count"],
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "rule_mutation_count": 0,
        "state_mutation_status": "THESIS_AND_ATTRIBUTION_OVERLAY_ONLY",
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
