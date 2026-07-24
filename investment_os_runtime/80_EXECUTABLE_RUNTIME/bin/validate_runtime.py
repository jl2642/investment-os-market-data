from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "80_EXECUTABLE_RUNTIME" / "src"
sys.path.insert(0, str(RUNTIME_SRC))

from investment_os_control.core import canonical_hash, read_json, validate_runtime

result = validate_runtime(ROOT, "2026-07-24")
if result["status"] != "PASS":
    raise SystemExit(json.dumps(result, indent=2))

state_manifest = read_json(ROOT / "30_STATE_CURRENT" / "00_STATE_MANIFEST.json")
state_hash = canonical_hash(state_manifest)

acceptance = {
    "acceptance_id": "WP1_5C_RUNTIME_ACCEPTANCE_20260724",
    "runtime_version": "1.0.0",
    "status": "PASS",
    "evaluation_date": "2026-07-24",
    "binding_count": 6,
    "cadence_contract_count": 6,
    "event_level_count": 6,
    "product_contract_count": 6,
    "attribution_contract_count": 4,
    "runtime_validation": result,
    "state_manifest_canonical_hash": state_hash,
    "automation_activation": "DISABLED_UNTIL_WP6",
    "candidate_membership_mutations": 0,
    "simulation_mutations": 0,
    "real_account_mutations": 0,
    "automatic_rule_mutations": 0,
    "orders": 0,
    "trade_authority": "NONE",
}
path = ROOT / "80_EXECUTABLE_RUNTIME" / "RUNTIME_ACCEPTANCE.json"
path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(acceptance, ensure_ascii=False, indent=2))
