from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dc_engine.json"
TZ = ZoneInfo("Asia/Shanghai")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def main() -> int:
    cfg = load_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(candidate / "FMDL3DC_DECISION.json")
    validation = load_json(candidate / "FMDL3DC_VALIDATION.json")
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures"):
        raise SystemExit("candidate decision not accepted")
    if validation.get("status") != "PASS" or validation.get("hard_failures"):
        raise SystemExit("candidate independent validation not accepted")

    release_id = str(decision["release_id"])
    release_root = ROOT / cfg["publication"]["release_root"] / release_id
    archive_root = ROOT / cfg["publication"]["archive_root"] / release_id
    current_root = ROOT / cfg["publication"]["current_root"]
    if release_root.exists() or archive_root.exists():
        raise SystemExit(f"immutable release already exists: {release_id}")

    shutil.copytree(candidate, release_root)
    shutil.copytree(candidate, archive_root)
    shutil.rmtree(current_root, ignore_errors=True)
    shutil.copytree(candidate, current_root)

    published_at = datetime.now(TZ).isoformat(timespec="seconds")
    release = {
        "release_version": "1.0.0",
        "release_id": release_id,
        "published_at": published_at,
        "program_id": "FMDL-3D-C",
        "status": cfg["exit_status"],
        "exit_gate": "VALUATION_ENGINE_CURRENT_ACCEPTED",
        "release_root": str(release_root.relative_to(ROOT)),
        "current_root": str(current_root.relative_to(ROOT)),
        "archive_path": str(archive_root.relative_to(ROOT)),
        "valuation_current_path": str(
            (current_root / "FMDL3DC_VALUATION_CURRENT.parquet").relative_to(ROOT)
        ),
        "valuation_metric_detail_path": str(
            (current_root / "FMDL3DC_VALUATION_METRIC_DETAIL.parquet").relative_to(ROOT)
        ),
        "coverage_path": str(
            (current_root / "FMDL3DC_COVERAGE.csv").relative_to(ROOT)
        ),
        "denominator_validity_path": str(
            (current_root / "FMDL3DC_DENOMINATOR_VALIDITY.csv").relative_to(ROOT)
        ),
        "quarantine_path": str(
            (current_root / "FMDL3DC_QUARANTINE.csv").relative_to(ROOT)
        ),
        "metric_registry_path": str(
            (current_root / "FMDL3DC_METRIC_REGISTRY.csv").relative_to(ROOT)
        ),
        "decision_path": str(
            (current_root / "FMDL3DC_DECISION.json").relative_to(ROOT)
        ),
        "validation_path": str(
            (current_root / "FMDL3DC_VALIDATION.json").relative_to(ROOT)
        ),
        "source_releases": {
            "valuation_contract_release_id": decision["metrics"]["valuation_contract_release_id"],
            "capitalization_release_id": decision["metrics"]["capitalization_release_id"],
            "factor_engine_release_id": decision["metrics"]["factor_engine_release_id"],
            "market_source_release_id": decision["metrics"]["market_source_release_id"],
            "market_as_of_date": decision["metrics"]["market_as_of_date"],
        },
        "metrics": validation["metrics"],
        "controlled_limitations": decision["controlled_limitations"],
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
        "next_gate": cfg["next_gate"],
    }
    for root in [release_root, archive_root, current_root]:
        write_json(root / "FMDL3DC_RELEASE.json", release)

    pointer = {
        "pointer_version": "1.0.0",
        "program_id": "FMDL-3D-C",
        "release_id": release_id,
        "published_at": published_at,
        "status": cfg["exit_status"],
        "current_release_path": str(
            (current_root / "FMDL3DC_RELEASE.json").relative_to(ROOT)
        ),
        "release_root": str(release_root.relative_to(ROOT)),
        "market_source_release_id": decision["metrics"]["market_source_release_id"],
        "market_as_of_date": decision["metrics"]["market_as_of_date"],
        "next_gate": cfg["next_gate"],
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
    }
    write_json(ROOT / cfg["publication"]["last_success"], pointer)
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
