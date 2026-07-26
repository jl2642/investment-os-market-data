#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def number(value: Any, default: float = 0.0) -> float:
    return default if value in (None, "") else float(value)


def canonical_security_id(code: str) -> str:
    raw = str(code).strip().upper()
    parts = raw.split(".")
    digits = parts[0].zfill(6)
    if len(parts) > 1 and parts[1] in {"SH", "SZ", "BJ", "OF"}:
        return f"{digits}.{parts[1]}"
    if digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if digits.startswith(("0", "1", "2", "3")):
        return f"{digits}.SZ"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    return digits


def security_id_for(code: str, asset_class: str) -> str:
    return f"{str(code).strip().split('.')[0].zfill(6)}.OF" if asset_class == "BOND_FUND" else canonical_security_id(code)


def real_positions(source: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in source.get("holdings", []):
        code, cls = str(item["code"]).zfill(6), item.get("asset_class", "UNKNOWN")
        qty = number(item.get("quantity_or_shares"))
        if cls == "BOND_FUND":
            cost, method = number(item.get("cost_price_or_cost")), "TOTAL_COST"
            unit_cost = cost / qty if qty else None
        else:
            unit_cost, method = number(item.get("cost_price_or_cost")), "UNIT_COST_TIMES_QUANTITY"
            cost = unit_cost * qty
        out.append({
            "account": "REAL", "security_id": security_id_for(code, cls), "code": code,
            "security_name": item.get("holding_name"), "asset_class": cls, "quantity": qty,
            "available_quantity": qty, "unit_cost": unit_cost, "cost_basis": round(cost, 6),
            "cost_basis_method": method, "position_source_as_of": item.get("as_of", source.get("as_of")),
            "position_source_run_id": item.get("run_id", source.get("state_id")), "broker_verified": False,
        })
    return out


def simulation_positions(source: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in source.get("holdings", []):
        code, qty, unit = str(item["security_code"]).zfill(6), number(item.get("quantity")), number(item.get("cost_price"))
        out.append({
            "account": "SIMULATION", "security_id": canonical_security_id(code), "code": code,
            "security_name": item.get("security_name"), "asset_class": "A_SHARE_STOCK",
            "quantity": qty, "available_quantity": number(item.get("available_quantity"), qty),
            "unit_cost": unit, "cost_basis": round(unit * qty, 6), "cost_basis_method": "UNIT_COST_TIMES_QUANTITY",
            "portfolio_bucket": item.get("portfolio_bucket"), "target_weight": item.get("target_weight"),
            "position_source_as_of": item.get("as_of", source.get("as_of")),
            "position_source_run_id": item.get("run_id", source.get("state_id")), "broker_verified": False,
        })
    return out


def validate_delta_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("trade_authority") != "NONE":
        raise ValueError("DELTA_LEDGER_TRADE_AUTHORITY_MUST_BE_NONE")
    seen = set()
    allowed = {"PENDING_USER_CONFIRMATION", "CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT", "REJECTED"}
    for row in ledger.get("entries", []):
        key = row.get("delta_id")
        if not key or key in seen:
            raise ValueError("DELTA_ID_MISSING_OR_DUPLICATE")
        seen.add(key)
        if row.get("status") not in allowed:
            raise ValueError(f"INVALID_DELTA_STATUS:{key}")
        if row.get("status") in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"} and row.get("confirmation_authority") != "USER":
            raise ValueError(f"CONFIRMED_DELTA_REQUIRES_USER_AUTHORITY:{key}")


def apply_confirmed_deltas(positions: list[dict[str, Any]], ledger: dict[str, Any], account: str) -> tuple[list[dict[str, Any]], list[str]]:
    current = {row["security_id"]: deepcopy(row) for row in positions}
    applied = []
    for delta in ledger.get("entries", []):
        if delta.get("account") != account or delta.get("status") not in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"}:
            continue
        cls = delta.get("asset_class", "UNKNOWN")
        sid = security_id_for(delta["security_id"], cls)
        action, qd, price, fees = delta["action"], number(delta.get("quantity_delta")), number(delta.get("unit_price")), number(delta.get("fees"))
        row = current.get(sid)
        if row is None:
            if qd <= 0:
                raise ValueError(f"DELTA_REFERENCES_MISSING_POSITION:{delta['delta_id']}")
            row = {
                "account": account, "security_id": sid, "code": sid.split(".")[0],
                "security_name": delta.get("security_name"), "asset_class": cls, "quantity": 0.0,
                "available_quantity": 0.0, "unit_cost": None, "cost_basis": 0.0,
                "cost_basis_method": "USER_CONFIRMED_TRANSACTION_LEDGER", "broker_verified": False,
            }
        old_q, old_cost, new_q = number(row.get("quantity")), number(row.get("cost_basis")), number(row.get("quantity")) + qd
        if new_q < -1e-9:
            raise ValueError(f"NEGATIVE_POSITION_AFTER_DELTA:{delta['delta_id']}")
        if action in {"BUY", "TRANSFER_IN"}:
            new_cost = old_cost + qd * price + fees
        elif action in {"SELL", "TRANSFER_OUT"}:
            if old_q <= 0:
                raise ValueError(f"SELL_WITHOUT_POSITION:{delta['delta_id']}")
            new_cost = max(0.0, old_cost - old_cost * abs(qd) / old_q)
        elif action == "COST_ADJUSTMENT":
            new_cost = old_cost + number(delta.get("cost_basis_delta"))
        else:
            raise ValueError(f"UNSUPPORTED_DELTA_ACTION:{action}")
        if new_q <= 1e-9:
            current.pop(sid, None)
        else:
            row.update({
                "quantity": round(new_q, 8), "available_quantity": min(round(number(row.get("available_quantity")) + qd, 8), round(new_q, 8)),
                "cost_basis": round(new_cost, 6), "unit_cost": round(new_cost / new_q, 8),
                "cost_basis_method": "USER_CONFIRMED_TRANSACTION_LEDGER", "position_source_as_of": delta.get("trade_date"),
                "position_source_run_id": delta["delta_id"],
            })
            current[sid] = row
        applied.append(delta["delta_id"])
    return sorted(current.values(), key=lambda x: x["security_id"]), applied


def fallback_marks(real: dict[str, Any], sim: dict[str, Any]) -> list[dict[str, Any]]:
    marks = {}
    for item in real.get("holdings", []):
        code, cls = str(item["code"]).zfill(6), item.get("asset_class", "UNKNOWN")
        sid = security_id_for(code, cls)
        marks[sid] = {
            "security_id": sid, "code": code, "security_name": item.get("holding_name"), "asset_class": cls,
            "mark": number(item.get("latest_price_or_nav")), "mark_type": "OFFICIAL_NAV" if cls == "BOND_FUND" else "CLOSE_OR_LAST",
            "as_of_date": str(item.get("as_of", real.get("as_of"))).split("_")[0],
            "provider": item.get("data_source", "LEGACY_STATE"), "freshness_status": "LKG_FALLBACK",
            "source_role": "LEGACY_CURRENT_FALLBACK",
        }
    for item in sim.get("holdings", []):
        code, sid = str(item["security_code"]).zfill(6), canonical_security_id(item["security_code"])
        marks[sid] = {
            "security_id": sid, "code": code, "security_name": item.get("security_name"), "asset_class": "A_SHARE_STOCK",
            "mark": number(item.get("last_price_close")), "mark_type": "CLOSE_OR_LAST",
            "as_of_date": str(item.get("as_of", sim.get("as_of"))).split("_")[0],
            "provider": item.get("data_source", "LEGACY_STATE"), "freshness_status": "LKG_FALLBACK",
            "source_role": "LEGACY_CURRENT_FALLBACK",
        }
    return sorted(marks.values(), key=lambda x: x["security_id"])


def marks(root: Path, cfg: dict[str, Any], real: dict[str, Any], sim: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    path = root / cfg["source_paths"]["marks_candidate"]
    if path.exists():
        payload = read(path)
        if payload.get("status") == "PASS_COMPLETE":
            return payload["marks"], payload.get("refresh_id", "MARKS_CANDIDATE")
    return fallback_marks(real, sim), "LEGACY_LKG_FALLBACK"


def enrich(positions: list[dict[str, Any]], all_marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {x["security_id"]: x for x in all_marks}
    result = []
    for base in positions:
        row, mark = deepcopy(base), lookup.get(base["security_id"])
        if not mark:
            row.update({"mark": None, "mark_as_of": None, "mark_provider": None, "mark_freshness_status": "MISSING", "market_value": None, "unrealized_pnl": None, "unrealized_pnl_pct": None})
        else:
            value, cost = number(row["quantity"]) * number(mark["mark"]), number(row["cost_basis"])
            row.update({"mark": mark["mark"], "mark_as_of": mark["as_of_date"], "mark_provider": mark["provider"], "mark_freshness_status": mark["freshness_status"], "market_value": round(value, 6), "unrealized_pnl": round(value - cost, 6), "unrealized_pnl_pct": round((value - cost) / cost, 8) if cost else None})
        result.append(row)
    return result


enrich_positions = enrich


def account_payload(account: str, rows: list[dict[str, Any]], continuity: str, source_as_of: str, applied: list[str], marks_id: str) -> dict[str, Any]:
    complete = all(x.get("mark") is not None for x in rows)
    fresh = complete and all(x.get("mark_freshness_status") in {"FRESH", "ACCEPTABLE_LAG"} for x in rows)
    value, cost = sum(number(x.get("market_value")) for x in rows), sum(number(x.get("cost_basis")) for x in rows)
    return {
        "schema_version": "1.0.0", "state_id": f"WP2R_{account}_POSITIONS_CURRENT", "account": account,
        "status": "POSITION_CURRENT_MARKS_FRESH_BROKER_UNVERIFIED_RESEARCH_ONLY" if fresh else "POSITION_CONTINUITY_CURRENT_MARKS_STALE_OR_INCOMPLETE",
        "position_watermark": {"base_state_as_of": source_as_of, "user_delta_continuity_confirmed_through": continuity, "applied_delta_count": len(applied), "applied_delta_ids": applied, "position_state_current": True},
        "mark_watermark": {"marks_source_id": marks_id, "all_positions_marked": complete, "all_marks_fresh_or_acceptable": fresh, "latest_mark_date": max((str(x.get("mark_as_of")) for x in rows if x.get("mark_as_of")), default=None)},
        "broker_verification": {"broker_linked": False, "broker_verified": False, "verification_status": "NOT_CONNECTED_USER_CONFIRMATION_AT_TRANSACTION_OR_ACTION_GATE", "separate_from_market_watermark": True},
        "holdings": rows, "summary": {"holding_count": len(rows), "market_value": round(value, 6), "cost_basis": round(cost, 6), "unrealized_pnl": round(value - cost, 6)},
        "permissions": {"portfolio_fit": fresh, "performance_monitoring": complete, "live_action": False, "automatic_quantity_or_cost_mutation": False, "order_execution": False},
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_r/config.json")
    args = parser.parse_args()
    root, cfg = Path(args.repo_root).resolve(), read(Path(args.repo_root).resolve() / args.config)
    real_source, sim_source, ledger = read(root / cfg["source_paths"]["real_legacy"]), read(root / cfg["source_paths"]["simulation_legacy"]), read(root / cfg["source_paths"]["delta_ledger"])
    validate_delta_ledger(ledger)
    real, real_applied = apply_confirmed_deltas(real_positions(real_source), ledger, "REAL")
    sim, sim_applied = apply_confirmed_deltas(simulation_positions(sim_source), ledger, "SIMULATION")
    all_marks, marks_id = marks(root, cfg, real_source, sim_source)
    real_out = account_payload("REAL", enrich(real, all_marks), ledger["continuity_confirmed_through"], real_source["as_of"], real_applied, marks_id)
    real_out["cash_policy"] = "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED"
    sim_out = account_payload("SIMULATION", enrich(sim, all_marks), ledger["continuity_confirmed_through"], sim_source["as_of"], sim_applied, marks_id)
    required, marked = {x["security_id"] for x in real + sim}, {x["security_id"] for x in all_marks}
    missing = sorted(required - marked)
    fresh = not missing and all(x.get("freshness_status") in {"FRESH", "ACCEPTABLE_LAG"} for x in all_marks if x["security_id"] in required)
    marks_out = {
        "schema_version": "1.0.0", "state_id": "WP2R_PORTFOLIO_MARKS_CURRENT",
        "status": "CURRENT_COMPLETE" if fresh else "LKG_FALLBACK_OR_INCOMPLETE_BLOCKED", "source_id": marks_id,
        "required_security_count": len(required), "marked_security_count": len(required - set(missing)), "missing_security_ids": missing,
        "marks": [x for x in all_marks if x["security_id"] in required],
        "data_watermark": {"latest_mark_date": max((str(x.get("as_of_date")) for x in all_marks if x.get("as_of_date")), default=None), "fresh_for_portfolio_fit": fresh, "broker_verification_not_inferred": True},
        "automatic_position_mutations": 0, "trade_authority": "NONE",
    }
    overall = real_out["permissions"]["portfolio_fit"] and sim_out["permissions"]["portfolio_fit"]
    run = {
        "schema_version": "1.0.0", "run_id": f"WP2R_PORTFOLIO_CURRENT_{date.today().isoformat()}", "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_POSITION_LEVEL_CURRENT_RESEARCH_READY" if overall else "PASS_CONTRACT_BASELINE_MARK_REFRESH_REQUIRED",
        "position_continuity_confirmed_through": ledger["continuity_confirmed_through"], "real_holding_count": len(real), "simulation_holding_count": len(sim),
        "portfolio_marks_required": len(required), "portfolio_marks_fresh": overall, "broker_verified": False, "wp4b_position_level_fit_ready": overall,
        "wp5_live_action_ready": False, "user_action_required_now": False, "next_user_input_trigger": "ONLY_WHEN_REAL_OR_SIMULATION_TRANSACTION_OCCURS",
        "economic_transaction_mutations": len(real_applied) + len(sim_applied), "orders": 0, "trade_authority": "NONE",
    }
    out = cfg["output_paths"]
    for key, value in [("real_positions", real_out), ("simulation_positions", sim_out), ("portfolio_marks", marks_out), ("run_current", run)]:
        write(root / out[key], value)
    acceptance = {
        "acceptance_id": "WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_V1",
        "status": "WP2R_RECURRING_PORTFOLIO_CURRENT_READY" if overall else "WP2R_CONTRACT_AND_POSITION_CURRENT_ACCEPTED_MARK_REFRESH_PENDING",
        "outputs": {key: {"path": out[key], "semantic_hash": digest(read(root / out[key]))} for key in ("real_positions", "simulation_positions", "portfolio_marks", "run_current")},
        "controls": {"position_and_mark_watermarks_separate": True, "broker_verification_separate": True, "user_delta_only_for_transactions": True, "automatic_quantity_or_cost_mutations": 0, "orders": 0, "trade_authority": "NONE"},
        "wp3r_unblocked": True, "wp4b_position_fit_unblocked": overall, "wp5_unblocked": False,
    }
    write(root / out["acceptance"], acceptance)
    print(json.dumps(run, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
