from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from scripts.fmdl3ea_core import (
    baseline_watermarks,
    build_file_inventory,
    canonical_row_hash_digest,
    canonical_symbol_set_digest,
    promotion_policy_is_fail_closed,
    rollback_policy_preserves_last_good,
    sha256_file,
    stable_hash,
    validate_delta_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl3ea_incremental_refresh_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def candidate_manifest(root: Path, release_id: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FMDL3EA_MANIFEST.json":
            files.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256_file(path),
                    "bytes": int(path.stat().st_size),
                }
            )
    return {
        "manifest_version": "1.0.0",
        "release_id": release_id,
        "files": files,
        "authority": "DATA_AND_RESEARCH_EVIDENCE_ONLY",
        "trade_authority": "NONE",
    }


def main() -> int:
    cfg = load_json(CONFIG)
    pointer = load_json(ROOT / cfg["entry_gate"]["pointer_path"])
    final_release = load_json(ROOT / cfg["inputs"]["final_release"])
    final_decision = load_json(ROOT / cfg["inputs"]["final_decision"])
    final_validation = load_json(ROOT / cfg["inputs"]["final_validation"])
    interface = load_json(ROOT / cfg["inputs"]["unified_interface"])
    release_index = load_json(ROOT / cfg["inputs"]["unified_release_index"])
    component_matrix = pd.read_csv(
        ROOT / cfg["inputs"]["component_release_matrix"], encoding="utf-8-sig"
    )
    unified = pd.read_parquet(ROOT / cfg["inputs"]["unified_current"])
    catalog = pd.read_csv(ROOT / cfg["inputs"]["delta_event_catalog"])

    candidate = ROOT / cfg["publication"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = f"FMDL3EA_{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}"
    component_release_ids = {
        str(key): str(value)
        for key, value in final_decision["component_release_ids"].items()
    }

    symbol_hashes = unified[
        [
            "symbol",
            "market_as_of_date",
            "row_hash",
            "component_release_ids_json",
            "authority",
            "trade_authority",
        ]
    ].copy()
    symbol_hashes["symbol"] = symbol_hashes["symbol"].astype(str)
    symbol_hashes = symbol_hashes.sort_values("symbol").reset_index(drop=True)
    symbol_set_sha256 = canonical_symbol_set_digest(symbol_hashes["symbol"].tolist())
    row_hash_set_sha256 = canonical_row_hash_digest(symbol_hashes)
    baseline_id = stable_hash(
        {
            "label": cfg["baseline"]["baseline_label"],
            "source_fmdl3d_release_id": final_release["release_id"],
            "market_as_of_date": interface["market_as_of_date"],
            "symbol_set_sha256": symbol_set_sha256,
            "row_hash_set_sha256": row_hash_set_sha256,
            "component_release_ids": component_release_ids,
        }
    )

    source_inventory = build_file_inventory(
        ROOT, list(cfg["baseline"]["required_source_files"])
    )
    baseline = {
        "baseline_version": "1.0.0",
        "baseline_id": baseline_id,
        "baseline_label": cfg["baseline"]["baseline_label"],
        "generated_at": generated_at,
        "status": "FROZEN_ACCEPTED_BASELINE",
        "source_fmdl3d_release_id": final_release["release_id"],
        "source_fmdl3d_published_at": final_release["published_at"],
        "market_as_of_date": interface["market_as_of_date"],
        "universe_symbol_count": int(len(symbol_hashes)),
        "symbol_set_sha256": symbol_set_sha256,
        "row_hash_set_sha256": row_hash_set_sha256,
        "component_release_ids": component_release_ids,
        "watermarks": baseline_watermarks(
            final_release,
            interface,
            component_release_ids,
            symbol_set_sha256,
        ),
        "files": source_inventory,
        "promotion_policy_sha256": stable_hash(cfg["promotion_policy"]),
        "rollback_policy_sha256": stable_hash(cfg["rollback_policy"]),
        "idempotence_policy_sha256": stable_hash(cfg["idempotence_policy"]),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }

    symbol_hashes.to_parquet(
        candidate / "FMDL3EA_BASELINE_SYMBOL_HASHES.parquet",
        index=False,
        compression="zstd",
    )
    catalog.to_csv(
        candidate / "FMDL3EA_DELTA_EVENT_CATALOG.csv",
        index=False,
        encoding="utf-8-sig",
    )
    write_json(candidate / "FMDL3EA_BASELINE_MANIFEST.json", baseline)
    write_json(candidate / "FMDL3EA_CONTRACT_SNAPSHOT.json", cfg)
    write_json(candidate / "FMDL3EA_SOURCE_FMDL3D_POINTER.json", pointer)
    write_json(candidate / "FMDL3EA_SOURCE_FMDL3D_RELEASE.json", final_release)
    write_json(candidate / "FMDL3EA_SOURCE_RELEASE_INDEX.json", release_index)

    incremental_interface = {
        "interface_version": "1.0.0",
        "interface_id": "FMDL3E_INCREMENTAL_REFRESH_BASELINE_INTERFACE",
        "status": "ACTIVE_CONTRACT_ONLY",
        "baseline_id": baseline_id,
        "source_fmdl3d_release_id": final_release["release_id"],
        "market_as_of_date": interface["market_as_of_date"],
        "datasets": [
            {
                "dataset_id": "baseline_manifest",
                "path": f"{cfg['publication']['current_root']}/FMDL3EA_BASELINE_MANIFEST.json",
                "purpose": "Frozen source hashes, release bindings and watermarks",
            },
            {
                "dataset_id": "baseline_symbol_hashes",
                "path": f"{cfg['publication']['current_root']}/FMDL3EA_BASELINE_SYMBOL_HASHES.parquet",
                "purpose": "Per-symbol semantic baseline for incremental diff and unchanged-row proof",
            },
            {
                "dataset_id": "delta_event_catalog",
                "path": f"{cfg['publication']['current_root']}/FMDL3EA_DELTA_EVENT_CATALOG.csv",
                "purpose": "Allowed incremental event taxonomy and affected-scope routing",
            },
        ],
        "required_runtime_sequence": [
            "detect source delta",
            "validate event against delta-event schema and catalog",
            "derive explicit affected symbols and periods",
            "choose incremental or full rebuild from frozen policy",
            "build isolated candidate",
            "independently validate and replay",
            "publish immutable release and current atomically",
            "update last-success only after successful publication",
        ],
        "prohibited_actions": [
            "silent full-universe rewrite under an incremental label",
            "partial candidate promotion",
            "overwriting Current or Last-success after a failed run",
            "mutating immutable Release or Archive",
            "automatic candidate-pool, simulation, real-account or portfolio action",
            "automatic brokerage execution",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    write_json(candidate / "FMDL3EA_INCREMENTAL_INTERFACE.json", incremental_interface)

    catalog_errors = validate_delta_catalog(catalog)
    expected_components = set(cfg["baseline"]["required_component_stages"])
    actual_components = set(component_release_ids)
    source_inventory_unique = len(source_inventory) == len(
        {row["path"] for row in source_inventory}
    )
    checks = {
        "ENTRY_POINTER_ACCEPTED": pointer.get("status")
        == cfg["entry_gate"]["required_status"],
        "ENTRY_NEXT_GATE_ALIGNED": pointer.get("next_gate")
        == cfg["entry_gate"]["required_next_gate"],
        "POINTER_RELEASE_ALIGNED": pointer.get("release_id")
        == final_release.get("release_id"),
        "FINAL_RELEASE_ACCEPTED": final_release.get("status")
        == cfg["entry_gate"]["required_status"],
        "FINAL_DECISION_ACCEPTED": final_decision.get("status")
        == cfg["entry_gate"]["required_status"]
        and final_decision.get("hard_failures") == [],
        "FINAL_VALIDATION_PASS": final_validation.get("status") == "PASS"
        and final_validation.get("hard_failures") == [],
        "EXACT_COMPONENT_STAGE_SET": actual_components == expected_components,
        "RELEASE_INDEX_COMPONENTS_ALIGNED": set(release_index["components"])
        == expected_components,
        "COMPONENT_MATRIX_EXACT": set(component_matrix["stage"].astype(str))
        == expected_components,
        "EXACT_BASELINE_UNIVERSE": len(symbol_hashes)
        == int(cfg["baseline"]["required_universe_symbol_count"]),
        "BASELINE_SYMBOL_KEYS_UNIQUE": not symbol_hashes["symbol"].duplicated().any(),
        "BASELINE_ROW_HASHES_PRESENT": symbol_hashes["row_hash"].notna().all()
        and symbol_hashes["row_hash"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all(),
        "SOURCE_FILE_INVENTORY_COMPLETE": len(source_inventory)
        == len(cfg["baseline"]["required_source_files"])
        and source_inventory_unique,
        "DELTA_CATALOG_VALID": catalog_errors == [],
        "PROMOTION_POLICY_FAIL_CLOSED": promotion_policy_is_fail_closed(
            cfg["promotion_policy"]
        ),
        "ROLLBACK_POLICY_PRESERVES_LAST_GOOD": rollback_policy_preserves_last_good(
            cfg["rollback_policy"]
        ),
        "FULL_REBUILD_TRIGGERS_PRESENT": len(cfg["full_rebuild_triggers"]) >= 8,
        "NO_AUTOMATIC_ACTION_AUTHORITY": not any(
            bool(cfg["authority_boundary"].get(key))
            for key in [
                "candidate_pool_mutation_authorized",
                "simulation_mutation_authorized",
                "real_account_mutation_authorized",
                "portfolio_action_authorized",
                "order_execution_authorized",
            ]
        ),
        "ZERO_TRADE_AUTHORITY": pointer.get("trade_authority") == "NONE"
        and final_release.get("trade_authority") == "NONE"
        and set(symbol_hashes["trade_authority"].astype(str)) == {"NONE"}
        and cfg["trade_authority"] == "NONE",
    }
    failures = [name for name, passed in checks.items() if not bool(passed)]
    metrics = {
        "source_fmdl3d_release_id": final_release["release_id"],
        "market_as_of_date": interface["market_as_of_date"],
        "baseline_symbol_count": int(len(symbol_hashes)),
        "baseline_component_count": int(len(component_release_ids)),
        "baseline_source_file_count": int(len(source_inventory)),
        "baseline_source_bytes": int(sum(row["bytes"] for row in source_inventory)),
        "delta_event_type_count": int(len(catalog)),
        "incremental_allowed_event_type_count": int(
            catalog["incremental_allowed"].astype(str).str.lower().eq("true").sum()
        ),
        "full_rebuild_event_type_count": int(
            catalog["full_rebuild_trigger"].astype(str).str.lower().eq("true").sum()
        ),
        "duplicate_baseline_symbol_count": int(
            symbol_hashes["symbol"].duplicated().sum()
        ),
        "missing_baseline_row_hash_count": int(symbol_hashes["row_hash"].isna().sum()),
        "catalog_error_count": int(len(catalog_errors)),
        "automatic_action_authorized_count": 0,
    }
    decision = {
        "decision_version": "1.0.0",
        "release_id": release_id,
        "generated_at": generated_at,
        "program_id": "FMDL-3E-A",
        "status": cfg["exit_status"] if not failures else "FMDL3EA_REMEDIATION_REQUIRED",
        "hard_failures": failures,
        "checks": [
            {"check_id": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "metrics": metrics,
        "baseline_id": baseline_id,
        "symbol_set_sha256": symbol_set_sha256,
        "row_hash_set_sha256": row_hash_set_sha256,
        "component_release_ids": component_release_ids,
        "controlled_limitations": [
            "CONTRACT_AND_BASELINE_ONLY_NO_NEW_MARKET_OR_FINANCIAL_REFRESH_IN_3E_A",
            "INCREMENTAL_THRESHOLDS_REQUIRE_REAL_RUN_VALIDATION_IN_3E_BC",
            "FAILURE_RECOVERY_IDEMPOTENCE_AND_ROLLBACK_REQUIRE_FAULT_INJECTION_IN_3E_DE",
            "NO_INVESTMENT_SCORE_TARGET_PRICE_PORTFOLIO_ACTION_OR_TRADE_PERMISSION",
        ],
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    write_json(candidate / "FMDL3EA_DECISION.json", decision)
    write_json(candidate / "FMDL3EA_MANIFEST.json", candidate_manifest(candidate, release_id))
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
