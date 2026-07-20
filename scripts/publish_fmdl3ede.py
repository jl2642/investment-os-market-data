from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl3ede_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ede_propagation_resilience.json"


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL3E_DECISION.json")
    validation = core.read_json(candidate / "FMDL3E_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-D/E decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-D/E independent validation not PASS")
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
        "program_id": "FMDL-3E-DE",
        "status": cfg["exit_status"],
        "propagation_status": decision["propagation_status"],
        "resilience_status": decision["resilience_status"],
        "exit_gate": "INCREMENTAL_PROPAGATION_RESILIENCE_AND_REPLAY_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "entry_release_id": decision["metrics"]["entry_release_id"],
        "incremental_release_id": decision["metrics"]["incremental_release_id"],
        "source_fmdl3d_release_id": decision["metrics"]["source_fmdl3d_release_id"],
        "baseline_id": decision["metrics"]["baseline_id"],
        "market_acceptance_mode": decision["metrics"]["market_acceptance_mode"],
        "market_replay_from_date": decision["metrics"]["market_replay_from_date"],
        "market_replay_to_date": decision["metrics"]["market_replay_to_date"],
        "post_frozen_baseline_advance_observed": decision["metrics"]["post_frozen_baseline_advance_observed"],
        "propagated_unified_current_path": f"{cfg['publication']['current_root']}/FMDL3E_PROPAGATED_UNIFIED_CURRENT.parquet",
        "full_rebuild_reference_path": f"{cfg['publication']['current_root']}/FMDL3E_FULL_REBUILD_REFERENCE.parquet",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3E_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3E_VALIDATION.json",
        "resilience_report_path": f"{cfg['publication']['current_root']}/FMDL3E_RESILIENCE_REPORT.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        core.write_json(root / "FMDL3E_RELEASE.json", release)
    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3E-DE",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "propagation_status": decision["propagation_status"],
        "resilience_status": decision["resilience_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3E_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "entry_release_id": decision["metrics"]["entry_release_id"],
        "baseline_id": decision["metrics"]["baseline_id"],
        "market_acceptance_mode": decision["metrics"]["market_acceptance_mode"],
        "post_frozen_baseline_advance_observed": decision["metrics"]["post_frozen_baseline_advance_observed"],
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    core.write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
