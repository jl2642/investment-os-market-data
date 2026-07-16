"""Quality gates for FMDL-1 A-share candidate datasets."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import pandas as pd

from pipeline.common import clean_scalar


@dataclass
class DatasetQuality:
    dataset_id: str
    qa_status: str
    publication_status: str
    hard_failures: list[str]
    soft_warnings: list[str]
    metrics: dict[str, Any]
    gate_results: list[dict[str, Any]]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _row_dict(row: pd.Series) -> dict[str, Any]:
    return {key: clean_scalar(value) for key, value in row.items()}


def _schema_failures(frame: pd.DataFrame, schema: dict[str, Any], max_messages: int = 20) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    messages: list[str] = []
    for index, row in frame.iterrows():
        errors = sorted(validator.iter_errors(_row_dict(row)), key=lambda item: list(item.path))
        for error in errors:
            messages.append(f"row={index} path={list(error.path)} message={error.message}")
            if len(messages) >= max_messages:
                return messages
    return messages


def _gate(
    results: list[dict[str, Any]],
    *,
    gate_id: str,
    severity: str,
    actual: Any,
    expected: str,
    passed: bool,
) -> None:
    results.append(
        {
            "gate_id": gate_id,
            "severity": severity,
            "actual": clean_scalar(actual),
            "expected": expected,
            "passed": bool(passed),
        }
    )


def _finalize(dataset_id: str, results: list[dict[str, Any]], metrics: dict[str, Any]) -> DatasetQuality:
    hard = [item["gate_id"] for item in results if item["severity"] == "HARD" and not item["passed"]]
    soft = [item["gate_id"] for item in results if item["severity"] == "SOFT" and not item["passed"]]
    if hard:
        return DatasetQuality(dataset_id, "FAIL", "QUARANTINED", hard, soft, metrics, results)
    if soft:
        return DatasetQuality(dataset_id, "PASS_WITH_WARNINGS", "DEGRADED", hard, soft, metrics, results)
    return DatasetQuality(dataset_id, "PASS", "READY", hard, soft, metrics, results)


def evaluate_universe(
    frame: pd.DataFrame,
    *,
    root: Path,
    lkg_frame: pd.DataFrame | None = None,
) -> DatasetQuality:
    cfg = _load_json(root / "config/quality_gates.json")["a_share_universe"]
    schema = _load_json(root / "schemas/a_share_universe.schema.json")
    results: list[dict[str, Any]] = []
    schema_errors = _schema_failures(frame, schema)
    _gate(results, gate_id="schema_valid", severity="HARD", actual=len(schema_errors), expected="0", passed=not schema_errors)

    row_count = len(frame)
    duplicate_count = int(frame.duplicated(subset=["as_of_date", "symbol"]).sum())
    symbol_ratio = float(frame["symbol"].astype(str).str.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)").mean()) if row_count else 0.0
    identity_ratio = float(frame[["symbol", "name", "exchange", "board"]].notna().all(axis=1).mean()) if row_count else 0.0
    industry_ratio = float(frame["industry_name"].notna().mean()) if row_count else 0.0
    list_date_ratio = float(frame["list_date"].notna().mean()) if row_count else 0.0
    lkg_ratio = row_count / len(lkg_frame) if lkg_frame is not None and len(lkg_frame) else 1.0

    _gate(results, gate_id="minimum_row_count", severity="HARD", actual=row_count, expected=f">={cfg['minimum_row_count']['value']}", passed=row_count >= cfg["minimum_row_count"]["value"])
    _gate(results, gate_id="duplicate_natural_key", severity="HARD", actual=duplicate_count, expected="0", passed=duplicate_count == 0)
    _gate(results, gate_id="symbol_valid_ratio", severity="HARD", actual=symbol_ratio, expected=f">={cfg['symbol_valid_ratio']['value']}", passed=symbol_ratio >= cfg["symbol_valid_ratio"]["value"])
    _gate(results, gate_id="required_identity_fill_ratio", severity="HARD", actual=identity_ratio, expected=f">={cfg['required_identity_fill_ratio']['value']}", passed=identity_ratio >= cfg["required_identity_fill_ratio"]["value"])
    _gate(results, gate_id="minimum_lkg_row_ratio", severity="HARD", actual=lkg_ratio, expected=f">={cfg['minimum_lkg_row_ratio']['value']}", passed=lkg_ratio >= cfg["minimum_lkg_row_ratio"]["value"])
    _gate(results, gate_id="industry_fill_ratio", severity="SOFT", actual=industry_ratio, expected=f">={cfg['industry_fill_ratio']['value']}", passed=industry_ratio >= cfg["industry_fill_ratio"]["value"])
    _gate(results, gate_id="listing_date_fill_ratio", severity="SOFT", actual=list_date_ratio, expected=f">={cfg['listing_date_fill_ratio']['value']}", passed=list_date_ratio >= cfg["listing_date_fill_ratio"]["value"])

    metrics = {
        "row_count": row_count,
        "duplicate_count": duplicate_count,
        "symbol_valid_ratio": symbol_ratio,
        "identity_fill_ratio": identity_ratio,
        "industry_fill_ratio": industry_ratio,
        "listing_date_fill_ratio": list_date_ratio,
        "lkg_row_ratio": lkg_ratio,
        "schema_error_examples": schema_errors,
    }
    return _finalize("a_share_universe", results, metrics)


def evaluate_snapshot(
    frame: pd.DataFrame,
    *,
    universe: pd.DataFrame,
    root: Path,
) -> DatasetQuality:
    cfg = _load_json(root / "config/quality_gates.json")["daily_market_snapshot"]
    schema = _load_json(root / "schemas/daily_market_snapshot.schema.json")
    results: list[dict[str, Any]] = []
    schema_errors = _schema_failures(frame, schema)
    _gate(results, gate_id="schema_valid", severity="HARD", actual=len(schema_errors), expected="0", passed=not schema_errors)

    row_count = len(frame)
    duplicate_count = int(frame.duplicated(subset=["as_of_date", "symbol"]).sum())
    coverage = len(set(frame["symbol"])) / len(set(universe["symbol"])) if len(universe) else 0.0
    traded = frame.loc[frame["data_status"] == "TRADED"].copy()
    positive_close_ratio = float((traded["close"] > 0).mean()) if len(traded) else 0.0
    negative_volume_rows = int((frame["volume_shares"].dropna() < 0).sum())
    negative_turnover_rows = int((frame["turnover_cny"].dropna() < 0).sum())
    reconciled = traded.loc[(traded["close"].notna()) & (traded["prev_close"].notna()) & (traded["prev_close"] > 0) & traded["pct_change"].notna()].copy()
    if len(reconciled):
        calculated = (reconciled["close"] / reconciled["prev_close"] - 1.0) * 100.0
        max_return_diff = float((calculated - reconciled["pct_change"]).abs().max())
    else:
        max_return_diff = float("inf")
    market_cap_ratio = float(frame["market_cap_cny"].notna().mean()) if row_count else 0.0
    valuation_ratio = float((frame["pe_ttm"].notna() | frame["pb"].notna()).mean()) if row_count else 0.0
    zero_turnover_ratio = float((frame["turnover_cny"].fillna(0) == 0).mean()) if row_count else 1.0
    max_abs_return = float(frame["pct_change"].dropna().abs().max()) if frame["pct_change"].notna().any() else 0.0

    _gate(results, gate_id="minimum_active_universe_coverage", severity="HARD", actual=coverage, expected=f">={cfg['minimum_active_universe_coverage']['value']}", passed=coverage >= cfg["minimum_active_universe_coverage"]["value"])
    _gate(results, gate_id="duplicate_natural_key", severity="HARD", actual=duplicate_count, expected="0", passed=duplicate_count == 0)
    _gate(results, gate_id="minimum_positive_close_ratio_for_traded_rows", severity="HARD", actual=positive_close_ratio, expected=f">={cfg['minimum_positive_close_ratio_for_traded_rows']['value']}", passed=positive_close_ratio >= cfg["minimum_positive_close_ratio_for_traded_rows"]["value"])
    _gate(results, gate_id="maximum_negative_volume_rows", severity="HARD", actual=negative_volume_rows, expected="0", passed=negative_volume_rows == 0)
    _gate(results, gate_id="maximum_negative_turnover_rows", severity="HARD", actual=negative_turnover_rows, expected="0", passed=negative_turnover_rows == 0)
    _gate(results, gate_id="return_reconciliation", severity="HARD", actual=max_return_diff, expected=f"<={cfg['return_reconciliation_tolerance_percentage_points']['value']}", passed=max_return_diff <= cfg["return_reconciliation_tolerance_percentage_points"]["value"])
    _gate(results, gate_id="market_cap_fill_ratio", severity="SOFT", actual=market_cap_ratio, expected=f">={cfg['market_cap_fill_ratio']['value']}", passed=market_cap_ratio >= cfg["market_cap_fill_ratio"]["value"])
    _gate(results, gate_id="valuation_fill_ratio", severity="SOFT", actual=valuation_ratio, expected=f">={cfg['valuation_fill_ratio']['value']}", passed=valuation_ratio >= cfg["valuation_fill_ratio"]["value"])
    _gate(results, gate_id="maximum_unexplained_absolute_return_pct", severity="SOFT", actual=max_abs_return, expected=f"<={cfg['maximum_unexplained_absolute_return_pct']['value']}", passed=max_abs_return <= cfg["maximum_unexplained_absolute_return_pct"]["value"])
    _gate(results, gate_id="maximum_zero_turnover_ratio", severity="SOFT", actual=zero_turnover_ratio, expected=f"<={cfg['maximum_zero_turnover_ratio']['value']}", passed=zero_turnover_ratio <= cfg["maximum_zero_turnover_ratio"]["value"])

    metrics = {
        "row_count": row_count,
        "universe_coverage_ratio": coverage,
        "traded_row_count": len(traded),
        "positive_close_ratio_for_traded_rows": positive_close_ratio,
        "negative_volume_rows": negative_volume_rows,
        "negative_turnover_rows": negative_turnover_rows,
        "maximum_return_reconciliation_difference_pp": None if max_return_diff == float("inf") else max_return_diff,
        "market_cap_fill_ratio": market_cap_ratio,
        "valuation_fill_ratio": valuation_ratio,
        "zero_turnover_ratio": zero_turnover_ratio,
        "maximum_absolute_return_pct": max_abs_return,
        "schema_error_examples": schema_errors,
    }
    return _finalize("daily_market_snapshot", results, metrics)
