from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import fmdl3ebc_core as bc

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ebc_incremental_refresh.json"


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def main() -> int:
    cfg = bc.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = bc.read_json(candidate / "FMDL3EBC_DECISION.json")
    validation = bc.read_json(candidate / "FMDL3EBC_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-BC decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("FMDL-3E-BC independent validation not PASS")
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
        "program_id": "FMDL-3E-BC",
        "status": cfg["exit_status"],
        "market_status": decision["market_status"],
        "financial_status": decision["financial_status"],
        "exit_gate": "MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "baseline_id": decision["metrics"]["baseline_id"],
        "source_fmdl3d_release_id": decision["metrics"]["source_fmdl3d_release_id"],
        "baseline_market_as_of_date": decision["metrics"]["baseline_market_as_of_date"],
        "refreshed_market_as_of_date": decision["metrics"]["refreshed_market_as_of_date"],
        "event_ledger_path": f"{cfg['publication']['current_root']}/FMDL3EBC_DELTA_EVENT_LEDGER.parquet",
        "market_delta_path": f"{cfg['publication']['current_root']}/FMDL3EB_MARKET_DELTA.parquet",
        "financial_event_ledger_path": f"{cfg['publication']['current_root']}/FMDL3EC_FINANCIAL_EVENT_LEDGER.parquet",
        "financial_fact_delta_path": f"{cfg['publication']['current_root']}/FMDL3EC_FINANCIAL_FACT_DELTA.parquet",
        "financial_version_ledger_path": f"{cfg['publication']['current_root']}/FMDL3EC_FINANCIAL_VERSION_LEDGER.parquet",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3EBC_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3EBC_VALIDATION.json",
        "metrics": decision["metrics"],
        "semantic_hashes": decision["semantic_hashes"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, current_root, archive_root]:
        bc.write_json(root / "FMDL3EBC_RELEASE.json", release)
    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3E-BC",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "market_status": decision["market_status"],
        "financial_status": decision["financial_status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3EBC_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "baseline_id": decision["metrics"]["baseline_id"],
        "baseline_market_as_of_date": decision["metrics"]["baseline_market_as_of_date"],
        "refreshed_market_as_of_date": decision["metrics"]["refreshed_market_as_of_date"],
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    bc.write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
