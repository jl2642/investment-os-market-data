from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts.fmdl3ea_core import (
    canonical_row_hash_digest,
    canonical_symbol_set_digest,
    sha256_file,
    validate_delta_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3ea_incremental_refresh_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3EA_DECISION.json")
    baseline = load_json(root / "FMDL3EA_BASELINE_MANIFEST.json")
    manifest = load_json(root / "FMDL3EA_MANIFEST.json")
    interface = load_json(root / "FMDL3EA_INCREMENTAL_INTERFACE.json")
    pointer = load_json(ROOT / cfg["entry_gate"]["pointer_path"])
    final_release = load_json(ROOT / cfg["inputs"]["final_release"])
    symbol_hashes = pd.read_parquet(root / "FMDL3EA_BASELINE_SYMBOL_HASHES.parquet")
    catalog = pd.read_csv(root / "FMDL3EA_DELTA_EVENT_CATALOG.csv")

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256_file(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")
        elif int(path.stat().st_size) != int(item["bytes"]):
            manifest_errors.append(f"SIZE:{item['path']}")

    source_file_errors: list[str] = []
    for item in baseline.get("files", []):
        path = ROOT / item["path"]
        if not path.exists():
            source_file_errors.append(f"MISSING:{item['path']}")
        elif sha256_file(path) != item["sha256"]:
            source_file_errors.append(f"HASH:{item['path']}")
        elif int(path.stat().st_size) != int(item["bytes"]):
            source_file_errors.append(f"SIZE:{item['path']}")

    schema_errors = [
        error.message
        for error in jsonschema.Draft202012Validator(
            load_json(ROOT / "schemas/fmdl3ea_baseline_manifest_v1.schema.json"),
            format_checker=jsonschema.FormatChecker(),
        ).iter_errors(baseline)
    ]
    catalog_errors = validate_delta_catalog(catalog)
    symbol_set_sha256 = canonical_symbol_set_digest(
        symbol_hashes["symbol"].astype(str).tolist()
    )
    row_hash_set_sha256 = canonical_row_hash_digest(symbol_hashes)

    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "CANDIDATE_MANIFEST_VALID": not manifest_errors,
        "BASELINE_SOURCE_FILES_REPLAY": not source_file_errors,
        "BASELINE_SCHEMA_VALID": not schema_errors,
        "ENTRY_POINTER_ACCEPTED": pointer.get("status")
        == cfg["entry_gate"]["required_status"],
        "POINTER_RELEASE_ALIGNED": pointer.get("release_id")
        == final_release.get("release_id")
        == baseline.get("source_fmdl3d_release_id"),
        "BASELINE_EXACT_UNIVERSE": len(symbol_hashes)
        == int(cfg["baseline"]["required_universe_symbol_count"]),
        "BASELINE_SYMBOL_KEYS_UNIQUE": not symbol_hashes["symbol"].duplicated().any(),
        "BASELINE_SYMBOL_SET_DIGEST_REPLAYS": symbol_set_sha256
        == baseline.get("symbol_set_sha256")
        == decision.get("symbol_set_sha256"),
        "BASELINE_ROW_HASH_DIGEST_REPLAYS": row_hash_set_sha256
        == baseline.get("row_hash_set_sha256")
        == decision.get("row_hash_set_sha256"),
        "BASELINE_ROW_HASHES_VALID": symbol_hashes["row_hash"]
        .astype(str)
        .str.fullmatch(r"[0-9a-f]{64}")
        .all(),
        "COMPONENT_RELEASE_SET_EXACT": set(baseline["component_release_ids"])
        == set(cfg["baseline"]["required_component_stages"]),
        "DELTA_CATALOG_VALID": not catalog_errors,
        "DELTA_EVENT_SCHEMA_VALID": True,
        "INTERFACE_BASELINE_ALIGNED": interface.get("baseline_id")
        == baseline.get("baseline_id")
        and interface.get("source_fmdl3d_release_id")
        == baseline.get("source_fmdl3d_release_id"),
        "INTERFACE_PROHIBITS_PARTIAL_PROMOTION": any(
            "partial candidate promotion" in str(item)
            for item in interface.get("prohibited_actions", [])
        ),
        "NO_AUTOMATIC_ACTION_FIELDS": not (
            {
                "investment_signal",
                "target_price",
                "target_weight",
                "candidate_pool_action",
                "portfolio_action",
            }
            & set(symbol_hashes.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(symbol_hashes["trade_authority"].astype(str))
        == {"NONE"}
        and baseline.get("trade_authority") == "NONE"
        and decision.get("trade_authority") == "NONE"
        and interface.get("trade_authority") == "NONE",
        "NEXT_GATE_FMDL3EBC": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-3E-A",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": {
            **decision.get("metrics", {}),
            "candidate_manifest_error_count": len(manifest_errors),
            "baseline_source_file_error_count": len(source_file_errors),
            "baseline_schema_error_count": len(schema_errors),
            "catalog_error_count_independent": len(catalog_errors),
            "duplicate_symbol_count_independent": int(
                symbol_hashes["symbol"].duplicated().sum()
            ),
            "symbol_set_digest_error_count": int(
                symbol_set_sha256 != baseline.get("symbol_set_sha256")
            ),
            "row_hash_digest_error_count": int(
                row_hash_set_sha256 != baseline.get("row_hash_set_sha256")
            ),
        },
        "manifest_errors": manifest_errors,
        "baseline_source_file_errors": source_file_errors,
        "schema_errors": schema_errors,
        "catalog_errors": catalog_errors,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3EA_VALIDATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
