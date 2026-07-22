#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "outputs" / "fmdl6x1b" / "current"
RELEASE = ROOT / "datasets" / "fmdl6x1b" / "releases" / "FMDL6X1B_20260722_8caf155efd67"
POINTER = ROOT / "outputs" / "status" / "FMDL6X1B_LAST_SUCCESS.json"
CONFIG = ROOT / "config" / "fmdl6x1b_anticipated_research_universe_contract.json"
FILES = ["FMDL6X1B_CONTRACT.json", "FMDL6X1B_DECISION.json", "FMDL6X1B_MANIFEST.json"]
STATUS = "FMDL6X1B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY_ACCEPTED"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> list[str]:
    errors: list[str] = []
    if not POINTER.exists():
        return ["missing_pointer"]
    pointer = json.loads(POINTER.read_text(encoding="utf-8"))
    if pointer.get("release_id") != "FMDL6X1B_20260722_8caf155efd67":
        errors.append("pointer_release")
    if pointer.get("status") != STATUS:
        errors.append("pointer_status")
    if pointer.get("trade_authority") != "NONE":
        errors.append("pointer_trade_authority")
    for name in FILES:
        current = CURRENT / name
        release = RELEASE / name
        if not current.exists() or not release.exists():
            errors.append(f"missing_{name}")
            continue
        if current.read_bytes() != release.read_bytes():
            errors.append(f"parity_{name}")
    contract = json.loads((CURRENT / "FMDL6X1B_CONTRACT.json").read_text(encoding="utf-8"))
    if contract.get("status") != "ACCEPTED":
        errors.append("contract_status")
    if contract.get("trade_authority") != "NONE":
        errors.append("contract_trade_authority")
    if CONFIG.read_bytes() != (CURRENT / "FMDL6X1B_CONTRACT.json").read_bytes():
        errors.append("config_current_parity")
    if pointer.get("contract_sha256") != sha(CURRENT / "FMDL6X1B_CONTRACT.json"):
        errors.append("contract_hash")
    if pointer.get("manifest_sha256") != sha(CURRENT / "FMDL6X1B_MANIFEST.json"):
        errors.append("manifest_hash")
    decision = json.loads((CURRENT / "FMDL6X1B_DECISION.json").read_text(encoding="utf-8"))
    if decision.get("next_gate") != "FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION":
        errors.append("next_gate")
    for key in ["live_security_rows_created", "candidate_pool_mutations", "simulation_mutations", "real_account_mutations", "orders"]:
        if decision.get(key) != 0:
            errors.append(f"zero_{key}")
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
