from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd

from scripts.fmdl3db_core import ROOT, load_json, sha256_file, shard_for_symbol

CONFIG = ROOT / "config/fmdl3db_engine.json"


def main() -> int:
    config = load_json(CONFIG)
    errors: list[str] = []
    required_paths = [
        config["entry_gate"]["pointer_path"],
        config["market_inputs"]["current_release_path"],
        config["market_inputs"]["universe_path"],
        config["market_inputs"]["universe_manifest_path"],
        config["market_inputs"]["snapshot_path"],
        config["market_inputs"]["snapshot_manifest_path"],
        "schemas/fmdl3db_effective_share_ledger_v1.schema.json",
        "schemas/fmdl3db_capitalization_current_v1.schema.json",
    ]
    for relative in required_paths:
        if not (ROOT / relative).exists():
            errors.append(f"MISSING_REQUIRED_PATH:{relative}")

    if not errors:
        entry = load_json(ROOT / config["entry_gate"]["pointer_path"])
        release = load_json(ROOT / config["market_inputs"]["current_release_path"])
        universe_manifest = load_json(
            ROOT / config["market_inputs"]["universe_manifest_path"]
        )
        snapshot_manifest = load_json(
            ROOT / config["market_inputs"]["snapshot_manifest_path"]
        )
        universe_path = ROOT / config["market_inputs"]["universe_path"]
        snapshot_path = ROOT / config["market_inputs"]["snapshot_path"]
        if entry.get("status") != config["entry_gate"]["required_status"]:
            errors.append("ENTRY_GATE_NOT_ACCEPTED")
        if release.get("hard_failures") != []:
            errors.append("SOURCE_CURRENT_HAS_HARD_FAILURES")
        if release.get("as_of_date") != universe_manifest.get("as_of_date"):
            errors.append("UNIVERSE_AS_OF_MISMATCH")
        if release.get("as_of_date") != snapshot_manifest.get("as_of_date"):
            errors.append("SNAPSHOT_AS_OF_MISMATCH")
        if sha256_file(universe_path) != release["current_files"]["a_share_universe"]["sha256"]:
            errors.append("UNIVERSE_HASH_MISMATCH")
        if sha256_file(snapshot_path) != release["current_files"]["daily_market_snapshot"]["sha256"]:
            errors.append("SNAPSHOT_HASH_MISMATCH")
        universe = pd.read_csv(universe_path, encoding="utf-8-sig", dtype={"symbol": str})
        snapshot = pd.read_csv(snapshot_path, encoding="utf-8-sig", dtype={"symbol": str})
        if len(universe) != int(universe_manifest["row_count"]):
            errors.append("UNIVERSE_ROW_COUNT_MISMATCH")
        if len(snapshot) != int(snapshot_manifest["row_count"]):
            errors.append("SNAPSHOT_ROW_COUNT_MISMATCH")
        if universe["symbol"].duplicated().any():
            errors.append("DUPLICATE_UNIVERSE_SYMBOL")
        shard_count = int(config["sharding"]["shard_count"])
        shard_ids = universe["symbol"].astype(str).map(
            lambda symbol: shard_for_symbol(symbol, shard_count)
        )
        if set(shard_ids) != set(range(shard_count)):
            errors.append("ONE_OR_MORE_SHARDS_EMPTY")
        if not shard_ids.between(0, shard_count - 1).all():
            errors.append("SHARD_ID_OUT_OF_RANGE")

    acceptance = config["acceptance"]
    ratio_fields = [
        "minimum_accepted_price_coverage",
        "minimum_effective_share_coverage_overall",
        "minimum_effective_share_coverage_non_bse",
    ]
    for field in ratio_fields:
        value = float(acceptance[field])
        if not 0 <= value <= 1:
            errors.append(f"INVALID_RATIO:{field}")
    for board, value in acceptance["minimum_effective_share_coverage_by_board"].items():
        if not 0 <= float(value) <= 1:
            errors.append(f"INVALID_BOARD_RATIO:{board}")
    if set(acceptance["minimum_effective_share_coverage_by_board"]) != {
        "SH_MAIN",
        "SZ_MAIN",
        "STAR",
        "CHINEXT",
        "BSE",
    }:
        errors.append("BOARD_GATE_SET_NOT_COMPLETE")
    if config["source_route"].get("provider_market_cap_fields_are_authoritative"):
        errors.append("PROVIDER_MARKET_CAP_MUST_NOT_BE_AUTHORITATIVE")
    if config["source_route"].get("provider_valuation_fields_are_authoritative"):
        errors.append("PROVIDER_VALUATION_MUST_NOT_BE_AUTHORITATIVE")
    if config.get("trade_authority") != "NONE":
        errors.append("TRADE_AUTHORITY_MUST_BE_NONE")
    if config.get("next_gate") != "FMDL-3D-C_VALUATION_ENGINE_CURRENT":
        errors.append("NEXT_GATE_NOT_FMDL3DC")
    if int(config["sharding"]["shard_count"]) != 16:
        errors.append("SHARD_COUNT_NOT_FROZEN_AT_16")

    for relative in [
        "schemas/fmdl3db_effective_share_ledger_v1.schema.json",
        "schemas/fmdl3db_capitalization_current_v1.schema.json",
    ]:
        try:
            jsonschema.Draft202012Validator.check_schema(load_json(ROOT / relative))
        except Exception as exc:
            errors.append(f"INVALID_SCHEMA:{relative}:{exc}")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "program_id": config["program_id"],
        "shard_count": config["sharding"]["shard_count"],
        "source_id": config["source_route"]["source_id"],
        "authority": config["authority"],
        "trade_authority": config["trade_authority"],
        "next_gate": config["next_gate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
