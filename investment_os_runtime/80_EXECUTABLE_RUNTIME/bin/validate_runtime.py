from __future__ import annotations

from datetime import date
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "80_EXECUTABLE_RUNTIME" / "src"
if RUNTIME_SRC.exists():
    sys.path.insert(0, str(RUNTIME_SRC))
else:
    sys.path.insert(0, str(ROOT / "src"))

from investment_os_control.core import canonical_hash, read_json, validate_runtime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Investment OS Control Runtime."
    )
    parser.add_argument(
        "--evaluation-date",
        default=date.today().isoformat(),
        help="ISO date used for freshness checks; defaults to the runtime date.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "80_EXECUTABLE_RUNTIME" / "RUNTIME_ACCEPTANCE.json"),
        help="Acceptance JSON output path.",
    )
    args = parser.parse_args()

    result = validate_runtime(ROOT, args.evaluation_date)
    if result["status"] != "PASS":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    state_manifest = read_json(ROOT / "30_STATE_CURRENT" / "00_STATE_MANIFEST.json")
    acceptance = {
        "acceptance_id": "WP1_5E_RUNTIME_ACCEPTANCE_V1_0_1",
        "runtime_version": "1.0.1",
        "status": "PASS",
        "evaluation_date": args.evaluation_date,
        "binding_count": 6,
        "cadence_contract_count": 6,
        "event_level_count": 6,
        "product_contract_count": 6,
        "attribution_contract_count": 4,
        "runtime_validation": result,
        "state_manifest_canonical_hash": canonical_hash(state_manifest),
        "automation_activation": "DISABLED_UNTIL_WP6",
        "candidate_membership_mutations": 0,
        "simulation_mutations": 0,
        "real_account_mutations": 0,
        "automatic_rule_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(acceptance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
