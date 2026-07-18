from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/fmdl3b_statement_store.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    cfg = load(CFG)
    publication = cfg["publication"]
    candidate = ROOT / publication["candidate_root"]
    current = ROOT / publication["current_root"]
    archive = ROOT / publication["archive_root"]
    validation = load(candidate / "FMDL3B1_VALIDATION.json")
    decision = load(candidate / "FMDL3B1_DECISION.json")
    if validation.get("status") != "PASS" or decision.get("status") != "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT":
        raise SystemExit("publication blocked")
    release_id = decision["run_id"]
    archive_release = archive / release_id
    if archive_release.exists():
        raise SystemExit(f"immutable archive exists: {archive_release}")
    shutil.copytree(candidate, archive_release)
    if current.exists():
        shutil.rmtree(current)
    shutil.copytree(candidate, current)
    published_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3B-1",
        "status": "FMDL3B1_ACCEPTED_NORMALIZATION_PILOT",
        "exit_gate": "NORMALIZATION_PILOT_ACCEPTED_FULL_UNIVERSE_BUILD_AUTHORIZED",
        "current_root": publication["current_root"],
        "archive_path": str(archive_release.relative_to(ROOT)),
        "raw_fact_path": f"{publication['current_root']}/FMDL3B_RAW_FACTS.csv",
        "normalized_long_path": f"{publication['current_root']}/FMDL3B_NORMALIZED_LONG.csv",
        "source_index_path": f"{publication['current_root']}/FMDL3B_SOURCE_INDEX.csv",
        "revision_ledger_path": f"{publication['current_root']}/FMDL3B_REVISION_LEDGER.csv",
        "comparability_bridge_path": f"{publication['current_root']}/FMDL3B_COMPARABILITY_BRIDGE.csv",
        "conflict_log_path": f"{publication['current_root']}/FMDL3B_CONFLICT_LOG.csv",
        "qa_flags_path": f"{publication['current_root']}/FMDL3B_QA_FLAGS.csv",
        "validation_checks_path": f"{publication['current_root']}/FMDL3B_VALIDATION_CHECKS.csv",
        "support_map_path": f"{publication['current_root']}/FMDL3B_SUPPORT_MAP.csv",
        "validation_path": f"{publication['current_root']}/FMDL3B1_VALIDATION.json",
        "metrics": decision["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_phase": "FMDL-3B-2",
    }
    for root in [current, archive_release]:
        dump(root / "FMDL3B1_RELEASE.json", release)
    dump(
        ROOT / publication["last_success_path"],
        {
            "pointer_version": "1.0.0",
            "program_id": "FMDL-3B-1",
            "release_id": release_id,
            "published_at": published_at,
            "status": release["status"],
            "current_release_path": f"{publication['current_root']}/FMDL3B1_RELEASE.json",
            "validation_path": release["validation_path"],
            "next_phase": "FMDL-3B-2",
            "authority": release["authority"],
            "trade_authority": "NONE",
        },
    )
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
