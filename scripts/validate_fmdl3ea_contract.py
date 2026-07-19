from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts.fmdl3ea_core import (
    promotion_policy_is_fail_closed,
    rollback_policy_preserves_last_good,
    validate_delta_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3ea_incremental_refresh_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    catalog = pd.read_csv(ROOT / cfg["inputs"]["delta_event_catalog"])
    errors: list[str] = []

    required_paths = [
        cfg["entry_gate"]["pointer_path"],
        cfg["inputs"]["final_release"],
        cfg["inputs"]["final_decision"],
        cfg["inputs"]["final_validation"],
        cfg["inputs"]["unified_current"],
        cfg["inputs"]["unified_interface"],
        cfg["inputs"]["unified_release_index"],
        cfg["inputs"]["component_release_matrix"],
        cfg["inputs"]["component_source_snapshot"],
        "schemas/fmdl3ea_baseline_manifest_v1.schema.json",
        "schemas/fmdl3ea_delta_event_v1.schema.json",
    ]
    for path in required_paths:
        if not (ROOT / path).exists():
            errors.append(f"MISSING_CONTRACT_INPUT:{path}")

    for path in [
        "schemas/fmdl3ea_baseline_manifest_v1.schema.json",
        "schemas/fmdl3ea_delta_event_v1.schema.json",
    ]:
        try:
            jsonschema.Draft202012Validator.check_schema(load_json(ROOT / path))
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{path}:{exc}")

    errors.extend(validate_delta_catalog(catalog))
    if len(catalog) != 16:
        errors.append("DELTA_EVENT_CATALOG_MUST_HAVE_16_ROWS")
    if len(cfg["baseline"]["required_source_files"]) != len(
        set(cfg["baseline"]["required_source_files"])
    ):
        errors.append("DUPLICATE_REQUIRED_SOURCE_FILE")
    if set(cfg["baseline"]["required_component_stages"]) != {
        "FMDL-3D-A",
        "FMDL-3D-B",
        "FMDL-3D-C",
        "FMDL-3D-D",
    }:
        errors.append("COMPONENT_STAGE_SET_NOT_EXACT")
    if int(cfg["baseline"]["required_universe_symbol_count"]) != 5528:
        errors.append("BASELINE_UNIVERSE_GATE_NOT_5528")
    if not 0 < float(cfg["incremental_scope"]["maximum_affected_symbol_ratio"]) <= 0.20:
        errors.append("INCREMENTAL_SYMBOL_RATIO_NOT_FAIL_CLOSED")
    if not 0 < float(cfg["incremental_scope"]["maximum_restatement_symbol_ratio"]) <= 0.10:
        errors.append("RESTATEMENT_RATIO_NOT_FAIL_CLOSED")
    if int(cfg["incremental_scope"]["maximum_affected_periods_per_symbol"]) > 12:
        errors.append("AFFECTED_PERIOD_GATE_TOO_WIDE")
    if not promotion_policy_is_fail_closed(cfg["promotion_policy"]):
        errors.append("PROMOTION_POLICY_NOT_FAIL_CLOSED")
    if not rollback_policy_preserves_last_good(cfg["rollback_policy"]):
        errors.append("ROLLBACK_POLICY_DOES_NOT_PRESERVE_LAST_GOOD")
    if len(cfg["full_rebuild_triggers"]) < 8:
        errors.append("FULL_REBUILD_TRIGGER_SET_INCOMPLETE")
    if cfg.get("authority") != "DATA_AND_RESEARCH_EVIDENCE_ONLY":
        errors.append("UNCONTROLLED_AUTHORITY")
    if cfg.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_NOT_NONE")
    if any(
        bool(cfg["authority_boundary"].get(key))
        for key in [
            "candidate_pool_mutation_authorized",
            "simulation_mutation_authorized",
            "real_account_mutation_authorized",
            "portfolio_action_authorized",
            "order_execution_authorized",
        ]
    ):
        errors.append("AUTOMATIC_ACTION_AUTHORITY_PRESENT")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "delta_event_type_count": int(len(catalog)),
        "required_source_file_count": int(len(cfg["baseline"]["required_source_files"])),
        "full_rebuild_trigger_count": int(len(cfg["full_rebuild_triggers"])),
        "authority": cfg["authority"],
        "trade_authority": cfg["trade_authority"],
        "next_gate": cfg["next_gate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
