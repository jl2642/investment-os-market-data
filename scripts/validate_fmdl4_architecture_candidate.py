from __future__ import annotations

import json
from pathlib import Path

from scripts import fmdl4_architecture_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl4_program_contract.json"


def main() -> int:
    cfg = core.read_json(CONFIG)
    candidate = ROOT / cfg["publication_contract"]["candidate_root"]
    contract = core.read_json(candidate / "FMDL4_ARCHITECTURE_CONTRACT.json")
    decision = core.read_json(candidate / "FMDL4_ARCHITECTURE_DECISION.json")
    validation = core.read_json(candidate / "FMDL4_ARCHITECTURE_VALIDATION.json")
    manifest = core.read_json(candidate / "FMDL4_ARCHITECTURE_MANIFEST.json")

    errors: list[str] = []
    if contract != cfg:
        errors.append("CANDIDATE_CONTRACT_DIFFERS_FROM_SOURCE")
    errors.extend(core.validate_contract_shape(contract))
    bound_errors, bindings = core.validate_bound_state(ROOT, contract)
    errors.extend(bound_errors)
    if decision.get("status") != contract["exit_status"] or decision.get("hard_failures") != []:
        errors.append("DECISION_NOT_ACCEPTED")
    if validation.get("status") != "PASS" or validation.get("hard_failures") != []:
        errors.append("VALIDATION_NOT_PASS")
    if decision.get("release_id") != validation.get("release_id") or decision.get("release_id") != manifest.get("release_id"):
        errors.append("RELEASE_ID_MISMATCH")
    semantic_hash = core.stable_hash(contract)
    if semantic_hash != decision.get("contract_semantic_hash") or semantic_hash != validation.get("contract_semantic_hash") or semantic_hash != manifest.get("contract_semantic_hash"):
        errors.append("CONTRACT_SEMANTIC_HASH_MISMATCH")
    if decision.get("bindings") != bindings or validation.get("bindings") != bindings:
        errors.append("BOUND_RELEASE_REPLAY_MISMATCH")
    for item in manifest.get("files", []):
        path = ROOT / item["path"]
        if not path.exists():
            errors.append(f"MANIFEST_FILE_MISSING:{item['path']}")
        elif core.sha256_file(path) != item.get("sha256"):
            errors.append(f"MANIFEST_HASH_MISMATCH:{item['path']}")
    if decision.get("trade_authority") != "NONE" or validation.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY")

    independent = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-4",
        "release_id": decision.get("release_id"),
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": sorted(set(errors)),
        "checks": [
            {"check_id": "SOURCE_CONTRACT_IDENTITY", "status": "PASS" if "CANDIDATE_CONTRACT_DIFFERS_FROM_SOURCE" not in errors else "FAIL"},
            {"check_id": "BOUND_RELEASE_REPLAY", "status": "PASS" if not bound_errors and "BOUND_RELEASE_REPLAY_MISMATCH" not in errors else "FAIL"},
            {"check_id": "SEMANTIC_HASH", "status": "PASS" if "CONTRACT_SEMANTIC_HASH_MISMATCH" not in errors else "FAIL"},
            {"check_id": "MANIFEST", "status": "PASS" if not any(error.startswith("MANIFEST_") for error in errors) else "FAIL"},
            {"check_id": "ZERO_TRADE_AUTHORITY", "status": "PASS" if "TRADE_AUTHORITY" not in errors else "FAIL"}
        ],
        "contract_semantic_hash": semantic_hash,
        "bindings": bindings,
        "authority": contract["authority"],
        "trade_authority": "NONE",
        "next_gate": contract["next_gate"]
    }
    core.write_json(candidate / "FMDL4_ARCHITECTURE_INDEPENDENT_VALIDATION.json", independent)
    print(json.dumps(independent, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
