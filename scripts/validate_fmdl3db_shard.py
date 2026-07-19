from __future__ import annotations

import argparse
import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd

from scripts.fmdl3db_core import ROOT, VALID_CAP_STATES, load_json, sha256_file, write_json

CONFIG = ROOT / "config/fmdl3db_engine.json"


def clean_record(record: dict) -> dict:
    cleaned = {}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and pd.isna(value)):
            cleaned[key] = None
        elif hasattr(value, "item"):
            try:
                cleaned[key] = value.item()
            except Exception:
                cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_json(args.config)
    shard_id = int(args.shard_id)
    root = ROOT / config["publication"]["shard_root"] / f"shard-{shard_id:02d}"
    decision = load_json(root / "SHARD_DECISION.json")
    manifest = load_json(root / "SHARD_MANIFEST.json")
    membership = pd.read_csv(root / "SHARD_MEMBERSHIP.csv", encoding="utf-8-sig", dtype={"symbol": str})
    current = pd.read_parquet(root / "SHARD_CAPITALIZATION_CURRENT.parquet")
    ledger = pd.read_parquet(root / "SHARD_EFFECTIVE_SHARE_LEDGER.parquet")
    retry = pd.read_csv(root / "SHARD_RETRY_LEDGER.csv", encoding="utf-8-sig", dtype={"symbol": str})

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256_file(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")

    schemas = [
        (
            current,
            load_json(ROOT / "schemas/fmdl3db_capitalization_current_v1.schema.json"),
            "current",
        ),
        (
            ledger,
            load_json(ROOT / "schemas/fmdl3db_effective_share_ledger_v1.schema.json"),
            "ledger",
        ),
    ]
    schema_errors: list[str] = []
    for frame, schema, label in schemas:
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        for record in frame.to_dict(orient="records"):
            cleaned = clean_record(record)
            for error in validator.iter_errors(cleaned):
                schema_errors.append(
                    f"{label}:{cleaned.get('symbol')}:{error.json_path}:{error.message}"
                )

    valid = current[current["capitalization_state"].isin(VALID_CAP_STATES)]
    invalid = current[~current["capitalization_state"].isin(VALID_CAP_STATES)]
    selected = ledger[ledger["selected_for_current"].eq(True)] if len(ledger) else ledger
    acceptance = config["acceptance"]
    replay_total = valid["close"] * valid["total_shares"]
    replay_float = valid["close"] * valid["float_a_shares"]
    checks = {
        "RUNNER_DECISION_ACCEPTED": decision.get("status") == "FMDL3DB_SHARD_ACCEPTED",
        "RUNNER_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_VALID": not manifest_errors,
        "ROW_SCHEMAS_VALID": not schema_errors,
        "MEMBERSHIP_CURRENT_EXACT": len(membership) == len(current)
        and set(membership["symbol"]) == set(current["symbol"]),
        "MEMBERSHIP_CURRENT_RETRY_EXACT": set(membership["symbol"]) == set(retry["symbol"]),
        "CURRENT_KEYS_UNIQUE": not current["symbol"].duplicated().any(),
        "LEDGER_KEYS_UNIQUE": not ledger.duplicated(
            ["symbol", "source_effective_date", "source_row_hash"]
        ).any() if len(ledger) else True,
        "VALID_ROWS_COMPLETE": valid[
            ["close", "share_effective_date", "total_shares", "float_a_shares", "total_market_cap_cny", "float_market_cap_cny", "share_source_row_hash"]
        ].notna().all().all(),
        "INVALID_ROWS_NULL_CAPITALIZATION": invalid[
            ["total_market_cap_cny", "float_market_cap_cny"]
        ].isna().all().all(),
        "ONE_SELECTED_LEDGER_ROW_PER_VALID_CURRENT": len(selected) == len(valid)
        and not selected["symbol"].duplicated().any()
        and set(selected["source_row_hash"]) == set(valid["share_source_row_hash"]),
        "SELECTED_SHARE_DATES_NOT_FUTURE": (
            pd.to_datetime(selected["source_effective_date"], errors="coerce")
            <= pd.to_datetime(selected["price_as_of_date"], errors="coerce")
        ).all() if len(selected) else True,
        "SELECTED_SHARES_POSITIVE": (
            (selected["total_shares"] > 0).all()
            and (selected["float_a_shares"] > 0).all()
        ) if len(selected) else True,
        "TOTAL_MARKET_CAP_REPLAYS": np.allclose(
            replay_total,
            valid["total_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "FLOAT_MARKET_CAP_REPLAYS": np.allclose(
            replay_float,
            valid["float_market_cap_cny"],
            rtol=float(acceptance["capitalization_relative_tolerance"]),
            atol=float(acceptance["capitalization_absolute_tolerance_cny"]),
        ),
        "NO_PROVIDER_MARKET_CAP_OR_VALUATION_AUTHORITY": not any(
            column in current.columns
            for column in ["provider_market_cap", "provider_pe", "provider_pb", "provider_ps"]
        ),
        "ZERO_TRADE_AUTHORITY": set(current["trade_authority"]) == {"NONE"}
        and (ledger.empty or set(ledger["trade_authority"]) == {"NONE"})
        and set(retry["trade_authority"]) == {"NONE"},
    }
    failures = [key for key, passed in checks.items() if not bool(passed)]
    result = {
        "validation_version": "1.0.0",
        "program_id": "FMDL-3D-B",
        "shard_id": f"{shard_id:02d}",
        "run_id": decision.get("run_id"),
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if passed else "FAIL"}
            for key, passed in checks.items()
        ],
        "metrics": {
            **decision.get("metrics", {}),
            "manifest_error_count": len(manifest_errors),
            "schema_error_count": len(schema_errors),
            "duplicate_current_key_count": int(current["symbol"].duplicated().sum()),
            "duplicate_ledger_key_count": int(
                ledger.duplicated(["symbol", "source_effective_date", "source_row_hash"]).sum()
            ) if len(ledger) else 0,
        },
        "manifest_errors": manifest_errors,
        "schema_errors": schema_errors[:100],
        "authority": config["authority"],
        "trade_authority": "NONE",
    }
    write_json(root / "SHARD_VALIDATION.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
