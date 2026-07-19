from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3cc_hardening.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3CC_DECISION.json")
    validation = load_json(candidate / "FMDL3CC_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get(
        "hard_failures"
    ) != []:
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
        "FMDL3CC_HARDENED_FACTOR_CURRENT.parquet",
        "FMDL3CC_FACTOR_REGISTRY.csv",
        "FMDL3CC_DISTRIBUTION_DIAGNOSTICS.csv",
        "FMDL3CC_TAIL_EVENTS.parquet",
        "FMDL3CC_PROFILE_RECONCILIATION.csv",
        "FMDL3CC_DECISION.json",
        "FMDL3CC_VALIDATION.json",
        "FMDL3CC_MANIFEST.json",
        "FMDL3CC_SOURCE_POINTER.json",
        "FMDL3CC_SOURCE_RELEASE.json",
    ]
    for name in compact_files:
        copy_file(candidate / name, current_root / name)
        copy_file(candidate / name, archive_root / name)

    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "program_id": "FMDL-3C-C",
        "status": cfg["exit_status"],
        "exit_gate": "FINANCIAL_FACTOR_VALIDATION_AND_HARDENING_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "source_factor_engine_release_id": decision["metrics"][
            "source_factor_engine_release_id"
        ],
        "hardened_factor_current_path": str(
            (current_root / "FMDL3CC_HARDENED_FACTOR_CURRENT.parquet").relative_to(
                ROOT
            )
        ),
        "factor_registry_path": str(
            (current_root / "FMDL3CC_FACTOR_REGISTRY.csv").relative_to(ROOT)
        ),
        "distribution_diagnostics_path": str(
            (
                current_root / "FMDL3CC_DISTRIBUTION_DIAGNOSTICS.csv"
            ).relative_to(ROOT)
        ),
        "tail_events_path": str(
            (current_root / "FMDL3CC_TAIL_EVENTS.parquet").relative_to(ROOT)
        ),
        "profile_reconciliation_path": str(
            (current_root / "FMDL3CC_PROFILE_RECONCILIATION.csv").relative_to(ROOT)
        ),
        "decision_path": str(
            (current_root / "FMDL3CC_DECISION.json").relative_to(ROOT)
        ),
        "validation_path": str(
            (current_root / "FMDL3CC_VALIDATION.json").relative_to(ROOT)
        ),
        "metrics": decision["metrics"],
        "controlled_limitations": decision.get("controlled_limitations", []),
        "industry_neutral_scoring_authorized": False,
        "financial_sector_factor_pack_authorized": False,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(release_root / "FMDL3CC_RELEASE.json", release)
    write_json(current_root / "FMDL3CC_RELEASE.json", release)
    write_json(archive_root / "FMDL3CC_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3C-C",
        "release_id": release_id,
        "published_at": release["published_at"],
        "status": cfg["exit_status"],
        "current_release_path": str(
            (current_root / "FMDL3CC_RELEASE.json").relative_to(ROOT)
        ),
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
