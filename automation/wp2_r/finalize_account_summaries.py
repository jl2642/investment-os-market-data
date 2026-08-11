#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def num(value: Any, default: float = 0.0) -> float:
    return default if value in (None, "") else float(value)


def round_money(value: float) -> float:
    return round(value, 6)


def pending_real_settlement_receivable(ledger: dict[str, Any]) -> float:
    total = 0.0
    for row in ledger.get("entries", []):
        if row.get("account") != "REAL":
            continue
        if row.get("action") != "SELL":
            continue
        if row.get("status") not in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"}:
            continue
        if row.get("settlement_status") != "PENDING_CASH_SETTLEMENT":
            continue
        total += num(row.get("net_settlement_amount"))
    return round_money(total)


def account_summary(
    *,
    account: str,
    current: dict[str, Any],
    execution_cash: float,
    historical_total_assets: float | None,
    historical_watermark: str | None,
    original_capital: float | None = None,
    reconciliation_exception: float = 0.0,
    reconciliation_exception_field: str | None = None,
    pending_settlement_receivable: float = 0.0,
) -> dict[str, Any]:
    holding_count = len(current.get("holdings", []))
    position_market_value = sum(num(row.get("market_value")) for row in current.get("holdings", []))
    position_cost_basis = sum(num(row.get("cost_basis")) for row in current.get("holdings", []))
    open_unrealized_pnl = position_market_value - position_cost_basis
    total_assets = position_market_value + execution_cash + pending_settlement_receivable + reconciliation_exception
    comparison = None
    if historical_total_assets is not None:
        comparison = round_money(total_assets - historical_total_assets)

    summary: dict[str, Any] = {
        "holding_count": holding_count,
        "position_market_value": round_money(position_market_value),
        "position_cost_basis": round_money(position_cost_basis),
        "open_unrealized_pnl": round_money(open_unrealized_pnl),
        "execution_cash_balance": round_money(execution_cash),
        "pending_settlement_receivable": round_money(pending_settlement_receivable),
        "pending_settlement_receivable_available_for_trading": False,
        "account_total_assets": round_money(total_assets),
        "cash_semantics": (
            "BROKER_EXECUTION_BALANCE_PLUS_SEPARATE_UNAVAILABLE_SETTLEMENT_RECEIVABLE_EXTERNAL_LIQUIDITY_EXCLUDED"
            if account == "REAL"
            else "SIMULATION_LEDGER_AVAILABLE_CASH"
        ),
        "historical_wp2_3_total_assets": historical_total_assets,
        "historical_wp2_3_watermark": historical_watermark,
        "difference_vs_historical_wp2_3": comparison,
        "reconciliation_status": (
            "CURRENT_AUTOMATED_MARK_WATERMARK_WITH_PRESERVED_SOURCE_EXCEPTION_NOT_DIRECTLY_COMPARABLE_TO_HISTORICAL_WP2_3"
            if comparison not in (None, 0.0)
            else "TIED_OR_NO_HISTORICAL_COMPARISON"
        ),
        "reconciliation_explanation": (
            "WP2-R uses the current automated listed-security close and official fund NAV set. "
            "Historical WP2-3 used its own accepted mixed watermark. Persistent source-level "
            "unallocated reconciliation exceptions are preserved explicitly and are never forced "
            "into a security, quantity, cost or cash mutation. Confirmed sale proceeds that have "
            "not settled are carried as a separate receivable and are never treated as executable cash."
        ),
    }
    if reconciliation_exception_field:
        summary[reconciliation_exception_field] = round_money(reconciliation_exception)
        summary["reported_total_reconciliation_exception_preserved"] = True
    if original_capital is not None:
        summary["original_capital"] = round_money(original_capital)
        summary["account_total_pnl"] = round_money(total_assets - original_capital)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_r/config.json")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    cfg = read(root / args.config)
    outputs = cfg["output_paths"]

    real_source = read(root / cfg["source_paths"]["real_legacy"])
    sim_source = read(root / cfg["source_paths"]["simulation_legacy"])
    delta_ledger = read(root / cfg["source_paths"]["delta_ledger"])
    execution_register = read(root / "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json")
    real = read(root / outputs["real_positions"])
    sim = read(root / outputs["simulation_positions"])
    marks = read(root / outputs["portfolio_marks"])
    run = read(root / outputs["run_current"])

    real_source_summary = real_source.get("summary", {})
    sim_source_summary = sim_source.get("summary", {})
    real_cash = num(real_source_summary.get("brokerage_available_cash"))
    real_pending_receivable = pending_real_settlement_receivable(delta_ledger)
    sim_cash = num(sim_source_summary.get("available_cash"))
    real_reconciliation_exception = num(real_source_summary.get("broker_reconciliation_exception_amount"))
    sim_snapshot_timing_exception = num(sim_source_summary.get("market_value_reconciliation_exception_amount"))
    sim_source_total_assets = num(sim_source_summary.get("total_assets"))
    sim_source_total_pnl = num(sim_source_summary.get("total_pnl"))
    original_capital = sim_source_total_assets - sim_source_total_pnl

    wp2_3 = execution_register.get("wp2_3", {})
    real_hist = wp2_3.get("real_account", {})
    sim_hist = wp2_3.get("simulation", {})

    real["summary"] = account_summary(
        account="REAL",
        current=real,
        execution_cash=real_cash,
        historical_total_assets=num(real_hist.get("total_assets")) if real_hist.get("total_assets") is not None else None,
        historical_watermark=real_hist.get("watermark"),
        reconciliation_exception=real_reconciliation_exception,
        reconciliation_exception_field="broker_reconciliation_exception_amount",
        pending_settlement_receivable=real_pending_receivable,
    )
    sim["summary"] = account_summary(
        account="SIMULATION",
        current=sim,
        execution_cash=sim_cash,
        historical_total_assets=num(sim_hist.get("total_assets")) if sim_hist.get("total_assets") is not None else None,
        historical_watermark=sim_hist.get("watermark"),
        original_capital=original_capital,
    )
    sim["summary"]["source_snapshot_timing_exception_amount"] = sim_snapshot_timing_exception
    sim["summary"]["source_snapshot_timing_exception_policy"] = (
        "DISCLOSE_ONLY_NOT_CARRIED_INTO_LATER_AUTOMATED_MARK_TOTALS"
    )

    run["account_summaries_finalized_at"] = datetime.now(timezone.utc).isoformat()
    run["real_account_total_assets"] = real["summary"]["account_total_assets"]
    run["real_execution_cash_balance"] = real["summary"]["execution_cash_balance"]
    run["real_pending_settlement_receivable"] = real_pending_receivable
    run["real_difference_vs_historical_wp2_3"] = real["summary"]["difference_vs_historical_wp2_3"]
    run["real_reconciliation_exception_amount"] = real_reconciliation_exception
    run["simulation_total_assets"] = sim["summary"]["account_total_assets"]
    run["simulation_available_cash"] = sim["summary"]["execution_cash_balance"]
    run["simulation_total_pnl"] = sim["summary"]["account_total_pnl"]
    run["simulation_difference_vs_historical_wp2_3"] = sim["summary"]["difference_vs_historical_wp2_3"]
    run["simulation_source_snapshot_timing_exception_amount"] = sim_snapshot_timing_exception
    run["historical_baseline_comparison_policy"] = "DISCLOSE_DIFFERENCE_DO_NOT_FORCE_RECONCILIATION"
    run["reported_total_reconciliation_exception_policy"] = "PRESERVE_PERSISTENT_REAL_EXCEPTION; DISCLOSE_SIMULATION_SECOND_LEVEL_TIMING_EXCEPTION"
    run["pending_settlement_policy"] = "COUNT_IN_TOTAL_ASSETS_AS_RECEIVABLE; EXCLUDE_FROM_EXECUTION_CASH_UNTIL_USER_CONFIRMS_SETTLEMENT"
    run["position_or_cost_mutations_from_reconciliation"] = 0

    write(root / outputs["real_positions"], real)
    write(root / outputs["simulation_positions"], sim)
    write(root / outputs["run_current"], run)

    acceptance = read(root / outputs["acceptance"])
    acceptance["account_summary_controls"] = {
        "execution_cash_included_in_account_total_assets": True,
        "pending_settlement_receivable_included_in_real_total_assets": True,
        "pending_settlement_receivable_excluded_from_execution_cash": True,
        "real_pending_settlement_receivable": real_pending_receivable,
        "external_real_account_liquidity_excluded": True,
        "historical_wp2_3_preserved_as_non_comparable_baseline": True,
        "reported_total_reconciliation_exceptions_preserved": True,
        "real_reconciliation_exception_amount": real_reconciliation_exception,
        "simulation_source_snapshot_timing_exception_amount": sim_snapshot_timing_exception,
        "real_reported_total_formula": "POSITION_MARKET_VALUE_PLUS_EXECUTION_CASH_PLUS_PENDING_SETTLEMENT_RECEIVABLE_PLUS_UNALLOCATED_EXCEPTION",
        "simulation_automated_mark_total_formula": "POSITION_MARKET_VALUE_PLUS_EXECUTION_CASH",
        "simulation_snapshot_exception_policy": "DISCLOSE_ONLY_NOT_CARRIED_INTO_LATER_AUTOMATED_MARK_TOTALS",
        "forced_reconciliation_mutations": 0,
        "real_difference_disclosed": real["summary"]["difference_vs_historical_wp2_3"],
        "simulation_difference_disclosed": sim["summary"]["difference_vs_historical_wp2_3"],
    }
    for key, path in outputs.items():
        if key == "acceptance":
            continue
        payload = read(root / path)
        acceptance.setdefault("outputs", {})[key] = {"path": path, "semantic_hash": digest(payload)}
    acceptance["marks_status"] = marks["status"]
    acceptance["trade_authority"] = "NONE"
    write(root / outputs["acceptance"], acceptance)

    print(
        json.dumps(
            {
                "real_total_assets": real["summary"]["account_total_assets"],
                "real_execution_cash": real["summary"]["execution_cash_balance"],
                "real_pending_settlement_receivable": real_pending_receivable,
                "real_reconciliation_exception": real_reconciliation_exception,
                "real_historical_difference": real["summary"]["difference_vs_historical_wp2_3"],
                "simulation_total_assets": sim["summary"]["account_total_assets"],
                "simulation_source_snapshot_timing_exception": sim_snapshot_timing_exception,
                "simulation_total_pnl": sim["summary"]["account_total_pnl"],
                "simulation_historical_difference": sim["summary"]["difference_vs_historical_wp2_3"],
                "forced_mutations": 0,
                "trade_authority": "NONE",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
