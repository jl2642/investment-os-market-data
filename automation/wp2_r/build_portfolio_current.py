#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def semantic_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def canonical_security_id(code: str) -> str:
    digits = str(code).strip().split(".")[0].zfill(6)
    if digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if digits.startswith(("0", "1", "2", "3")):
        return f"{digits}.SZ"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    return digits


def parse_number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def extract_real_positions(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in source.get("holdings", []):
        code = str(item["code"]).zfill(6)
        asset_class = item.get("asset_class", "UNKNOWN")
        quantity = parse_number(item.get("quantity_or_shares"))
        if asset_class == "BOND_FUND":
            cost_basis = parse_number(item.get("cost_price_or_cost"))
            cost_basis_method = "TOTAL_COST"
            unit_cost = cost_basis / quantity if quantity else None
        else:
            unit_cost = parse_number(item.get("cost_price_or_cost"))
            cost_basis = unit_cost * quantity
            cost_basis_method = "UNIT_COST_TIMES_QUANTITY"
        rows.append(
            {
                "account": "REAL",
                "security_id": canonical_security_id(code),
                "code": code,
                "security_name": item.get("holding_name"),
                "asset_class": asset_class,
                "quantity": quantity,
                "available_quantity": quantity,
                "unit_cost": unit_cost,
                "cost_basis": round(cost_basis, 6),
                "cost_basis_method": cost_basis_method,
                "position_source_as_of": item.get("as_of", source.get("as_of")),
                "position_source_run_id": item.get("run_id", source.get("state_id")),
                "broker_verified": False,
            }
        )
    return rows


def extract_simulation_positions(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in source.get("holdings", []):
        code = str(item["security_code"]).zfill(6)
        quantity = parse_number(item.get("quantity"))
        unit_cost = parse_number(item.get("cost_price"))
        rows.append(
            {
                "account": "SIMULATION",
                "security_id": canonical_security_id(code),
                "code": code,
                "security_name": item.get("security_name"),
                "asset_class": "A_SHARE_STOCK",
                "quantity": quantity,
                "available_quantity": parse_number(item.get("available_quantity"), quantity),
                "unit_cost": unit_cost,
                "cost_basis": round(unit_cost * quantity, 6),
                "cost_basis_method": "UNIT_COST_TIMES_QUANTITY",
                "portfolio_bucket": item.get("portfolio_bucket"),
                "target_weight": item.get("target_weight"),
                "position_source_as_of": item.get("as_of", source.get("as_of")),
                "position_source_run_id": item.get("run_id", source.get("state_id")),
                "broker_verified": False,
            }
        )
    return rows


def validate_delta_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("trade_authority") != "NONE":
        raise ValueError("DELTA_LEDGER_TRADE_AUTHORITY_MUST_BE_NONE")
    seen: set[str] = set()
    for entry in ledger.get("entries", []):
        delta_id = entry.get("delta_id")
        if not delta_id or delta_id in seen:
            raise ValueError("DELTA_ID_MISSING_OR_DUPLICATE")
        seen.add(delta_id)
        if entry.get("status") not in {
            "PENDING_USER_CONFIRMATION",
            "CONFIRMED_BY_USER",
            "APPLIED_TO_POSITION_CURRENT",
            "REJECTED",
        }:
            raise ValueError(f"INVALID_DELTA_STATUS:{delta_id}")
        if entry.get("status") in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"}:
            if entry.get("confirmation_authority") != "USER":
                raise ValueError(f"CONFIRMED_DELTA_REQUIRES_USER_AUTHORITY:{delta_id}")


def apply_confirmed_deltas(
    positions: list[dict[str, Any]],
    ledger: dict[str, Any],
    account: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {row["security_id"]: deepcopy(row) for row in positions}
    applied: list[str] = []
    for entry in ledger.get("entries", []):
        if entry.get("account") != account:
            continue
        if entry.get("status") not in {"CONFIRMED_BY_USER", "APPLIED_TO_POSITION_CURRENT"}:
            continue
        security_id = canonical_security_id(entry["security_id"])
        action = entry["action"]
        quantity_delta = parse_number(entry.get("quantity_delta"))
        unit_price = parse_number(entry.get("unit_price"))
        fees = parse_number(entry.get("fees"))
        row = by_id.get(security_id)
        if row is None:
            if quantity_delta <= 0:
                raise ValueError(f"DELTA_REFERENCES_MISSING_POSITION:{entry['delta_id']}")
            row = {
                "account": account,
                "security_id": security_id,
                "code": security_id.split(".")[0],
                "security_name": entry.get("security_name"),
                "asset_class": entry.get("asset_class", "UNKNOWN"),
                "quantity": 0.0,
                "available_quantity": 0.0,
                "unit_cost": None,
                "cost_basis": 0.0,
                "cost_basis_method": "USER_CONFIRMED_TRANSACTION_LEDGER",
                "position_source_as_of": entry.get("trade_date"),
                "position_source_run_id": entry["delta_id"],
                "broker_verified": False,
            }
        old_qty = parse_number(row.get("quantity"))
        old_cost = parse_number(row.get("cost_basis"))
        new_qty = old_qty + quantity_delta
        if new_qty < -1e-9:
            raise ValueError(f"NEGATIVE_POSITION_AFTER_DELTA:{entry['delta_id']}")
        if action in {"BUY", "TRANSFER_IN"}:
            new_cost = old_cost + quantity_delta * unit_price + fees
        elif action in {"SELL", "TRANSFER_OUT"}:
            if old_qty <= 0:
                raise ValueError(f"SELL_WITHOUT_POSITION:{entry['delta_id']}")
            cost_removed = old_cost * abs(quantity_delta) / old_qty
            new_cost = max(0.0, old_cost - cost_removed)
        elif action == "COST_ADJUSTMENT":
            new_cost = old_cost + parse_number(entry.get("cost_basis_delta"))
        else:
            raise ValueError(f"UNSUPPORTED_DELTA_ACTION:{action}")
        if new_qty <= 1e-9:
            by_id.pop(security_id, None)
        else:
            row["quantity"] = round(new_qty, 8)
            row["available_quantity"] = min(
                round(parse_number(row.get("available_quantity")) + quantity_delta, 8),
                round(new_qty, 8),
            )
            row["cost_basis"] = round(new_cost, 6)
            row["unit_cost"] = round(new_cost / new_qty, 8)
            row["cost_basis_method"] = "USER_CONFIRMED_TRANSACTION_LEDGER"
            row["position_source_as_of"] = entry.get("trade_date")
            row["position_source_run_id"] = entry["delta_id"]
            by_id[security_id] = row
        applied.append(entry["delta_id"])
    return sorted(by_id.values(), key=lambda row: row["security_id"]), applied


def fallback_marks(
    real_source: dict[str, Any],
    simulation_source: dict[str, Any],
) -> list[dict[str, Any]]:
    marks: dict[str, dict[str, Any]] = {}
    for item in real_source.get("holdings", []):
        code = str(item["code"]).zfill(6)
        sid = canonical_security_id(code)
        asset_class = item.get("asset_class", "UNKNOWN")
        marks[sid] = {
            "security_id": sid,
            "code": code,
            "security_name": item.get("holding_name"),
            "asset_class": asset_class,
            "mark": parse_number(item.get("latest_price_or_nav")),
            "mark_type": "OFFICIAL_NAV" if asset_class == "BOND_FUND" else "CLOSE_OR_LAST",
            "as_of_date": str(item.get("as_of", real_source.get("as_of"))).split("_")[0],
            "provider": item.get("data_source", "LEGACY_STATE"),
            "freshness_status": "LKG_FALLBACK",
            "source_role": "LEGACY_CURRENT_FALLBACK",
        }
    for item in simulation_source.get("holdings", []):
        code = str(item["security_code"]).zfill(6)
        sid = canonical_security_id(code)
        marks[sid] = {
            "security_id": sid,
            "code": code,
            "security_name": item.get("security_name"),
            "asset_class": "A_SHARE_STOCK",
            "mark": parse_number(item.get("last_price_close")),
            "mark_type": "CLOSE_OR_LAST",
            "as_of_date": str(item.get("as_of", simulation_source.get("as_of"))).split("_")[0],
            "provider": item.get("data_source", "LEGACY_STATE"),
            "freshness_status": "LKG_FALLBACK",
            "source_role": "LEGACY_CURRENT_FALLBACK",
        }
    return sorted(marks.values(), key=lambda row: row["security_id"])


def load_marks(
    root: Path,
    config: dict[str, Any],
    real_source: dict[str, Any],
    simulation_source: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    candidate = root / config["source_paths"]["marks_candidate"]
    if candidate.exists():
        payload = read_json(candidate)
        if payload.get("status") == "PASS_COMPLETE":
            return payload["marks"], payload.get("refresh_id", "MARKS_CANDIDATE")
    return fallback_marks(real_source, simulation_source), "LEGACY_LKG_FALLBACK"


def enrich_positions(
    positions: list[dict[str, Any]],
    marks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mark_map = {row["security_id"]: row for row in marks}
    output: list[dict[str, Any]] = []
    for position in positions:
        row = deepcopy(position)
        mark = mark_map.get(row["security_id"])
        if mark is None:
            row.update(
                {
                    "mark": None,
                    "mark_as_of": None,
                    "mark_provider": None,
                    "mark_freshness_status": "MISSING",
                    "market_value": None,
                    "unrealized_pnl": None,
                    "unrealized_pnl_pct": None,
                }
            )
        else:
            market_value = parse_number(row["quantity"]) * parse_number(mark["mark"])
            cost_basis = parse_number(row["cost_basis"])
            unrealized = market_value - cost_basis
            row.update(
                {
                    "mark": mark["mark"],
                    "mark_as_of": mark["as_of_date"],
                    "mark_provider": mark["provider"],
                    "mark_freshness_status": mark["freshness_status"],
                    "market_value": round(market_value, 6),
                    "unrealized_pnl": round(unrealized, 6),
                    "unrealized_pnl_pct": round(unrealized / cost_basis, 8) if cost_basis else None,
                }
            )
        output.append(row)
    return output


def account_payload(
    *,
    account: str,
    positions: list[dict[str, Any]],
    continuity_through: str,
    source_as_of: str,
    applied_delta_ids: list[str],
    marks_source_id: str,
) -> dict[str, Any]:
    complete = all(row.get("mark") is not None for row in positions)
    fresh = complete and all(
        row.get("mark_freshness_status") in {"FRESH", "ACCEPTABLE_LAG"} for row in positions
    )
    market_value = sum(parse_number(row.get("market_value")) for row in positions)
    cost_basis = sum(parse_number(row.get("cost_basis")) for row in positions)
    status = (
        "POSITION_CURRENT_MARKS_FRESH_BROKER_UNVERIFIED_RESEARCH_ONLY"
        if fresh
        else "POSITION_CONTINUITY_CURRENT_MARKS_STALE_OR_INCOMPLETE"
    )
    return {
        "schema_version": "1.0.0",
        "state_id": f"WP2R_{account}_POSITIONS_CURRENT",
        "account": account,
        "status": status,
        "position_watermark": {
            "base_state_as_of": source_as_of,
            "user_delta_continuity_confirmed_through": continuity_through,
            "applied_delta_count": len(applied_delta_ids),
            "applied_delta_ids": applied_delta_ids,
            "position_state_current": True,
        },
        "mark_watermark": {
            "marks_source_id": marks_source_id,
            "all_positions_marked": complete,
            "all_marks_fresh_or_acceptable": fresh,
            "latest_mark_date": max(
                (str(row.get("mark_as_of")) for row in positions if row.get("mark_as_of")),
                default=None,
            ),
        },
        "broker_verification": {
            "broker_linked": False,
            "broker_verified": False,
            "verification_status": "NOT_CONNECTED_USER_CONFIRMATION_AT_TRANSACTION_OR_ACTION_GATE",
            "separate_from_market_watermark": True,
        },
        "holdings": positions,
        "summary": {
            "holding_count": len(positions),
            "market_value": round(market_value, 6),
            "cost_basis": round(cost_basis, 6),
            "unrealized_pnl": round(market_value - cost_basis, 6),
        },
        "permissions": {
            "portfolio_fit": fresh,
            "performance_monitoring": complete,
            "live_action": False,
            "automatic_quantity_or_cost_mutation": False,
            "order_execution": False,
        },
        "trade_authority": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default="automation/wp2_r/config.json")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    real_source = read_json(root / config["source_paths"]["real_legacy"])
    simulation_source = read_json(root / config["source_paths"]["simulation_legacy"])
    ledger = read_json(root / config["source_paths"]["delta_ledger"])
    validate_delta_ledger(ledger)

    real = extract_real_positions(real_source)
    simulation = extract_simulation_positions(simulation_source)
    real, real_deltas = apply_confirmed_deltas(real, ledger, "REAL")
    simulation, simulation_deltas = apply_confirmed_deltas(simulation, ledger, "SIMULATION")

    marks, marks_source_id = load_marks(root, config, real_source, simulation_source)
    real_enriched = enrich_positions(real, marks)
    simulation_enriched = enrich_positions(simulation, marks)

    continuity = ledger["continuity_confirmed_through"]
    real_payload = account_payload(
        account="REAL",
        positions=real_enriched,
        continuity_through=continuity,
        source_as_of=real_source["as_of"],
        applied_delta_ids=real_deltas,
        marks_source_id=marks_source_id,
    )
    real_payload["cash_policy"] = "BROKER_EXECUTION_BALANCE_ONLY_EXTERNAL_LIQUIDITY_EXCLUDED"
    simulation_payload = account_payload(
        account="SIMULATION",
        positions=simulation_enriched,
        continuity_through=continuity,
        source_as_of=simulation_source["as_of"],
        applied_delta_ids=simulation_deltas,
        marks_source_id=marks_source_id,
    )

    required_ids = {row["security_id"] for row in real + simulation}
    marked_ids = {row["security_id"] for row in marks}
    missing = sorted(required_ids - marked_ids)
    marks_fresh = not missing and all(
        row.get("freshness_status") in {"FRESH", "ACCEPTABLE_LAG"}
        for row in marks
        if row["security_id"] in required_ids
    )
    marks_payload = {
        "schema_version": "1.0.0",
        "state_id": "WP2R_PORTFOLIO_MARKS_CURRENT",
        "status": "CURRENT_COMPLETE" if marks_fresh else "LKG_FALLBACK_OR_INCOMPLETE_BLOCKED",
        "source_id": marks_source_id,
        "required_security_count": len(required_ids),
        "marked_security_count": len(required_ids - set(missing)),
        "missing_security_ids": missing,
        "marks": [row for row in marks if row["security_id"] in required_ids],
        "data_watermark": {
            "latest_mark_date": max(
                (str(row.get("as_of_date")) for row in marks if row.get("as_of_date")),
                default=None,
            ),
            "fresh_for_portfolio_fit": marks_fresh,
            "broker_verification_not_inferred": True,
        },
        "automatic_position_mutations": 0,
        "trade_authority": "NONE",
    }

    overall_fresh = (
        real_payload["permissions"]["portfolio_fit"]
        and simulation_payload["permissions"]["portfolio_fit"]
    )
    run_payload = {
        "schema_version": "1.0.0",
        "run_id": f"WP2R_PORTFOLIO_CURRENT_{date.today().isoformat()}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "PASS_POSITION_LEVEL_CURRENT_RESEARCH_READY"
            if overall_fresh
            else "PASS_CONTRACT_BASELINE_MARK_REFRESH_REQUIRED"
        ),
        "position_continuity_confirmed_through": continuity,
        "real_holding_count": len(real_payload["holdings"]),
        "simulation_holding_count": len(simulation_payload["holdings"]),
        "portfolio_marks_required": len(required_ids),
        "portfolio_marks_fresh": overall_fresh,
        "broker_verified": False,
        "wp4b_position_level_fit_ready": overall_fresh,
        "wp5_live_action_ready": False,
        "user_action_required_now": False,
        "next_user_input_trigger": "ONLY_WHEN_REAL_OR_SIMULATION_TRANSACTION_OCCURS",
        "economic_transaction_mutations": len(real_deltas) + len(simulation_deltas),
        "orders": 0,
        "trade_authority": "NONE",
    }

    outputs = config["output_paths"]
    write_json(root / outputs["real_positions"], real_payload)
    write_json(root / outputs["simulation_positions"], simulation_payload)
    write_json(root / outputs["portfolio_marks"], marks_payload)
    write_json(root / outputs["run_current"], run_payload)

    acceptance = {
        "acceptance_id": "WP2_R_PORTFOLIO_CURRENT_ACCEPTANCE_V1",
        "status": (
            "WP2R_CONTRACT_AND_POSITION_CURRENT_ACCEPTED_MARK_REFRESH_PENDING"
            if not overall_fresh
            else "WP2R_RECURRING_PORTFOLIO_CURRENT_READY"
        ),
        "outputs": {
            key: {
                "path": path,
                "semantic_hash": semantic_hash(read_json(root / path)),
            }
            for key, path in outputs.items()
            if key != "acceptance"
        },
        "controls": {
            "position_and_mark_watermarks_separate": True,
            "broker_verification_separate": True,
            "user_delta_only_for_transactions": True,
            "automatic_quantity_or_cost_mutations": 0,
            "orders": 0,
            "trade_authority": "NONE",
        },
        "wp3r_unblocked": True,
        "wp4b_position_fit_unblocked": overall_fresh,
        "wp5_unblocked": False,
    }
    write_json(root / outputs["acceptance"], acceptance)
    print(json.dumps(run_payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
