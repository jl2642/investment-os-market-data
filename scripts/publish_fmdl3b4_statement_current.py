from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3b4_statement_current.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3B4_DECISION.json")
    validation = load_json(candidate / "FMDL3B4_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or validation.get("status") != "PASS":
        raise SystemExit("FMDL-3B-4 publication blocked")

    release_id = decision["release_id"]
    release_root = ROOT / cfg["publication"]["release_root"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    archive_root = ROOT / cfg["publication"]["archive_root"] / release_id
    last_success = ROOT / cfg["publication"]["last_success_path"]
    if release_root.exists() or archive_root.exists():
        raise SystemExit("immutable FMDL-3B-4 release already exists")

    shutil.copytree(candidate, release_root)
    if current_root.exists():
        shutil.rmtree(current_root)
    shutil.copytree(candidate, current_root)
    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3B-4",
        "status": decision["status"],
        "exit_gate": cfg["exit_gate"],
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "statement_base_release_id": decision["statement_base_release_id"],
        "comparability_release_id": decision["comparability_release_id"],
        "statement_catalog_path": f"{cfg['publication']['current_root']}/FMDL3B4_STATEMENT_CATALOG.csv",
        "statement_validation_path": f"{cfg['publication']['current_root']}/FMDL3B4_STATEMENT_VALIDATION_SNAPSHOT.json",
        "comparability_validation_path": f"{cfg['publication']['current_root']}/FMDL3B4_COMPARABILITY_VALIDATION_SNAPSHOT.json",
        "decision_path": f"{cfg['publication']['current_root']}/FMDL3B4_DECISION.json",
        "validation_path": f"{cfg['publication']['current_root']}/FMDL3B4_VALIDATION.json",
        "metrics": decision["metrics"],
        "controlled_limitations": decision.get("controlled_limitations", []),
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    write_json(release_root / "FMDL3B4_RELEASE.json", release)
    write_json(current_root / "FMDL3B4_RELEASE.json", release)
    shutil.copytree(current_root, archive_root)
    write_json(last_success, {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3B-4",
        "release_id": release_id,
        "published_at": published_at,
        "status": release["status"],
        "current_release_path": f"{cfg['publication']['current_root']}/FMDL3B4_RELEASE.json",
        "release_root": release["release_root"],
        "next_gate": release["next_gate"],
        "authority": release["authority"],
        "trade_authority": "NONE",
    })
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
