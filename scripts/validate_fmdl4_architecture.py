from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from scripts import fmdl4_architecture_core as core

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/fmdl4_program_contract.json"
SCHEMA = ROOT / "schemas/fmdl4_program_contract.schema.json"
DOCS = [ROOT / "docs/FMDL-4_ARCHITECTURE.md", ROOT / "docs/FMDL-4_PHASED_PLAN.md"]


def main() -> int:
    started = time.perf_counter()
    cfg = core.read_json(CONFIG)
    schema = core.read_json(SCHEMA)
    errors = [f"SCHEMA:{error.message}" for error in Draft202012Validator(schema).iter_errors(cfg)]
    errors.extend(core.validate_contract_shape(cfg))
    bound_errors, bindings = core.validate_bound_state(ROOT, cfg)
    errors.extend(bound_errors)
    for path in DOCS:
        if not path.exists():
            errors.append(f"MISSING_DOC:{path.name}")

    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    release_id = "FMDL4_ARCH_" + datetime.now(TZ).strftime("%Y%m%dT%H%M%S%z")
    status = cfg["exit_status"] if not errors else "FMDL4_ARCHITECTURE_REJECTED"
    candidate = ROOT / cfg["publication_contract"]["candidate_root"]
    if candidate.exists():
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True, exist_ok=True)

    source_files = [CONFIG, SCHEMA, *DOCS]
    source_hashes = {str(path.relative_to(ROOT)): core.sha256_file(path) for path in source_files}
    decision = {
        "decision_version": "1.0.0",
        "program_id": "FMDL-4",
        "release_id": release_id,
        "generated_at": generated_at,
        "status": status,
        "hard_failures": sorted(set(errors)),
        "architecture_state": cfg["architecture_state"],
        "bindings": bindings,
        "metrics": {
            "phase_count": len(cfg["phase_sequence"]),
            "canonical_object_count": len(cfg["canonical_objects"]),
            "public_equity_workflow_count": len(cfg["public_equity_workflow_map"]),
            "global_hard_gate_count": len(cfg["global_hard_gates"]),
            "bound_input_count": len(cfg["bound_inputs"]),
            "external_investment_os_release_sequence": cfg["external_investment_os_baseline"]["release_sequence"],
            "controlled_limitation_count": len(cfg["controlled_limitations"]),
            "elapsed_seconds": round(time.perf_counter() - started, 4)
        },
        "contract_semantic_hash": core.stable_hash(cfg),
        "source_hashes": source_hashes,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }
    validation = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-4",
        "release_id": release_id,
        "status": "PASS" if not errors else "FAIL",
        "hard_failures": sorted(set(errors)),
        "checks": [
            {"check_id": "PROGRAM_SCHEMA", "status": "PASS" if not any(error.startswith("SCHEMA:") for error in errors) else "FAIL"},
            {"check_id": "PHASE_AND_GATE_CHAIN", "status": "PASS" if not any(error in errors for error in ["PHASE_SEQUENCE", "PHASE_GATE_CHAIN"]) else "FAIL"},
            {"check_id": "LAYER_AND_ROLE_SEPARATION", "status": "PASS" if not any(error in errors for error in ["LAYER_MODEL", "STATE_MUTATION_OWNERSHIP", "REAL_ACCOUNT_GATE_CHAIN"]) else "FAIL"},
            {"check_id": "INVESTMENT_OS_PACKAGE_MAPPING", "status": "PASS" if not any(error in errors for error in ["PACKAGE_MAPPING", "STORAGE_POLICY", "EXTERNAL_BASELINE_STATUS", "EXTERNAL_BASELINE_SEQUENCE", "EXTERNAL_BASELINE_SHA", "PROJECT_SOURCES_REQUIRED"]) else "FAIL"},
            {"check_id": "BOUND_FMDL_INPUTS", "status": "PASS" if not bound_errors else "FAIL"},
            {"check_id": "AUTHORITY_FIREWALL", "status": "PASS" if not any("TRADE_AUTHORITY" in error or error == "GLOBAL_HARD_GATES" for error in errors) else "FAIL"},
            {"check_id": "DOCUMENTATION", "status": "PASS" if not any(error.startswith("MISSING_DOC:") for error in errors) else "FAIL"}
        ],
        "contract_semantic_hash": decision["contract_semantic_hash"],
        "bindings": bindings,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"]
    }

    core.write_json(candidate / "FMDL4_ARCHITECTURE_CONTRACT.json", cfg)
    core.write_json(candidate / "FMDL4_ARCHITECTURE_DECISION.json", decision)
    core.write_json(candidate / "FMDL4_ARCHITECTURE_VALIDATION.json", validation)
    manifest = core.manifest(ROOT, source_files)
    manifest.update({"release_id": release_id, "candidate_status": status, "contract_semantic_hash": decision["contract_semantic_hash"]})
    core.write_json(candidate / "FMDL4_ARCHITECTURE_MANIFEST.json", manifest)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
