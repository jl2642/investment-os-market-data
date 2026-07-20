from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import fmdl3efinal_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3efinal_operational_closure.json"


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication"]["candidate_root"]
    decision = core.read_json(candidate / "FMDL3EFINAL_DECISION.json")
    state = core.read_json(candidate / "FMDL3EFINAL_OPERATIONAL_STATE.json")
    manifest = core.read_json(candidate / "FMDL3EFINAL_MANIFEST.json")
    current = pd.read_parquet(candidate / "FMDL3EFINAL_UNIFIED_CURRENT.parquet")

    failures: list[str] = []
    if decision.get("status") != cfg["exit_status"] or decision.get("hard_failures") != []:
        failures.append("DECISION")
    if state.get("status") != cfg["exit_status"]:
        failures.append("OPERATIONAL_STATE")
    if len(current) != cfg["acceptance"]["required_universe_symbol_count"]:
        failures.append("UNIVERSE_COUNT")
    if "symbol" not in current or current["symbol"].duplicated().any():
        failures.append("DUPLICATE_SYMBOL")
    if core.trade_authority_errors(current):
        failures.append("TRADE_AUTHORITY")
    semantic_hash = core.semantic_frame_hash(current)
    if semantic_hash != decision.get("semantic_hashes", {}).get("unified_current"):
        failures.append("SEMANTIC_HASH")

    manifest_errors = 0
    for item in manifest.get("files", []):
        path = candidate / item["path"]
        if not path.exists() or core.sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            manifest_errors += 1
    if manifest_errors:
        failures.append("MANIFEST")

    source_hash_errors = 0
    for path, expected in state.get("source_hashes", {}).items():
        source = ROOT / path
        if not source.exists() or core.sha256_file(source) != expected:
            source_hash_errors += 1
    if source_hash_errors:
        failures.append("SOURCE_HASH")

    chain = {name: core.read_json(ROOT / path) for name, path in cfg["entry_chain"].items()}
    chain_error_count = len(core.chain_errors(chain, cfg))
    if chain_error_count:
        failures.append("CANONICAL_CHAIN")

    metrics = {
        **decision.get("metrics", {}),
        "manifest_error_count": manifest_errors,
        "source_hash_error_count": source_hash_errors,
        "canonical_chain_error_count": chain_error_count,
        "independent_unified_current_hash": semantic_hash,
    }
    checks = [
        {"check_id": "DECISION", "status": "PASS" if "DECISION" not in failures else "FAIL"},
        {"check_id": "OPERATIONAL_STATE", "status": "PASS" if "OPERATIONAL_STATE" not in failures else "FAIL"},
        {"check_id": "CANONICAL_CHAIN", "status": "PASS" if "CANONICAL_CHAIN" not in failures else "FAIL"},
        {"check_id": "UNIVERSE_AND_UNIQUENESS", "status": "PASS" if not {"UNIVERSE_COUNT", "DUPLICATE_SYMBOL"}.intersection(failures) else "FAIL"},
        {"check_id": "MANIFEST", "status": "PASS" if "MANIFEST" not in failures else "FAIL"},
        {"check_id": "SOURCE_HASH", "status": "PASS" if "SOURCE_HASH" not in failures else "FAIL"},
        {"check_id": "SEMANTIC_HASH", "status": "PASS" if "SEMANTIC_HASH" not in failures else "FAIL"},
        {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if "TRADE_AUTHORITY" not in failures else "FAIL"},
    ]
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": cfg["program_id"],
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": sorted(set(failures)),
        "checks": checks,
        "metrics": metrics,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    core.write_json(candidate / "FMDL3EFINAL_VALIDATION.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
