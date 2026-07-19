from __future__ import annotations

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


def validate_frame(frame: pd.DataFrame, schema: dict, label: str) -> list[str]:
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors: list[str] = []
    for record in frame.to_dict(orient="records"):
        cleaned = clean_record(record)
        for error in validator.iter_errors(cleaned):
            errors.append(
                f"{label}:{cleaned.get('symbol')}:{error.json_path}:{error.message}"
            )
    return errors


def main() -> int:
    config = load_json(CONFIG)
    root = ROOT / config["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3DB_DECISION.json")
    manifest = load_json(root / "FMDL3DB_MANIFEST.json")
    release = load_json(root / "FMDL3DB_SOURCE_MARKET_RELEASE.json")
    current = pd.read_parquet(root / "FMDL3DB_CAPITALIZATION_CURRENT.parquet")
    ledger = pd.read_parquet(root / "FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet")
    retry = pd.read_csv(root / "FMDL3DB_RETRY_LEDGER.csv", encoding="utf-8-sig", dtype={"symbol": str})
    coverage = pd.read_csv(root / "FMDL3DB_COVERAGE.csv", encoding="utf-8-sig")
    quarantine = pd.read_csv(root / "FMDL3DB_QUARANTINE.csv", encoding="utf-8-sig", dtype={"symbol": str})
    universe = pd.read_csv(
        ROOT / config["market_inputs"]["universe_path"],
        encoding="utf-8-sig",
        dtype={"symbol": str},
    )

    manifest_errors: list[str] = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"MISSING:{item['path']}")
        elif sha256_file(path) != item["sha256"]:
            manifest_errors.append(f"HASH:{item['path']}")

    schema_errors = validate_frame(
        current,
        load_json(ROOT / "schemas/fmdl3db_capitalization_current_v1.schema.json"),
        "current",
    )
    schema_errors.extend(
        validate_frame(
            ledger,
            load_json(ROOT / "schemas/fmdl3db_effective_share_ledger_v1.schema.json"),
            "ledger",
        )
    )

    acceptance = config["acceptance"]
    valid = current[current["capitalization_state"].isin(VALID_CAP_STATES)]
    invalid = current[~current["capitalization_state"].isin(VALID_CAP_STATES)]
    selected = ledger[ledger["selected_for_current"].eq(True)] if len(ledger) else ledger
    accepted_price = (
        current["close"].notna()
        & (current["close"] > 0)
        & current["price_row_hash"].notna()
    )
    price_coverage = float(accepted_price.mean())
    share_coverage = float(len(valid) / len(current))
    non_bse = current[current["board"].ne("BSE")]
    non_bse_coverage = float(
        non_bse["capitalization_state"].isin(VALID_CAP_STATES).mean()
    ) if len(non_bse) else 0.0
    board_coverage = {
        str(board): float(frame["capitalization_state"].isin(VALID_CAP_STATES).mean())
        for board, frame in current.groupby("board", dropna=False)
    }
    board_gates = {
        board: board_coverage.get(board, 0.0) >= float(threshold)
        for board, threshold in acceptance["minimum_effective_share_coverage_by_board"].items()
    }
    replay_total = valid["close"] * valid["total_shares"]
    replay_float = valid["close"] * valid["float_a_shares"]
    future_selected = int(
        selected["eligibility_state"].eq("FUTURE_EFFECTIVE").sum()
    ) if len(selected) else 0
    future_current = int(
        (
            pd.to_datetime(valid["share_effective_date"], errors="coerce")
            > pd.to_datetime(valid["price_as_of_date"], errors="coerce")
        ).sum()
    ) if len(valid) else 0
    selected_hashes = set(selected["source_row_hash"]) if len(selected) else set()
    current_hashes = set(valid["share_source_row_hash"].dropna())
    universe_symbols = set(universe["symbol"].astype(str))

    checks = {
        "DECISION_ACCEPTED": decision.get("status") == config["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": decision.get("hard_failures") == [],
        "MANIFEST_VALID": not manifest_errors,
        "ROW_SCHEMAS_VALID": not schema_errors,
        "CURRENT_EXACT_UNIVERSE": len(current) == len(universe)
        and set(current["symbol"].astype(str)) == universe_symbols,
        "CURRENT_KEYS_UNIQUE": not current["symbol"].duplicated().any(),
        "RETRY_EXACT_UNIVERSE": len(retry) == len(universe)
        and set(retry["symbol"].astype(str)) == universe_symbols,
        "QUARANTINE_EQUALS_INVALID_CURRENT": len(quarantine) == len(invalid)
        and set(quarantine["symbol"].astype(str)) == set(invalid["symbol"].astype(str)),
        "LEDGER_KEYS_UNIQUE": not ledger.duplicated(
            ["symbol", "source_effective_date", "source_row_hash"]
        ).any() if len(ledger) else True,
        "PRICE_COVERAGE_GATE": price_coverage
        >= float(acceptance["minimum_accepted_price_coverage"]),
        "SHARE_COVERAGE_GATE": share_coverage
        >= float(acceptance["minimum_effective_share_coverage_overall"]),
        "NON_BSE_COVERAGE_GATE": non_bse_coverage
        >= float(acceptance["minimum_effective_share_coverage_non_bse"]),
        "BOARD_COVERAGE_GATES": all(board_gates.values()),
        "VALID_ROWS_COMPLETE": valid[
            ["close", "share_effective_date", "total_shares", "float_a_shares", "total_market_cap_cny", "float_market_cap_cny", "share_source_row_hash"]
        ].notna().all().all(),
        "INVALID_ROWS_NULL_CAPITALIZATION": invalid[
            ["total_market_cap_cny", "float_market_cap_cny"]
        ].isna().all().all(),
        "ONE_SELECTED_LEDGER_ROW_PER_VALID_CURRENT": len(selected) == len(valid)
        and not selected["symbol"].duplicated().any(),
        "SELECTED_LINEAGE_EXACT": selected_hashes == current_hashes,
        "ZERO_FUTURE_SELECTED": future_selected == 0,
        "ZERO_FUTURE_CURRENT": future_current == 0,
        "SELECTED_SHARES_POSITIVE": (
            (selected["total_shares"] > 0).all()
            and (selected["float_a_shares"] > 0).all()
        ) if len(selected) else True,
        "FLOAT_SHARES_WITHIN_TOTAL": (valid["float_a_shares"] <= valid["total_shares"]).all(),
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
        "SOURCE_RELEASE_BOUND": set(current["source_release_id"]) == {release["run_id"]}
        and set(current["price_as_of_date"]) == {release["as_of_date"]},
        "COVERAGE_HAS_ALL_BOARDS": set(
            coverage.loc[coverage["dimension"].eq("BOARD"), "dimension_value"].astype(str)
        ).issuperset(set(acceptance["minimum_effective_share_coverage_by_board"])),
        "INVALID_ROWS_EXPLICIT": invalid["state_reason"].fillna("").str.len().gt(0).all(),
        "NO_VALUATION_SCORE_TARGET_OR_ACTION": not (
            {
                "valuation_score",
                "target_price",
                "investment_signal",
                "target_weight",
                "portfolio_action",
            }
            & set(current.columns)
        ),
        "ZERO_TRADE_AUTHORITY": set(current["trade_authority"]) == {"NONE"}
        and (ledger.empty or set(ledger["trade_authority"]) == {"NONE"})
        and set(retry["trade_authority"]) == {"NONE"},
        "NEXT_GATE_FMDL3DC": decision.get("next_gate") == config["next_gate"],
    }
    failures = [key for key, passed in checks.items() if not bool(passed)]
    total_abs = (replay_total - valid["total_market_cap_cny"]).abs()
    float_abs = (replay_float - valid["float_market_cap_cny"]).abs()
    result = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-3D-B",
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
            "price_coverage_ratio_independent": price_coverage,
            "effective_share_coverage_ratio_independent": share_coverage,
            "non_bse_effective_share_coverage_ratio_independent": non_bse_coverage,
            "future_selected_share_count_independent": future_selected,
            "future_current_share_count_independent": future_current,
            "total_market_cap_max_absolute_replay_difference_cny": float(total_abs.max()) if len(total_abs) else 0.0,
            "float_market_cap_max_absolute_replay_difference_cny": float(float_abs.max()) if len(float_abs) else 0.0,
            "board_coverage_independent": board_coverage,
        },
        "manifest_errors": manifest_errors,
        "schema_errors": schema_errors[:200],
        "authority": config["authority"],
        "trade_authority": "NONE",
        "next_gate": config["next_gate"],
    }
    write_json(root / "FMDL3DB_VALIDATION.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
