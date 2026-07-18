from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3b2_full_build.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    cfg = load(CONFIG)
    publication = cfg["publication"]
    candidate = ROOT / publication["candidate_root"]
    current = ROOT / publication["current_root"]
    archive_root = ROOT / publication["archive_root"]
    decision = load(candidate / "FMDL3B2_CANARY_DECISION.json")
    validation = load(candidate / "FMDL3B2_CANARY_VALIDATION.json")
    if decision.get("status") != "FMDL3B2_CANARY_ACCEPTED_FULL_UNIVERSE_MATRIX_AUTHORIZED" or validation.get("status") != "PASS":
        raise SystemExit("canary publication blocked")
    release_id = decision["run_id"]
    archive = archive_root / release_id
    if archive.exists():
        raise SystemExit(f"immutable archive exists: {archive}")
    shutil.copytree(candidate, archive)
    if current.exists():
        shutil.rmtree(current)
    shutil.copytree(candidate, current)
    published_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3B-2-CANARY",
        "status": decision["status"],
        "exit_gate": "RUNTIME_STORAGE_AND_SHARDING_CANARY_ACCEPTED",
        "current_root": publication["current_root"],
        "archive_path": str(archive.relative_to(ROOT)),
        "decision_path": f"{publication['current_root']}/FMDL3B2_CANARY_DECISION.json",
        "validation_path": f"{publication['current_root']}/FMDL3B2_CANARY_VALIDATION.json",
        "runtime_storage_path": f"{publication['current_root']}/FMDL3B2_CANARY_RUNTIME_STORAGE.json",
        "symbols_path": f"{publication['current_root']}/FMDL3B2_CANARY_SYMBOLS.csv",
        "support_map_path": f"{publication['current_root']}/FMDL3B2_CANARY_SUPPORT_MAP.csv",
        "field_frequency_path": f"{publication['current_root']}/FMDL3B2_CANARY_FIELD_FREQUENCY.csv",
        "raw_fact_path": f"{publication['current_root']}/FMDL3B2_CANARY_RAW_FACTS.parquet",
        "normalized_long_path": f"{publication['current_root']}/FMDL3B2_CANARY_NORMALIZED_LONG.parquet",
        "revision_ledger_path": f"{publication['current_root']}/FMDL3B2_CANARY_REVISION_LEDGER.parquet",
        "source_index_path": f"{publication['current_root']}/FMDL3B2_CANARY_SOURCE_INDEX.parquet",
        "metrics": decision["metrics"],
        "runtime_storage": validation["runtime_storage"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    for root in [current, archive]:
        dump(root / "FMDL3B2_CANARY_RELEASE.json", release)
    dump(
        ROOT / publication["last_success_path"],
        {
            "pointer_version": "1.0.0",
            "program_id": "FMDL-3B-2-CANARY",
            "release_id": release_id,
            "published_at": published_at,
            "status": release["status"],
            "current_release_path": f"{publication['current_root']}/FMDL3B2_CANARY_RELEASE.json",
            "validation_path": release["validation_path"],
            "runtime_storage_path": release["runtime_storage_path"],
            "next_gate": release["next_gate"],
            "authority": release["authority"],
            "trade_authority": "NONE",
        },
    )
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
