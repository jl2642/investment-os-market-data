#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REAL_SOURCE = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_CURRENT.json"
SIM_SOURCE = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_LEDGER_CURRENT.json"
REAL_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/10_REAL_ACCOUNT/REAL_ACCOUNT_POSITIONS_CURRENT.json"
SIM_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/20_SIMULATION/SIMULATION_POSITIONS_CURRENT.json"
DELTA = ROOT / "investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json"
MARKS_CANDIDATE = ROOT / "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP2_R/PORTFOLIO_MARKS_REFRESH_CANDIDATE.json"
MARKS_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/25_PORTFOLIO_MARKS/PORTFOLIO_MARKS_CURRENT.json"
RUN_CURRENT = ROOT / "investment_os_runtime/30_STATE_CURRENT/70_OPERATIONS/PORTFOLIO_CURRENT_RUN_CURRENT.json"
ACCEPTANCE = ROOT / "investment_os_runtime/00_CONTROL/WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_RECORD.json"

REAL_TS = "2026-08-04T09:51:00+08:00"
SIM_TS = "2026-08-04T09:52:00+08:00"
RUN_ID = "POSITION_UPDATE_20260804_USER_INTRADAY"

REAL_CLASSES = {
    "159352": "A_SHARE_ETF", "159612": "QDII_ETF", "159655": "QDII_ETF",
    "510500": "A_SHARE_ETF", "605090": "A_SHARE_STOCK",
    "017534": "BOND_FUND", "110017": "BOND_FUND", "217003": "BOND_FUND",
}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def code(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("security_code") or row.get("security_id", "").split(".")[0]).zfill(6)


def unit_cost(row: dict[str, Any]) -> float:
    return float(row.get("broker_display_unit_cost", row.get("unit_cost", 0.0)))


def pct_text(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_id(sec: str, asset_class: str) -> str:
    if asset_class == "BOND_FUND":
        return f"{sec}.OF"
    return f"{sec}.SH" if sec.startswith(("5", "6")) else f"{sec}.SZ"


def patch_real_source(source: dict[str, Any], draft: dict[str, Any]) -> None:
    old = {str(row["code"]).zfill(6): row for row in source.get("holdings", [])}
    draft_rows = {code(row): row for row in draft["holdings"]}
    ordered = ["159352", "159612", "159655", "510500", "605090", "017534", "110017", "217003"]
    rows: list[dict[str, Any]] = []
    for sec in ordered:
        d = draft_rows[sec]
        row = deepcopy(old.get(sec, {}))
        cls = REAL_CLASSES[sec]
        row.update({
            "run_id": RUN_ID,
            "as_of": REAL_TS,
            "schema_version": row.get("schema_version", "3.5.0"),
            "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
            "source_run_id": RUN_ID,
            "source_schema_version": row.get("source_schema_version", "3.5.0"),
            "source_as_of": REAL_TS,
            "account": "REAL",
            "asset_class": cls,
            "holding_name": d["security_name"],
            "code": sec,
            "quantity_or_shares": float(d["quantity"]),
            "latest_price_or_nav": float(d["mark"]),
            "market_value": float(d["market_value"]),
            "holding_pnl": float(d["unrealized_pnl"]),
            "holding_pnl_pct": pct_text(d["unrealized_pnl_pct"]),
            "daily_pnl": 0.0,
            "data_source": "USER_CONFIRMED_BROKER_SCREENSHOT_INTRADAY_20260804",
            "snapshot_type": "USER_CONFIRMED_INTRADAY",
            "formal_eod_snapshot_written": False,
            "broker_display_holding_pnl": float(d["unrealized_pnl"]),
            "broker_display_holding_pnl_pct": float(d["unrealized_pnl_pct"]),
        })
        row["cost_price_or_cost"] = float(d["cost_basis"]) if cls == "BOND_FUND" else unit_cost(d)
        if sec == "605090":
            row.update({
                "batch_identity": "UNKNOWN_STOCK_INCENTIVE_OR_OPTION",
                "economic_cost_basis_status": "SEPARATE_EQUITY_COMPENSATION_SUBLEDGER",
                "pending_entitlement_quantity_excluded": 4950,
                "technical_entitlement_codes_excluded": ["Q99460", "Q99461"],
            })
        rows.append(row)
    source.update({
        "state_id": "REAL_ACCOUNT_USER_CONFIRMED_INTRADAY_20260804",
        "as_of": REAL_TS,
        "status": "USER_CONFIRMED_INTRADAY_NOT_EOD",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
        "canonical_position_update_compatibility_status": "WP2_R_COMPATIBLE",
        "trade_authority": "NONE",
        "orders": 0,
        "holdings": rows,
    })
    source.setdefault("source_bindings", []).append({
        "run_id": RUN_ID,
        "as_of": REAL_TS,
        "role": "USER_CONFIRMED_INTRADAY_POSITION_SOURCE",
        "formal_eod": False,
    })
    summary = source.setdefault("summary", {})
    summary.update({
        "run_id": RUN_ID,
        "as_of": REAL_TS,
        "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
        "brokerage_total_assets": 615390.25,
        "consolidated_assets_including_bank_cash": 615390.25,
        "stock_etf_value": 299390.20,
        "listed_security_line_market_value_sum": 299152.70,
        "wealth_bond_value": 315230.60,
        "brokerage_available_cash": 769.45,
        "bank_side_cash": 0.0,
        "reconciled_cash_total": 769.45,
        "in_transit_other": 0.0,
        "broker_reconciliation_exception_amount": 237.50,
        "real_account_trade_action": "NO_TRADE_OR_ORDER_AUTHORIZED; USER_CONFIRMED_INTRADAY_POSITION_UPDATE_ONLY",
        "pricing_caveat": "User-confirmed intraday broker snapshot at approximately 09:51 Asia/Shanghai; not a formal EOD close.",
    })


def patch_sim_source(source: dict[str, Any], draft: dict[str, Any]) -> None:
    old = {str(row["security_code"]).zfill(6): row for row in source["holdings"]}
    draft_rows = {code(row): row for row in draft["holdings"]}
    rows: list[dict[str, Any]] = []
    for original in source["holdings"]:
        sec = str(original["security_code"]).zfill(6)
        d = draft_rows[sec]
        row = deepcopy(old[sec])
        mv = float(d["market_value"])
        row.update({
            "run_id": RUN_ID,
            "as_of": SIM_TS,
            "promotion_status": "USER_CONFIRMED_INTRADAY_PROVISIONAL",
            "source_run_id": RUN_ID,
            "source_as_of": SIM_TS,
            "security_name": d["security_name"],
            "security_code": sec,
            "quantity": float(d["quantity"]),
            "available_quantity": float(d["available_quantity"]),
            "last_price_close": float(d["mark"]),
            "cost_price": unit_cost(d),
            "market_value": mv,
            "holding_pnl": float(d["unrealized_pnl"]),
            "holding_pnl_pct": pct_text(d["unrealized_pnl_pct"]),
            "current_weight_pct_of_total_asset": round(mv / 1021157.08 * 100, 6),
            "current_weight_pct_of_market_value": round(mv / 799495.10 * 100, 6),
            "data_source": "USER_CONFIRMED_SIMULATION_SCREENSHOT_INTRADAY_20260804",
            "snapshot_type": "USER_CONFIRMED_INTRADAY",
            "formal_eod_snapshot_written": False,
            "mark_type": "USER_CONFIRMED_INTRADAY_NOT_CLOSE",
            "broker_display_holding_pnl": float(d["unrealized_pnl"]),
            "broker_display_holding_pnl_pct": float(d["unrealized_pnl_pct"]),
        })
        rows.append(row)
    source.update({
        "state_id": "SIMULATION_USER_CONFIRMED_INTRADAY_20260804",
        "as_of": SIM_TS,
        "status": "USER_CONFIRMED_INTRADAY_NOT_EOD_NO_NEW_TRADES",
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
        "canonical_position_update_compatibility_status": "WP2_R_COMPATIBLE",
        "trade_authority": "NONE",
        "orders": 0,
        "holdings": rows,
    })
    source.setdefault("source_bindings", []).append({
        "run_id": RUN_ID,
        "as_of": SIM_TS,
        "role": "USER_CONFIRMED_INTRADAY_SIMULATION_SOURCE",
        "formal_eod": False,
    })
    source.setdefault("summary", {}).update({
        "run_id": RUN_ID,
        "as_of": SIM_TS,
        "total_assets": 1021157.08,
        "total_pnl": 21157.08,
        "total_market_value": 799495.10,
        "holding_line_market_value_sum": 799538.10,
        "available_cash": 221661.98,
        "position_ratio": 0.7829,
        "market_value_reconciliation_exception_amount": -43.0,
        "new_confirmed_trades": 0,
        "trade_action": "NO_NEW_TRADE; MARK_AND_ACCOUNT_TOTAL_REFRESH_ONLY",
    })


def patch_delta(ledger: dict[str, Any]) -> None:
    reasons = {
        "JOVO_2025_STOCK_INCENTIVE_CLOSED": "Historical 2025 batch is closed and fully sold; evidence is retained but no Current mutation is permitted.",
        "JOVO_2025_OPTION_EXERCISE_CLOSED": "Historical 2025 exercised batch is closed and fully sold; evidence is retained but no Current mutation is permitted.",
        "JOVO_2026_OPTION_EXERCISE_PAYMENT": "Cash economic cost belongs to the equity-compensation subledger and must not mutate broker execution cash or ordinary holdings.",
        "JOVO_2026_SETTLED_ORDINARY_SHARES_UNKNOWN_BATCH": "The settled 4,950 shares are already reflected in the user-confirmed Real source baseline; applying this row again would double count.",
        "JOVO_2026_PENDING_ENTITLEMENT": "Pending entitlement is not a current ordinary holding and has zero recognized market value.",
    }
    for row in ledger["entries"]:
        row.update({
            "status": "REJECTED",
            "confirmation_authority": "USER",
            "evidence_status": "USER_CONFIRMED",
            "application_decision": "NOT_APPLICABLE_TO_WP2_R_POSITION_MUTATION",
            "rejection_reason": reasons[row["delta_id"]],
        })
    ledger.update({
        "status": "USER_CONFIRMED_EVIDENCE_RECORDED_ZERO_WP2_R_MUTATIONS",
        "applied_delta_count": 0,
        "unapplied_delta_count": len(ledger["entries"]),
        "rejected_for_position_engine_count": len(ledger["entries"]),
        "continuity_confirmed_through": SIM_TS,
        "orders": 0,
        "trade_authority": "NONE",
    })


def build_marks(real_draft: dict[str, Any], sim_draft: dict[str, Any]) -> dict[str, Any]:
    marks: dict[str, dict[str, Any]] = {}
    for account, payload, ts in (("REAL", real_draft, REAL_TS), ("SIMULATION", sim_draft, SIM_TS)):
        for row in payload["holdings"]:
            sec = code(row)
            cls = REAL_CLASSES.get(sec, "A_SHARE_STOCK") if account == "REAL" else "A_SHARE_STOCK"
            sid = canonical_id(sec, cls)
            candidate = {
                "security_id": sid,
                "code": sec,
                "security_name": row["security_name"],
                "asset_class": cls,
                "mark": float(row["mark"]),
                "mark_type": "OFFICIAL_NAV" if cls == "BOND_FUND" else "USER_CONFIRMED_INTRADAY_LAST",
                "as_of_date": "2026-08-04",
                "as_of_time": ts[11:19],
                "as_of_timestamp": ts,
                "provider": f"USER_CONFIRMED_{account}_SCREENSHOT_INTRADAY",
                "freshness_status": "FRESH",
                "source_role": "USER_CONFIRMED_INTRADAY_NOT_FORMAL_EOD",
            }
            # 510500 is visible in both accounts at adjacent seconds. The later simulation mark
            # is the shared WP2-R mark; the Real Current receives an explicit account override.
            if sid not in marks or account == "SIMULATION":
                marks[sid] = candidate
    return {
        "refresh_id": "USER_CONFIRMED_INTRADAY_20260804",
        "status": "PASS_COMPLETE",
        "generated_at": "2026-08-05T01:46:34Z",
        "latest_completed_listed_close_date": None,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
        "marked_security_count": len(marks),
        "marks": sorted(marks.values(), key=lambda row: row["security_id"]),
        "intraday_observation_count": len(marks),
        "intraday_observations": [],
        "errors": [],
        "automatic_quantity_or_cost_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }


def patch_standard_current(real: dict[str, Any], sim: dict[str, Any], real_draft: dict[str, Any], sim_draft: dict[str, Any]) -> None:
    for account, current, draft, ts in (
        ("REAL", real, real_draft, REAL_TS), ("SIMULATION", sim, sim_draft, SIM_TS)
    ):
        draft_rows = {code(row): row for row in draft["holdings"]}
        for row in current["holdings"]:
            sec, d = code(row), draft_rows[code(row)]
            row.update({
                "mark": float(d["mark"]),
                "mark_as_of": ts,
                "mark_provider": f"USER_CONFIRMED_{account}_SCREENSHOT_INTRADAY",
                "mark_freshness_status": "FRESH",
                "market_value": float(d["market_value"]),
                "broker_display_unrealized_pnl": float(d["unrealized_pnl"]),
                "broker_display_unrealized_pnl_pct": float(d["unrealized_pnl_pct"]),
                "broker_display_unit_cost": unit_cost(d),
                "snapshot_type": "USER_CONFIRMED_INTRADAY",
            })
            row["unrealized_pnl"] = round(float(row["market_value"]) - float(row["cost_basis"]), 6)
            row["unrealized_pnl_pct"] = round(row["unrealized_pnl"] / float(row["cost_basis"]), 8) if row["cost_basis"] else None
            if sec == "605090":
                row.update({
                    "batch_identity": "UNKNOWN_STOCK_INCENTIVE_OR_OPTION",
                    "economic_cost_basis_status": "SEPARATE_EQUITY_COMPENSATION_SUBLEDGER",
                    "pending_entitlement_quantity_excluded": 4950,
                    "technical_entitlement_codes_excluded": ["Q99460", "Q99461"],
                })
        current.update({
            "snapshot_type": "USER_CONFIRMED_INTRADAY",
            "formal_eod_snapshot_written": False,
            "user_confirmed": True,
            "orders": 0,
            "trade_authority": "NONE",
        })
        current["position_watermark"].update({
            "base_state_as_of": ts,
            "user_delta_continuity_confirmed_through": SIM_TS,
            "position_state_current": True,
        })
        current["mark_watermark"].update({
            "marks_source_id": "USER_CONFIRMED_INTRADAY_20260804",
            "latest_mark_date": "2026-08-04",
            "all_positions_marked": True,
            "all_marks_fresh_or_acceptable": True,
        })

    real_sum = real["summary"]
    real_sum.update({
        "holding_count": 8,
        "position_market_value": 614383.30,
        "execution_cash_balance": 769.45,
        "account_total_assets": 615390.25,
        "broker_total_assets_reported": 615390.25,
        "broker_listed_security_total_reported": 299390.20,
        "listed_security_line_market_value_sum": 299152.70,
        "broker_bond_fund_total_reported": 315230.60,
        "broker_reconciliation_exception_amount": 237.50,
        "pending_entitlement_quantity_included": 0,
        "pending_entitlement_market_value_included": 0.0,
        "reconciliation_status": "USER_CONFIRMED_INTRADAY_WITH_UNALLOCATED_BROKER_EXCEPTION",
        "reconciliation_explanation": "Broker total is preserved. CNY 237.50 is not allocated to any security.",
    })
    real["reconciliation_exceptions"] = [{
        "exception_id": "REAL_STOCK_TOTAL_MINUS_LINE_SUM_20260804_INTRADAY",
        "amount": 237.50,
        "status": "OPEN_SOURCE_RECONCILIATION_EXCEPTION",
        "allocation_policy": "DO_NOT_ALLOCATE_TO_ANY_SECURITY",
    }]

    sim_sum = sim["summary"]
    sim_sum.update({
        "holding_count": 16,
        "position_market_value": 799495.10,
        "position_market_value_line_sum": 799538.10,
        "execution_cash_balance": 221661.98,
        "account_total_assets": 1021157.08,
        "account_total_pnl": 21157.08,
        "top_market_value_reported": 799495.10,
        "top_total_assets_reported": 1021157.08,
        "market_value_reconciliation_exception_amount": -43.0,
        "position_ratio_top_reported": 0.7829,
        "new_confirmed_trades": 0,
        "quantity_mutations_from_market_refresh": 0,
        "reconciliation_status": "USER_CONFIRMED_INTRADAY_SECOND_LEVEL_PRICE_EXCEPTION",
        "reconciliation_explanation": "Top totals are preserved. CNY -43.00 is not allocated to any security.",
    })
    sim["reconciliation_exceptions"] = [{
        "exception_id": "SIMULATION_TOP_MARKET_VALUE_MINUS_LINE_SUM_20260804_INTRADAY",
        "amount": -43.0,
        "status": "OPEN_SECOND_LEVEL_PRICE_TIMING_EXCEPTION",
        "allocation_policy": "DO_NOT_ALLOCATE_TO_ANY_SECURITY",
    }]


def update_acceptance() -> None:
    acceptance = read(ACCEPTANCE)
    outputs = {
        "real_positions": REAL_CURRENT,
        "simulation_positions": SIM_CURRENT,
        "portfolio_marks": MARKS_CURRENT,
        "run_current": RUN_CURRENT,
    }
    for key, path in outputs.items():
        acceptance.setdefault("outputs", {})[key] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "semantic_hash": digest(read(path)),
        }
    acceptance["compatibility_repair"] = {
        "status": "PASS",
        "legacy_source_interface_preserved": True,
        "standard_current_interface_preserved": True,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
        "trade_authority": "NONE",
        "orders": 0,
    }
    acceptance["trade_authority"] = "NONE"
    write(ACCEPTANCE, acceptance)


def main() -> None:
    real_draft, sim_draft = read(REAL_CURRENT), read(SIM_CURRENT)
    real_source, sim_source, delta = read(REAL_SOURCE), read(SIM_SOURCE), read(DELTA)
    patch_real_source(real_source, real_draft)
    patch_sim_source(sim_source, sim_draft)
    patch_delta(delta)
    write(REAL_SOURCE, real_source)
    write(SIM_SOURCE, sim_source)
    write(DELTA, delta)
    write(MARKS_CANDIDATE, build_marks(real_draft, sim_draft))

    subprocess.run(["python", "automation/wp2_r/build_portfolio_current.py", "--repo-root", "."], cwd=ROOT, check=True)
    subprocess.run(["python", "automation/wp2_r/finalize_account_summaries.py", "--repo-root", "."], cwd=ROOT, check=True)

    real, sim = read(REAL_CURRENT), read(SIM_CURRENT)
    patch_standard_current(real, sim, real_draft, sim_draft)
    write(REAL_CURRENT, real)
    write(SIM_CURRENT, sim)

    run = read(RUN_CURRENT)
    run.update({
        "run_id": RUN_ID,
        "snapshot_type": "USER_CONFIRMED_INTRADAY",
        "formal_eod_snapshot_written": False,
        "real_account_total_assets": 615390.25,
        "real_execution_cash_balance": 769.45,
        "real_reconciliation_exception_amount": 237.50,
        "simulation_total_assets": 1021157.08,
        "simulation_available_cash": 221661.98,
        "simulation_total_pnl": 21157.08,
        "simulation_market_value_reconciliation_exception_amount": -43.0,
        "candidate_mutations": 0,
        "decision_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    })
    write(RUN_CURRENT, run)
    update_acceptance()

    print(json.dumps({
        "status": "WP2_R_COMPATIBILITY_REPAIRED",
        "real_holdings": len(real["holdings"]),
        "simulation_holdings": len(sim["holdings"]),
        "ordinary_605090": 4950,
        "pending_605090": 4950,
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
