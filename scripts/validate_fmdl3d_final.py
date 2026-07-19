from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts.fmdl3d_final_core import (
    market_cap_replay_error_count,
    replay_row_hashes,
    shareholder_yield_replay_error_count,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3d_final_contract.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(record: dict) -> dict:
    return {key: (None if pd.isna(value) else value) for key, value in record.items()}


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3D_FINAL_DECISION.json")
    manifest = load_json(root / "FMDL3D_FINAL_MANIFEST.json")
    interface = load_json(root / "FMDL3D_UNIFIED_CURRENT_INTERFACE.json")
    release_index = load_json(root / "FMDL3D_UNIFIED_RELEASE_INDEX.json")
    source_snapshot = load_json(root / "FMDL3D_COMPONENT_SOURCE_SNAPSHOT.json")
    unified = pd.read_parquet(root / "FMDL3D_UNIFIED_CURRENT.parquet")
    capitalization = pd.read_parquet(ROOT / cfg["inputs"]["capitalization_current"])
    valuation = pd.read_parquet(ROOT / cfg["inputs"]["valuation_current"])
    shareholder_return = pd.read_parquet(
        ROOT / cfg["inputs"]["shareholder_return_current"]
    )
    valuation_detail = pd.read_parquet(ROOT / cfg["inputs"]["valuation_detail"])
    shareholder_events = pd.read_parquet(
        ROOT / cfg["inputs"]["shareholder_return_events"]
    )
    current_schema = load_json(
        ROOT / "schemas/fmdl3d_unified_current_v1.schema.json"
    )
    interface_schema = load_json(
        ROOT / "schemas/fmdl3d_unified_interface_v1.schema.json"
    )

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")

    schema_errors: list[str] = []
    current_validator = jsonschema.Draft202012Validator(
        current_schema, format_checker=jsonschema.FormatChecker()
    )
    for record in unified.to_dict(orient="records"):
        cleaned = clean(record)
        for error in current_validator.iter_errors(cleaned):
            schema_errors.append(f"current:{record.get('symbol')}:{error.message}")
    interface_errors = [
        error.message
        for error in jsonschema.Draft202012Validator(
            interface_schema, format_checker=jsonschema.FormatChecker()
        ).iter_errors(interface)
    ]

    cap_replay_errors, max_cap_diff = market_cap_replay_error_count(
        capitalization,
        float(cfg["unified_current"]["market_cap_replay_tolerance_cny"]),
    )
    shareholder_replay_errors, max_shareholder_diff = (
        shareholder_yield_replay_error_count(
            shareholder_return,
            float(cfg["unified_current"]["formula_replay_tolerance"]),
        )
    )
    row_hash_errors = replay_row_hashes(unified)
    component_validations = source_snapshot["validations"]
    component_pointers = source_snapshot["pointers"]
    component_releases = source_snapshot["releases"]
    component_stages = {"FMDL-3D-A", "FMDL-3D-B", "FMDL-3D-C", "FMDL-3D-D"}
    symbol_sets = [
        set(capitalization["symbol"].astype(str)),
        set(valuation["symbol"].astype(str)),
        set(shareholder_return["symbol"].astype(str)),
        set(unified["symbol"].astype(str)),
    ]
    date_sets = [
        set(capitalization["price_as_of_date"].dropna().astype(str)),
        set(valuation["market_as_of_date"].dropna().astype(str)),
        set(shareholder_return["market_as_of_date"].dropna().astype(str)),
        set(unified["market_as_of_date"].dropna().astype(str)),
    ]
    complete = unified[unified["complete_shareholder_yield"]]
    forbidden = {
        "valuation_score",
        "shareholder_return_score",
        "investment_signal",
        "target_price",
        "target_weight",
        "order_quantity",
        "portfolio_action",
    }
    b_metrics = component_validations["FMDL-3D-B"].get("metrics", {})
    c_metrics = component_validations["FMDL-3D-C"].get("metrics", {})
    d_metrics = component_validations["FMDL-3D-D"].get("metrics", {})
    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_VALID": not manifest_errors,
        "UNIFIED_CURRENT_SCHEMA_VALID": not schema_errors,
        "UNIFIED_INTERFACE_SCHEMA_VALID": not interface_errors,
        "COMPONENT_STAGE_SET_EXACT": set(component_pointers) == component_stages
        and set(component_releases) == component_stages
        and set(component_validations) == component_stages,
        "COMPONENT_POINTER_RELEASE_ALIGNMENT": all(
            component_pointers[stage]["release_id"]
            == component_releases[stage]["release_id"]
            for stage in component_stages
        ),
        "COMPONENT_VALIDATIONS_PASS": all(
            component_validations[stage].get("status") == "PASS"
            and component_validations[stage].get("hard_failures") == []
            for stage in component_stages
        ),
        "RELEASE_INDEX_ALIGNED": release_index.get("components", {}).keys()
        == interface.get("component_releases", {}).keys()
        and all(
            release_index["components"][stage]["release_id"]
            == interface["component_releases"][stage]
            for stage in component_stages
        ),
        "UNIFIED_EXACT_UNIVERSE": len(unified)
        == int(cfg["unified_current"]["required_universe_count"]),
        "UNIFIED_KEYS_UNIQUE": not unified["symbol"].duplicated().any(),
        "EXACT_SYMBOL_SET_ALIGNMENT": all(
            symbols == symbol_sets[0] for symbols in symbol_sets[1:]
        ),
        "EXACT_MARKET_DATE_ALIGNMENT": all(
            dates == date_sets[0] for dates in date_sets[1:]
        )
        and len(date_sets[0]) == 1,
        "UNIFIED_ROW_HASHES_REPLAY": row_hash_errors == 0,
        "CAPITALIZATION_REPLAY": cap_replay_errors == 0,
        "SHAREHOLDER_YIELD_REPLAY": shareholder_replay_errors == 0,
        "COMPLETE_SHAREHOLDER_ROWS_HAVE_COMPONENTS": complete[
            [
                "dividend_yield_ttm",
                "completed_buyback_yield_ttm",
                "completed_issuance_dilution_yield_ttm",
                "shareholder_yield_ttm",
            ]
        ]
        .notna()
        .all()
        .all(),
        "VALUATION_DETAIL_KEYS_UNIQUE": not valuation_detail.duplicated(
            ["symbol", "metric_id"]
        ).any(),
        "SHAREHOLDER_EVENT_KEYS_UNIQUE": shareholder_events.empty
        or not shareholder_events["event_id"].duplicated().any(),
        "ZERO_FUTURE_SELECTED_SHARE": int(
            b_metrics.get("future_selected_share_count_independent", -1)
        )
        == 0,
        "ZERO_FUTURE_SELECTED_DENOMINATOR": int(
            c_metrics.get("future_selected_denominator_count_independent", -1)
        )
        == 0,
        "ZERO_FUTURE_EFFECTIVE_SHAREHOLDER_EVENT": int(
            d_metrics.get("future_effective_event_count_independent", -1)
        )
        == 0,
        "ZERO_COMPONENT_FORMULA_ERRORS": int(
            c_metrics.get("formula_replay_error_count", -1)
        )
        == 0
        and int(d_metrics.get("formula_replay_error_count_independent", -1)) == 0,
        "NO_SCORE_TARGET_OR_ACTION": not (forbidden & set(unified.columns)),
        "ZERO_TRADE_AUTHORITY": set(unified["trade_authority"].astype(str)).issubset(
            {"NONE"}
        )
        and interface.get("trade_authority") == "NONE"
        and release_index.get("trade_authority") == "NONE",
        "NEXT_GATE_FMDL3E": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-3D-FINAL",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if value else "FAIL"}
            for key, value in checks.items()
        ],
        "metrics": {
            **decision.get("metrics", {}),
            "manifest_error_count": len(manifest_errors),
            "unified_schema_error_count": len(schema_errors),
            "interface_schema_error_count": len(interface_errors),
            "unified_row_hash_error_count": row_hash_errors,
            "capitalization_replay_error_count_independent": cap_replay_errors,
            "capitalization_maximum_replay_difference_cny_independent": max_cap_diff,
            "shareholder_yield_replay_error_count_independent": shareholder_replay_errors,
            "shareholder_yield_maximum_replay_difference_independent": max_shareholder_diff,
        },
        "manifest_errors": manifest_errors,
        "schema_errors": schema_errors[:50],
        "interface_schema_errors": interface_errors,
        "authority": cfg["authority"],
        "trade_authority": "NONE",
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3D_FINAL_VALIDATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
