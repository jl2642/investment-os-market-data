from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CANDIDATE = ROOT / "outputs/financial_factors/contract/candidate"
CURRENT = ROOT / "outputs/financial_factors/contract/current"
ARCHIVE = ROOT / "outputs/financial_factors/contract/archive"
RELEASES = ROOT / "datasets/financial_factors/contract/releases"
STATUS = ROOT / "outputs/status/FMDL3CA_LAST_SUCCESS.json"


def load(name: str):
    return json.loads((CANDIDATE / name).read_text(encoding="utf-8"))


def copy_tree(source: Path, target: Path):
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    decision = load("FMDL3CA_DECISION.json")
    validation = load("FMDL3CA_VALIDATION.json")
    if decision.get("status") != "FMDL3CA_FACTOR_ARCHITECTURE_AND_CONTRACT_ACCEPTED":
        raise SystemExit("FMDL-3C-A candidate not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures"):
        raise SystemExit("FMDL-3C-A validation not accepted")

    release_id = decision["release_id"]
    release_root = RELEASES / release_id
    archive_root = ARCHIVE / release_id
    copy_tree(CANDIDATE, release_root)
    copy_tree(CANDIDATE, CURRENT)
    copy_tree(CANDIDATE, archive_root)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3C-A",
        "status": decision["status"],
        "exit_gate": "FACTOR_ARCHITECTURE_AND_CONTRACT_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(CURRENT.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "factor_count": decision["metrics"]["factor_count"],
        "mvp_required_factor_count": decision["metrics"]["mvp_required_factor_count"],
        "diagnostic_factor_count": decision["metrics"]["diagnostic_factor_count"],
        "deferred_factor_count": decision["metrics"]["deferred_factor_count"],
        "input_release_id": decision["input_release_id"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
        "next_gate": decision["next_gate"],
    }
    for target in [release_root, CURRENT, archive_root]:
        (target / "FMDL3CA_RELEASE.json").write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf-8")

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3C-A",
        "release_id": release_id,
        "published_at": published_at,
        "status": decision["status"],
        "current_release_path": "outputs/financial_factors/contract/current/FMDL3CA_RELEASE.json",
        "release_root": str(release_root.relative_to(ROOT)),
        "next_gate": decision["next_gate"],
        "authority": decision["authority"],
        "trade_authority": "NONE",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
