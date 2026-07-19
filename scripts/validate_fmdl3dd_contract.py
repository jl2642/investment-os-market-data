from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dd_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    errors: list[str] = []
    for path in [
        cfg["entry_gates"]["valuation_contract_pointer"],
        cfg["entry_gates"]["capitalization_pointer"],
        cfg["entry_gates"]["valuation_pointer"],
        cfg["inputs"]["universe"],
        cfg["inputs"]["effective_share_ledger"],
        cfg["inputs"]["valuation_current"],
        cfg["inputs"]["event_registry"],
        "schemas/fmdl3dd_shareholder_return_event_v1.schema.json",
        "schemas/fmdl3dd_shareholder_return_current_v1.schema.json",
    ]:
        if not (ROOT / path).exists():
            errors.append(f"MISSING_INPUT:{path}")
    pointers = [
        (
            cfg["entry_gates"]["valuation_contract_pointer"],
            cfg["entry_gates"]["valuation_contract_status"],
        ),
        (
            cfg["entry_gates"]["capitalization_pointer"],
            cfg["entry_gates"]["capitalization_status"],
        ),
        (
            cfg["entry_gates"]["valuation_pointer"],
            cfg["entry_gates"]["valuation_status"],
        ),
    ]
    for path, expected in pointers:
        payload = load_json(ROOT / path)
        if payload.get("status") != expected:
            errors.append(f"ENTRY_GATE_MISMATCH:{path}")
        if payload.get("trade_authority") != "NONE":
            errors.append(f"ENTRY_TRADE_AUTHORITY_NOT_NONE:{path}")
    registry = pd.read_csv(
        ROOT / cfg["inputs"]["event_registry"], encoding="utf-8-sig"
    )
    if len(registry) != 8 or registry["event_type"].duplicated().any():
        errors.append("EVENT_REGISTRY_NOT_EXACT_8")
    if cfg["source"]["dividend_source_adapter"] != "akshare.stock_fhps_em":
        errors.append("DIVIDEND_ADAPTER_NOT_FROZEN")
    period_dates = list(cfg["source"].get("report_period_dates", []))
    if len(period_dates) != 4 or len(set(period_dates)) != 4:
        errors.append("REPORT_PERIOD_SET_NOT_EXACT_4")
    if cfg["dividend_policy"]["proposal_or_approval_counts_as_implemented"]:
        errors.append("PROPOSAL_CANNOT_COUNT_AS_IMPLEMENTED")
    if cfg["share_change_policy"][
        "unclassified_share_changes_enter_shareholder_yield"
    ]:
        errors.append("UNCLASSIFIED_SHARE_CHANGE_CANNOT_ENTER_YIELD")
    if cfg.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    for path in [
        "schemas/fmdl3dd_shareholder_return_event_v1.schema.json",
        "schemas/fmdl3dd_shareholder_return_current_v1.schema.json",
    ]:
        try:
            jsonschema.Draft202012Validator.check_schema(load_json(ROOT / path))
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{path}:{exc}")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "event_type_count": int(len(registry)),
        "report_period_count": len(period_dates),
        "shard_count": int(cfg["sharding"]["shard_count"]),
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
        "next_gate": cfg["next_gate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
