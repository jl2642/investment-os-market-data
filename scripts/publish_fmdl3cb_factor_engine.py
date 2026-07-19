from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3cb_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3CB_DECISION.json")
    validation = load_json(candidate / "FMDL3CB_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        raise SystemExit("candidate decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        raise SystemExit("candidate validation not accepted")

    release_id = decision["release_id"]
    release_root = ROOT / cfg["publication"]["release_parent"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    archive_root = ROOT / cfg["publication"]["archive_parent"] / release_id
    for path in [release_root, current_root, archive_root]:
        if path.exists():
            shutil.rmtree(path)
    shutil.copytree(candidate, release_root)

    compact_files = [
        "FMDL3CB_LATEST_FACTOR_CURRENT.parquet",
        "FMDL3CB_SECTOR_PROFILES.csv",
        "FMDL3CB_QUALITY_SUMMARY.csv",
        "FMDL3CB_FACTOR_COVERAGE.csv",
        "FMDL3CB_DECISION.json",
        "FMDL3CB_VALIDATION.json",
        "FMDL3CB_MANIFEST.json",
        "FMDL3CB_STATEMENT_CURRENT_POINTER.json",
        "FMDL3CB_FACTOR_CONTRACT_POINTER.json",
    ]
    for name in compact_files:
        copy_file(candidate / name, current_root / name)
        copy_file(candidate / name, archive_root / name)

    history_paths = sorted((release_root / "factor_history").glob("shard-*.parquet"))
    derived_paths = sorted((release_root / "derived_inputs").glob("shard-*.parquet"))
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-B",
        "status": cfg["exit_status"],
        "exit_gate": "FINANCIAL_FACTOR_ENGINE_MVP_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "statement_current_release_id": decision["metrics"]["statement_current_release_id"],
        "factor_contract_release_id": decision["metrics"]["factor_contract_release_id"],
        "factor_history_shards": [str(path.relative_to(ROOT)) for path in history_paths],
        "derived_input_shards": [str(path.relative_to(ROOT)) for path in derived_paths],
        "latest_factor_current_path": str((current_root / "FMDL3CB_LATEST_FACTOR_CURRENT.parquet").relative_to(ROOT)),
        "sector_profile_path": str((current_root / "FMDL3CB_SECTOR_PROFILES.csv").relative_to(ROOT)),
        "quality_summary_path": str((current_root / "FMDL3CB_QUALITY_SUMMARY.csv").relative_to(ROOT)),
        "factor_coverage_path": str((current_root / "FMDL3CB_FACTOR_COVERAGE.csv").relative_to(ROOT)),
        "decision_path": str((current_root / "FMDL3CB_DECISION.json").relative_to(ROOT)),
        "validation_path": str((current_root / "FMDL3CB_VALIDATION.json").relative_to(ROOT)),
        "metrics": decision["metrics"],
        "controlled_limitations": decision.get("controlled_limitations", []),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(release_root / "FMDL3CB_RELEASE.json", release)
    write_json(current_root / "FMDL3CB_RELEASE.json", release)
    write_json(archive_root / "FMDL3CB_RELEASE.json", release)
    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3C-B",
        "release_id": release_id,
        "published_at": release["published_at"],
        "status": cfg["exit_status"],
        "current_release_path": str((current_root / "FMDL3CB_RELEASE.json").relative_to(ROOT)),
        "release_root": str(release_root.relative_to(ROOT)),
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
