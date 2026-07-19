from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3d_final_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    errors: list[str] = []
    for key, gate in cfg["entry_gates"].items():
        path = ROOT / gate["path"]
        if not path.exists():
            errors.append(f"MISSING_ENTRY_POINTER:{key}:{gate['path']}")
            continue
        payload = load_json(path)
        if payload.get("status") != gate["required_status"]:
            errors.append(f"ENTRY_STATUS_MISMATCH:{key}")
        if payload.get("trade_authority") != "NONE":
            errors.append(f"ENTRY_TRADE_AUTHORITY_NOT_NONE:{key}")
    for key, relative in cfg["inputs"].items():
        if not (ROOT / relative).exists():
            errors.append(f"MISSING_INPUT:{key}:{relative}")
    for relative in [
        "schemas/fmdl3d_unified_current_v1.schema.json",
        "schemas/fmdl3d_unified_interface_v1.schema.json",
    ]:
        try:
            jsonschema.Draft202012Validator.check_schema(load_json(ROOT / relative))
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{relative}:{exc}")
    boundary = cfg["authority_boundary"]
    false_fields = [
        "valuation_score_authorized",
        "target_price_authorized",
        "candidate_pool_mutation_authorized",
        "simulation_mutation_authorized",
        "real_account_mutation_authorized",
        "portfolio_action_authorized",
        "order_execution_authorized",
    ]
    if any(bool(boundary.get(field)) for field in false_fields):
        errors.append("UNCONTROLLED_ACTION_AUTHORITY")
    if cfg.get("authority") != "DATA_AND_RESEARCH_EVIDENCE_ONLY":
        errors.append("AUTHORITY_NOT_RESEARCH_EVIDENCE_ONLY")
    if cfg.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    if cfg.get("next_gate") != "FMDL-3E_INCREMENTAL_REFRESH_REPLAY_AND_FINAL_ACCEPTANCE":
        errors.append("NEXT_GATE_NOT_FMDL3E")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "entry_gate_count": len(cfg["entry_gates"]),
        "input_count": len(cfg["inputs"]),
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
        "next_gate": cfg["next_gate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
