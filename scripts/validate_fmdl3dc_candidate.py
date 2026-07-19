from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from scripts import fmdl3dc_core as core

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3dc_engine.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonable(record: dict) -> dict:
    out = {}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and pd.isna(value)):
            out[key] = None
        elif hasattr(value, "item"):
            try:
                out[key] = value.item()
            except Exception:
                out[key] = value
        else:
            out[key] = value
    return out


def validate_rows(frame: pd.DataFrame, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for index, record in enumerate(frame.to_dict("records")):
        for error in validator.iter_errors(jsonable(record)):
            errors.append(f"row={index}:{error.json_path}:{error.message}")
            if len(errors) >= 100:
                return errors
    return errors


def replay_value(row: pd.Series) -> float | None:
    values = core.parse_json_map(row.get("input_values_json"))
    metric_id = str(row["metric_id"])
    market_cap = values.get("total_market_cap_cny")
    if market_cap is None:
        return None
    market_cap = float(market_cap)
    if metric_id == "VAL_PE_TTM":
        return market_cap / float(values["net_income_parent_ttm"])
    if metric_id == "VAL_EARNINGS_YIELD_TTM":
        return float(values["net_income_parent_ttm"]) / market_cap
    if metric_id == "VAL_PB":
        return market_cap / float(values["parent_equity"])
    if metric_id == "VAL_PS_TTM":
        return market_cap / float(values["revenue_ttm"])
    if metric_id == "VAL_FCF_YIELD_TTM":
        return float(values["free_cash_flow_ttm"]) / market_cap
    if metric_id == "VAL_EV_SALES_TTM":
        return float(values["enterprise_value_cny"]) / float(values["revenue_ttm"])
    if metric_id == "VAL_EV_OPERATING_INCOME_TTM":
        return float(values["enterprise_value_cny"]) / float(values["operating_income_ttm"])
    return None


def main() -> int:
    cfg = load_json(CONFIG)
    root = ROOT / cfg["publication"]["candidate_root"]
    decision = load_json(root / "FMDL3DC_DECISION.json")
    manifest = load_json(root / "FMDL3DC_MANIFEST.json")
    detail = pd.read_parquet(root / "FMDL3DC_VALUATION_METRIC_DETAIL.parquet")
    current = pd.read_parquet(root / "FMDL3DC_VALUATION_CURRENT.parquet")
    coverage = pd.read_csv(root / "FMDL3DC_COVERAGE.csv", encoding="utf-8-sig")
    denominator = pd.read_csv(
        root / "FMDL3DC_DENOMINATOR_VALIDITY.csv", encoding="utf-8-sig"
    )
    registry = pd.read_csv(root / "FMDL3DC_METRIC_REGISTRY.csv", encoding="utf-8-sig")
    cap_release = load_json(ROOT / cfg["inputs"]["capitalization_release"])
    cap = pd.read_parquet(ROOT / cap_release["capitalization_current_path"])

    manifest_errors = []
    for item in manifest.get("files", []):
        path = root / item["path"]
        if not path.exists():
            manifest_errors.append(f"missing:{item['path']}")
        elif sha256(path) != item["sha256"]:
            manifest_errors.append(f"hash:{item['path']}")
        elif path.stat().st_size != int(item["bytes"]):
            manifest_errors.append(f"size:{item['path']}")

    detail_schema = load_json(
        ROOT / "schemas/fmdl3dc_valuation_metric_detail_v1.schema.json"
    )
    current_schema = load_json(ROOT / "schemas/fmdl3dc_valuation_current_v1.schema.json")
    detail_schema_errors = validate_rows(detail, detail_schema)
    current_schema_errors = validate_rows(current, current_schema)

    expected_metrics = cfg["engine"]["expected_valuation_metric_ids"]
    valid = detail[detail["quality_state"].isin(core.VALID_STATES)].copy()
    invalid = detail[~detail["quality_state"].isin(core.VALID_STATES)].copy()

    max_replay_diff = 0.0
    replay_errors = 0
    denominator_sign_errors = 0
    for _, row in valid.iterrows():
        expected = replay_value(row)
        actual = float(row["metric_value"])
        if expected is None:
            replay_errors += 1
            continue
        diff = abs(actual - expected)
        max_replay_diff = max(max_replay_diff, diff)
        if diff > float(cfg["engine"]["valuation_replay_absolute_tolerance"]):
            replay_errors += 1
        values = core.parse_json_map(row["input_values_json"])
        metric_id = str(row["metric_id"])
        if metric_id in {"VAL_PE_TTM", "VAL_EARNINGS_YIELD_TTM"} and float(values["net_income_parent_ttm"]) <= 0:
            denominator_sign_errors += 1
        if metric_id == "VAL_PB" and float(values["parent_equity"]) <= 0:
            denominator_sign_errors += 1
        if metric_id in {"VAL_PS_TTM", "VAL_EV_SALES_TTM"} and float(values["revenue_ttm"]) <= 0:
            denominator_sign_errors += 1
        if metric_id == "VAL_EV_OPERATING_INCOME_TTM" and float(values["operating_income_ttm"]) <= 0:
            denominator_sign_errors += 1
        if metric_id.startswith("VAL_EV_") and float(values["enterprise_value_cny"]) <= 0:
            denominator_sign_errors += 1

    future_selected = 0
    for _, row in detail[detail["denominator_available_from"].notna()].iterrows():
        available = core.normalize_timestamp(
            row["denominator_available_from"], cfg["business_timezone"]
        )
        cutoff = core.market_cutoff(
            str(row["market_as_of_date"]),
            cfg["engine"]["market_cutoff_time"],
            cfg["business_timezone"],
        )
        if available is not None and available > cutoff:
            future_selected += 1

    non_general_valid = valid[
        valid["metric_id"].isin(
            ["VAL_PS_TTM", "VAL_FCF_YIELD_TTM", "VAL_EV_SALES_TTM", "VAL_EV_OPERATING_INCOME_TTM"]
        )
        & ~valid["sector_profile"].eq("GENERAL_NON_FINANCIAL")
    ]

    current_metric_pairs = set()
    for metric_id, (value_col, state_col) in core.METRIC_COLUMN_MAP.items():
        for _, row in current.iterrows():
            current_metric_pairs.add(
                (
                    str(row["symbol"]),
                    metric_id,
                    None if pd.isna(row[value_col]) else float(row[value_col]),
                    str(row[state_col]),
                )
            )
    detail_metric_pairs = {
        (
            str(row["symbol"]),
            str(row["metric_id"]),
            None if pd.isna(row["metric_value"]) else float(row["metric_value"]),
            str(row["quality_state"]),
        )
        for _, row in detail.iterrows()
    }

    prohibited_columns = {
        column
        for column in list(detail.columns) + list(current.columns)
        if any(token in column.lower() for token in ["target_price", "valuation_score", "buy_signal", "sell_signal", "portfolio_action"])
    }

    checks = {
        "DECISION_ACCEPTED": decision.get("status") == cfg["exit_status"],
        "DECISION_HARD_FAILURES_EMPTY": not decision.get("hard_failures"),
        "MANIFEST_VALID": not manifest_errors,
        "ROW_SCHEMAS_VALID": not detail_schema_errors and not current_schema_errors,
        "CURRENT_EXACT_CAPITALIZATION_UNIVERSE": len(current) == len(cap)
        and set(current["symbol"].astype(str)) == set(cap["symbol"].astype(str)),
        "CURRENT_KEYS_UNIQUE": not current.duplicated(["symbol"]).any(),
        "DETAIL_EXACT_MATRIX": len(detail) == len(current) * len(expected_metrics),
        "DETAIL_KEYS_UNIQUE": not detail.duplicated(["symbol", "metric_id"]).any(),
        "REGISTRY_EXACT": set(registry["metric_id"].astype(str)) == set(expected_metrics)
        and len(registry) == len(expected_metrics),
        "CURRENT_DETAIL_RECONCILE": current_metric_pairs == detail_metric_pairs,
        "VALID_ROWS_HAVE_VALUES": valid["metric_value"].notna().all(),
        "INVALID_ROWS_HAVE_NULL_VALUES": invalid["metric_value"].isna().all(),
        "VALUATION_FORMULAS_REPLAY": replay_errors == 0,
        "DENOMINATOR_SIGN_GATES": denominator_sign_errors == 0,
        "ZERO_FUTURE_SELECTED_DENOMINATOR": future_selected == 0,
        "SECTOR_APPLICABILITY_ENFORCED": non_general_valid.empty,
        "CAPITALIZATION_LINEAGE_PRESENT_FOR_VALID": valid["capitalization_lineage_id"].notna().all(),
        "METRIC_LINEAGE_UNIQUE": not detail.duplicated(["metric_lineage_id"]).any(),
        "COVERAGE_NONEMPTY": len(coverage) > 0,
        "DENOMINATOR_MAP_NONEMPTY": len(denominator) > 0,
        "NO_SCORE_TARGET_OR_ACTION": not prohibited_columns,
        "ZERO_TRADE_AUTHORITY": set(detail["trade_authority"].astype(str)) == {"NONE"}
        and set(current["trade_authority"].astype(str)) == {"NONE"},
        "NEXT_GATE_FMDL3DD": decision.get("next_gate") == cfg["next_gate"],
    }
    failures = [key for key, value in checks.items() if not bool(value)]
    metrics = dict(decision.get("metrics", {}))
    metrics.update(
        {
            "manifest_error_count": len(manifest_errors),
            "detail_schema_error_count": len(detail_schema_errors),
            "current_schema_error_count": len(current_schema_errors),
            "formula_replay_error_count": replay_errors,
            "denominator_sign_error_count": denominator_sign_errors,
            "future_selected_denominator_count_independent": future_selected,
            "non_general_valid_ordinary_metric_count": int(len(non_general_valid)),
            "maximum_valuation_replay_difference": max_replay_diff,
        }
    )
    validation = {
        "validation_version": "1.0.0",
        "release_id": decision.get("release_id"),
        "program_id": "FMDL-3D-C",
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "checks": [
            {"check_id": key, "status": "PASS" if bool(value) else "FAIL"}
            for key, value in checks.items()
        ],
        "metrics": metrics,
        "manifest_errors": manifest_errors,
        "schema_errors": detail_schema_errors + current_schema_errors,
        "authority": core.AUTHORITY,
        "trade_authority": core.TRADE_AUTHORITY,
        "next_gate": cfg["next_gate"],
    }
    (root / "FMDL3DC_VALIDATION.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
