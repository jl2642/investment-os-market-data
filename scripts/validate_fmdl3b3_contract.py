from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/fmdl3b3_comparability.json"
SCHEMA = ROOT / "schemas/fmdl3b3_comparability_v1.schema.json"


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda item: list(item.path))
    if errors:
        for error in errors:
            print(f"{list(error.path)}: {error.message}")
        return 1
    print("FMDL-3B-3 contract validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
