#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: Any, default: float = 0.0) -> float:
    return default if value in (None, "") else float(value)


def close(actual: Any, expected: Any, tolerance: float = 1e-6) -> None:
    if abs(num(actual) - num(expected)) > tolerance:
        raise AssertionError(("NUMERIC_MISMATCH", actual, expected, tolerance))


def authority_values(value: Any) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "trade_authority":
                out.append(item)
            out.extend(authority_values(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(authority_values(item))
    return out


def require_none_authority(label: str, payload: Any) -> None:
    values = authority_values(payload)
    if values and set(values) != {"NONE"}:
        raise AssertionError(("AUTHORITY_VIOLATION", label, values))


def code(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("security_code") or row.get("security_id", "").split(".")[0]).zfill(6)


def validate_schema(root: Path, schema_path: str, data_path: str) -> None:
    schema = read(root / schema_path)
    data = read(root / data_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda err: list(err.path))
    if errors:
        raise AssertionError(("SCHEMA_FAILURE", data_path, [err.message for err in errors]))


def validate_real_economic_state(real_source: dict[str, Any], real: dict[str, Any]) -> None:
    source = {str(row["code"]).zfill(6): row for row in real_source.get("holdings", [])}
    current = {code(row): row for row in real.get("holdings", [])}
    if set(source) != set(current):
        raise AssertionError(("REAL_SECURITY_SET_CHANGED", sorted(source), sorted(current)))
    for sec, src in source.items():
        row = current[sec]
        quantity = num(src.get("quantity_or_shares"))
        if abs(num(row.get("quantity")) - quantity) > 1e-6:
            raise AssertionError(("REAL_QUANTITY_CHANGED", sec, row.get("quantity"), quantity))
        if abs(num(row.get("available_quantity")) - quantity) > 1e-6:
            raise AssertionError(("REAL_AVAILABLE_QUANTITY_CHANGED", sec, row.get("available_quantity"), quantity))
        source_cost = num(src.get("cost_price_or_cost"))
        if src.get("asset_class") == "BOND_FUND":
            if abs(num(row.get("cost_basis")) - source_cost) > 1e-4:
                raise AssertionError(("REAL_FUND_COST_BASIS_CHANGED", sec, row.get("cost_basis"), source_cost))
            if quantity and abs(num(row.get("unit_cost")) - source_cost / quantity) > 1e-8:
                raise AssertionError(("REAL_FUND_UNIT_COST_CHANGED", sec, row.get("unit_cost"), source_cost / quantity))
        else:
            if abs(num(row.get("unit_cost")) - source_cost) > 1e-8:
                raise AssertionError(("REAL_UNIT_COST_CHANGED", sec, row.get("unit_cost"), source_cost))
            if abs(num(row.get("cost_basis")) - source_cost * quantity) > 1e-4:
                raise AssertionError(("REAL_COST_BASIS_CHANGED", sec, row.get("cost_basis"), source_cost * quantity))


def validate_sim_economic_state(sim_source: dict[str, Any], sim: dict[str, Any]) -> None:
    source = {str(row["security_code"]).zfill(6): row for row in sim_source.get("holdings", [])}
    current = {code(row): row for row in sim.get("holdings", [])}
    if set(source) != set(current):
        raise AssertionError(("SIM_SECURITY_SET_CHANGED", sorted(source), sorted(current)))
    for sec, src in source.items():
        row = current[sec]
        quantity = num(src.get("quantity"))
        if abs(num(row.get("quantity")) - quantity) > 1e-6:
            raise AssertionError(("SIM_QUANTITY_CHANGED", sec, row.get("quantity"), quantity))
        expected_available = num(src.get("available_quantity"), quantity)
        if abs(num(row.get("available_quantity")) - expected_available) > 1e-6:
            raise AssertionError(("SIM_AVAILABLE_QUANTITY_CHANGED", sec, row.get("available_quantity"), expected_available))
        if abs(num(row.get("unit_cost")) - num(src.get("cost_price"))) > 1e-8:
            raise AssertionError(("SIM_UNIT_COST_CHANGED", sec, row.get("unit_cost"), src.get("cost_price")))
        if abs(num(row.get("cost_basis")) - num(src.get("cost_price")) * quantity) > 1e-4:
            raise AssertionError(("SIM_COST_BASIS_CHANGED", sec, row.get("cost_basis"), num(src.get("cost_price")) * quantity))


def validate_equity_compensation(real: dict[str, Any], equity: dict[str, Any]) -> None:
    by_code = {code(row): row for row in real.get("holdings", [])}
    current = equity.get("current_recognition", {})
    ordinary = current.get("ordinary_share_position", {})
    if "605090" in by_code and ordinary:
        if abs(num(ordinary.get("quantity")) - num(by_code["605090"].get("quantity"))) > 1e-6:
            raise AssertionError(("605090_EQUITY_RECOGNITION_MISMATCH", ordinary.get("quantity"), by_code["605090"].get("quantity")))
        if ordinary.get("included_in_real_account_current") is not True:
            raise AssertionError("605090 ordinary share recognition must be included")
    pending = current.get("pending_entitlement", {})
    if pending:
        if pending.get("included_in_real_account_current") is not False:
            raise AssertionError("pending entitlement entered real current")
        if pending.get("included_in_total_assets") is not False:
            raise AssertionError("pending entitlement entered total assets")
        if abs(num(pending.get("market_value"))) > 1e-6:
            raise AssertionError(("PENDING_ENTITLEMENT_NONZERO_VALUE", pending.get("market_value")))
    technical = current.get("technical_entitlement_codes", [])
    technical_codes = {str(row.get("code")) for row in technical}
    if technical_codes & set(by_code):
        raise AssertionError(("TECHNICAL_ENTITLEMENT_DOUBLE_COUNT", sorted(technical_codes & set(by_code))))
    if any(abs(num(row.get("market_value"))) > 1e-6 for row in technical):
        raise AssertionError("technical entitlement has non-zero market value")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--require-fresh", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    cfg = read(root / "automation/wp2_r/config.json")
    source = cfg["source_paths"]
    output = cfg["output_paths"]

    schema_pairs = [
        ("investment_os_runtime/20_SCHEMAS_AND_INTERFACES/portfolio_positions_current.schema.json", output["real_positions"]),
        ("investment_os_runtime/20_SCHEMAS_AND_INTERFACES/portfolio_positions_current.schema.json", output["simulation_positions"]),
        ("investment_os_runtime/20_SCHEMAS_AND_INTERFACES/portfolio_marks_current.schema.json", output["portfolio_marks"]),
        ("investment_os_runtime/20_SCHEMAS_AND_INTERFACES/transaction_delta_ledger.schema.json", source["delta_ledger"]),
    ]
    for schema_path, data_path in schema_pairs:
        validate_schema(root, schema_path, data_path)

    real_source = read(root / source["real_legacy"])
    sim_source = read(root / source["simulation_legacy"])
    ledger = read(root / source["delta_ledger"])
    real = read(root / output["real_positions"])
    sim = read(root / output["simulation_positions"])
    marks = read(root / output["portfolio_marks"])
    run = read(root / output["run_current"])
    acceptance = read(root / output["acceptance"])
    equity = read(root / "investment_os_runtime/30_STATE_CURRENT/12_EQUITY_COMPENSATION/EQUITY_COMPENSATION_CURRENT.json")

    for label, payload in {
        "real_source": real_source,
        "simulation_source": sim_source,
        "delta": ledger,
        "real": real,
        "simulation": sim,
        "marks": marks,
        "run": run,
        "acceptance": acceptance,
        "equity": equity,
    }.items():
        require_none_authority(label, payload)

    validate_real_economic_state(real_source, real)
    validate_sim_economic_state(sim_source, sim)
    validate_equity_compensation(real, equity)

    if marks.get("automatic_position_mutations") != 0:
        raise AssertionError(("MARK_REFRESH_MUTATED_POSITIONS", marks.get("automatic_position_mutations")))
    mark_status = marks.get("status")
    if args.require_fresh and mark_status != "CURRENT_COMPLETE":
        raise AssertionError(("MARKS_NOT_CURRENT_COMPLETE", mark_status))
    if mark_status not in {"CURRENT_COMPLETE", "LKG_FALLBACK_OR_INCOMPLETE_BLOCKED"}:
        raise AssertionError(("UNKNOWN_MARK_STATUS", mark_status))
    if mark_status != "CURRENT_COMPLETE":
        if run.get("portfolio_marks_fresh") is not False:
            raise AssertionError(("STALE_MARKS_FALSE_READY_CLAIM", "portfolio_marks_fresh", run.get("portfolio_marks_fresh")))
        if run.get("wp4b_position_level_fit_ready") is not False:
            raise AssertionError(("STALE_MARKS_FALSE_READY_CLAIM", "wp4b_position_level_fit_ready", run.get("wp4b_position_level_fit_ready")))

    required_ids = {row["security_id"] for row in real.get("holdings", []) + sim.get("holdings", [])}
    mark_rows = {row["security_id"]: row for row in marks.get("marks", [])}
    if not required_ids <= set(mark_rows):
        raise AssertionError(("MISSING_MARKS", sorted(required_ids - set(mark_rows))))
    if mark_status == "CURRENT_COMPLETE":
        bad_freshness = sorted(
            sid for sid in required_ids if mark_rows[sid].get("freshness_status") not in {"FRESH", "ACCEPTABLE_LAG"}
        )
        if bad_freshness:
            raise AssertionError(("STALE_REQUIRED_MARKS", bad_freshness))

    if run.get("economic_transaction_mutations") != 0:
        raise AssertionError(("ECONOMIC_TRANSACTION_MUTATION", run.get("economic_transaction_mutations")))
    if run.get("position_or_cost_mutations_from_reconciliation") != 0:
        raise AssertionError(("RECONCILIATION_MUTATED_POSITION_OR_COST", run.get("position_or_cost_mutations_from_reconciliation")))
    if run.get("orders") != 0:
        raise AssertionError(("ORDER_CREATED", run.get("orders")))

    real_summary = real.get("summary", {})
    real_source_summary = real_source.get("summary", {})
    real_position_value = sum(num(row.get("market_value")) for row in real.get("holdings", []))
    real_cash = num(real_source_summary.get("brokerage_available_cash"))
    real_exception = num(real_source_summary.get("broker_reconciliation_exception_amount"))
    close(real_summary.get("position_market_value"), real_position_value)
    close(real_summary.get("execution_cash_balance"), real_cash)
    close(real_summary.get("broker_reconciliation_exception_amount"), real_exception)
    close(real_summary.get("account_total_assets"), real_position_value + real_cash + real_exception)

    sim_summary = sim.get("summary", {})
    sim_source_summary = sim_source.get("summary", {})
    sim_position_value = sum(num(row.get("market_value")) for row in sim.get("holdings", []))
    sim_cash = num(sim_source_summary.get("available_cash"))
    close(sim_summary.get("position_market_value"), sim_position_value)
    close(sim_summary.get("execution_cash_balance"), sim_cash)
    close(sim_summary.get("account_total_assets"), sim_position_value + sim_cash)
    close(sim_summary.get("source_snapshot_timing_exception_amount"), sim_source_summary.get("market_value_reconciliation_exception_amount"))

    controls = acceptance.get("account_summary_controls", {})
    if controls.get("forced_reconciliation_mutations") != 0:
        raise AssertionError(("FORCED_RECONCILIATION_MUTATION", controls.get("forced_reconciliation_mutations")))
    if acceptance.get("trade_authority") != "NONE":
        raise AssertionError(("ACCEPTANCE_AUTHORITY_VIOLATION", acceptance.get("trade_authority")))
    if acceptance.get("wp5_unblocked") is not False:
        raise AssertionError(("WP5_MUST_REMAIN_BLOCKED", acceptance.get("wp5_unblocked")))

    entries = ledger.get("entries", [])
    allowed = {"PENDING_USER_CONFIRMATION", "CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT", "REJECTED"}
    invalid = [row.get("delta_id") for row in entries if row.get("status") not in allowed]
    if invalid:
        raise AssertionError(("INVALID_DELTA_STATUS", invalid))

    print(json.dumps({
        "status": "PASS",
        "require_fresh": args.require_fresh,
        "marks_status": mark_status,
        "real_holding_count": len(real.get("holdings", [])),
        "simulation_holding_count": len(sim.get("holdings", [])),
        "real_605090_quantity": next((row.get("quantity") for row in real.get("holdings", []) if code(row) == "605090"), None),
        "pending_605090_quantity": equity.get("current_recognition", {}).get("pending_entitlement", {}).get("quantity"),
        "mark_watermark": marks.get("data_watermark", {}).get("latest_mark_date"),
        "economic_transaction_mutations": 0,
        "reconciliation_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}".replace("\n", " ")
        print(f"::error title=WP2-R Canonical-relative contract failure::{message}")
        raise
