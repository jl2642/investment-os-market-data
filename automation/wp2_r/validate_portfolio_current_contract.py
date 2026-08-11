#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# GitHub Actions invokes this validator directly as a script. Add the repository
# root before importing shared WP2-R logic so direct execution and pytest use the
# same canonical delta semantics.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.wp2_r.build_portfolio_current import (  # noqa: E402
    apply_confirmed_deltas,
    real_positions,
    simulation_positions,
    validate_delta_ledger,
)
from automation.wp2_r.finalize_account_summaries import pending_real_settlement_receivable  # noqa: E402


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


def validate_expected_economic_state(
    *,
    label: str,
    expected_rows: list[dict[str, Any]],
    current_payload: dict[str, Any],
) -> None:
    """Require Current to equal source state after authorized user deltas.

    This deliberately does not compare Current directly with the legacy source.
    A confirmed/applied user transaction is an authorized economic mutation; a
    disappearance, quantity change or cost change without such a delta remains
    a hard failure because it will not appear in ``expected_rows``.
    """
    expected = {row["security_id"]: row for row in expected_rows}
    current = {row["security_id"]: row for row in current_payload.get("holdings", [])}
    if set(expected) != set(current):
        raise AssertionError((f"{label}_SECURITY_SET_MISMATCH_AFTER_AUTHORIZED_DELTAS", sorted(expected), sorted(current)))

    for sid, exp in expected.items():
        row = current[sid]
        close(row.get("quantity"), exp.get("quantity"), 1e-6)
        close(row.get("available_quantity"), exp.get("available_quantity"), 1e-6)
        close(row.get("cost_basis"), exp.get("cost_basis"), 1e-4)
        if exp.get("unit_cost") is None:
            if row.get("unit_cost") is not None:
                raise AssertionError((f"{label}_UNIT_COST_EXPECTED_NULL", sid, row.get("unit_cost")))
        else:
            close(row.get("unit_cost"), exp.get("unit_cost"), 1e-8)


def expected_economic_states(
    real_source: dict[str, Any],
    sim_source: dict[str, Any],
    ledger: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], list[str]]:
    validate_delta_ledger(ledger)
    expected_real, real_applied = apply_confirmed_deltas(real_positions(real_source), ledger, "REAL")
    expected_sim, sim_applied = apply_confirmed_deltas(simulation_positions(sim_source), ledger, "SIMULATION")
    return expected_real, real_applied, expected_sim, sim_applied


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

    expected_real, real_applied, expected_sim, sim_applied = expected_economic_states(real_source, sim_source, ledger)
    validate_expected_economic_state(label="REAL", expected_rows=expected_real, current_payload=real)
    validate_expected_economic_state(label="SIM", expected_rows=expected_sim, current_payload=sim)
    validate_equity_compensation(real, equity)

    real_watermark = real.get("position_watermark", {})
    sim_watermark = sim.get("position_watermark", {})
    if real_watermark.get("applied_delta_ids", []) != real_applied:
        raise AssertionError(("REAL_APPLIED_DELTA_IDS_MISMATCH", real_watermark.get("applied_delta_ids"), real_applied))
    if sim_watermark.get("applied_delta_ids", []) != sim_applied:
        raise AssertionError(("SIM_APPLIED_DELTA_IDS_MISMATCH", sim_watermark.get("applied_delta_ids"), sim_applied))
    if int(real_watermark.get("applied_delta_count", 0)) != len(real_applied):
        raise AssertionError(("REAL_APPLIED_DELTA_COUNT_MISMATCH", real_watermark.get("applied_delta_count"), len(real_applied)))
    if int(sim_watermark.get("applied_delta_count", 0)) != len(sim_applied):
        raise AssertionError(("SIM_APPLIED_DELTA_COUNT_MISMATCH", sim_watermark.get("applied_delta_count"), len(sim_applied)))

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
    missing_marks = sorted(required_ids - set(mark_rows))
    if mark_status == "CURRENT_COMPLETE" and missing_marks:
        raise AssertionError(("MISSING_MARKS", missing_marks))
    if mark_status == "CURRENT_COMPLETE":
        bad_freshness = sorted(
            sid for sid in required_ids if mark_rows[sid].get("freshness_status") not in {"FRESH", "ACCEPTABLE_LAG"}
        )
        if bad_freshness:
            raise AssertionError(("STALE_REQUIRED_MARKS", bad_freshness))

    expected_user_mutations = len(real_applied) + len(sim_applied)
    if int(run.get("economic_transaction_mutations", 0)) != expected_user_mutations:
        raise AssertionError(("USER_DELTA_MUTATION_COUNT_MISMATCH", run.get("economic_transaction_mutations"), expected_user_mutations))
    if run.get("position_or_cost_mutations_from_reconciliation") != 0:
        raise AssertionError(("RECONCILIATION_MUTATED_POSITION_OR_COST", run.get("position_or_cost_mutations_from_reconciliation")))
    if run.get("orders") != 0:
        raise AssertionError(("ORDER_CREATED", run.get("orders")))

    real_summary = real.get("summary", {})
    real_source_summary = real_source.get("summary", {})
    real_position_value = sum(num(row.get("market_value")) for row in real.get("holdings", []))
    real_cash = num(real_source_summary.get("brokerage_available_cash"))
    real_exception = num(real_source_summary.get("broker_reconciliation_exception_amount"))
    pending_receivable = pending_real_settlement_receivable(ledger)
    close(real_summary.get("position_market_value"), real_position_value)
    close(real_summary.get("execution_cash_balance"), real_cash)
    close(real_summary.get("pending_settlement_receivable"), pending_receivable)
    if real_summary.get("pending_settlement_receivable_available_for_trading") is not False:
        raise AssertionError(("PENDING_SETTLEMENT_MISCLASSIFIED_AS_TRADING_CASH", real_summary.get("pending_settlement_receivable_available_for_trading")))
    close(real_summary.get("broker_reconciliation_exception_amount"), real_exception)
    close(real_summary.get("account_total_assets"), real_position_value + real_cash + pending_receivable + real_exception)

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
        "missing_marks": missing_marks,
        "real_holding_count": len(real.get("holdings", [])),
        "simulation_holding_count": len(sim.get("holdings", [])),
        "real_applied_delta_ids": real_applied,
        "simulation_applied_delta_ids": sim_applied,
        "real_pending_settlement_receivable": pending_receivable,
        "real_605090_quantity": next((row.get("quantity") for row in real.get("holdings", []) if code(row) == "605090"), None),
        "pending_605090_quantity": equity.get("current_recognition", {}).get("pending_entitlement", {}).get("quantity"),
        "mark_watermark": marks.get("data_watermark", {}).get("latest_mark_date"),
        "economic_transaction_mutations": expected_user_mutations,
        "market_driven_economic_mutations": 0,
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
