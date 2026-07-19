from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts import fmdl3cb_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cb_engine.json"
SCHEMA = ROOT / "schemas/fmdl3cb_factor_row_v1.schema.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    schema = load_json(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    statement_pointer = load_json(ROOT / cfg["entry_gates"]["statement_current_pointer"])
    contract_pointer = load_json(ROOT / cfg["entry_gates"]["factor_contract_pointer"])
    contract = load_json(ROOT / cfg["inputs"]["factor_contract"])
    dictionary = pd.read_csv(ROOT / cfg["inputs"]["factor_dictionary"], encoding="utf-8-sig")
    declared_tokens = set(contract["formula_dsl"]["statement_tokens"]) | set(contract["formula_dsl"]["comparison_tokens"])
    errors: list[str] = []
    if statement_pointer.get("status") != cfg["entry_gates"]["statement_current_status"]:
        errors.append("STATEMENT_CURRENT_ENTRY_NOT_ACCEPTED")
    if contract_pointer.get("status") != cfg["entry_gates"]["factor_contract_status"]:
        errors.append("FACTOR_CONTRACT_ENTRY_NOT_ACCEPTED")
    if len(dictionary) != int(cfg["engine"]["expected_factor_count"]):
        errors.append("FACTOR_COUNT_MISMATCH")
    if int(dictionary["build_state"].eq("MVP_REQUIRED").sum()) != int(cfg["engine"]["expected_mvp_required_factor_count"]):
        errors.append("MVP_REQUIRED_FACTOR_COUNT_MISMATCH")
    if dictionary["factor_id"].duplicated().any() or dictionary["factor_name"].duplicated().any():
        errors.append("DUPLICATE_FACTOR_ID_OR_NAME")
    for _, factor in dictionary.iterrows():
        required = set(str(factor["required_inputs"]).split("|"))
        if not required.issubset(declared_tokens):
            errors.append(f"UNDECLARED_INPUT:{factor['factor_id']}")
        try:
            core.parse_formula(str(factor["formula"]))
        except Exception as exc:
            errors.append(f"INVALID_FORMULA:{factor['factor_id']}:{type(exc).__name__}")
    if set(dictionary["trade_authority"].astype(str)) != {"NONE"}:
        errors.append("NONZERO_TRADE_AUTHORITY")
    if cfg.get("trade_authority") != "NONE":
        errors.append("CONFIG_NONZERO_TRADE_AUTHORITY")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
