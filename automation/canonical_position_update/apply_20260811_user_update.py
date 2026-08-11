#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path("investment_os_runtime/30_STATE_CURRENT/15_PORTFOLIO_INPUT/USER_TRANSACTION_DELTA_LEDGER_CURRENT.json")
EVIDENCE = Path("investment_os_runtime/40_EVIDENCE_AND_LINEAGE/POSITION_UPDATE_2026_08_11/USER_CONFIRMED_REAL_SALE_20260806.json")

DELTA_ID = "REAL_20260806_SELL_110017_ALL"
CONFIRMED_AT = "2026-08-11T09:27:00+08:00"
QUANTITY = 71422.49
GROSS_AMOUNT = 100491.44
FEES = 100.49
NET_SETTLEMENT = 100390.95
UNIT_PRICE = round(GROSS_AMOUNT / QUANTITY, 8)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expected_delta() -> dict:
    return {
        "account": "REAL",
        "action": "SELL",
        "application_decision": "APPLY_TO_POSITION_CURRENT",
        "asset_class": "BOND_FUND",
        "cash_availability_status": "NOT_AVAILABLE_UNTIL_SETTLED",
        "confirmation_authority": "USER",
        "confirmed_at": CONFIRMED_AT,
        "delta_id": DELTA_ID,
        "event_type": "USER_CONFIRMED_REAL_TRADE",
        "evidence_status": "USER_CONFIRMED",
        "fees": FEES,
        "gross_amount": GROSS_AMOUNT,
        "net_settlement_amount": NET_SETTLEMENT,
        "note": "User confirmed full sale on 2026-08-06. Net proceeds are confirmed but remain unsettled and must not be treated as executable broker cash until settlement is explicitly confirmed.",
        "orders": 0,
        "price": UNIT_PRICE,
        "quantity": QUANTITY,
        "quantity_delta": -QUANTITY,
        "security_code": "110017",
        "security_id": "110017.OF",
        "security_name": "易方达增强回报债券A",
        "settlement_status": "PENDING_CASH_SETTLEMENT",
        "status": "CONFIRMED_BY_USER",
        "trade_date": "2026-08-06",
        "trade_authority": "NONE",
        "unit_price": UNIT_PRICE,
    }


def main() -> None:
    ledger = read(LEDGER)
    if ledger.get("trade_authority") != "NONE":
        raise SystemExit("DELTA_LEDGER_TRADE_AUTHORITY_MUST_BE_NONE")

    expected = expected_delta()
    matches = [row for row in ledger.get("entries", []) if row.get("delta_id") == DELTA_ID]
    if len(matches) > 1:
        raise SystemExit("DUPLICATE_RUNTIME_CLOSURE_DELTA")
    if matches:
        for key, value in expected.items():
            if matches[0].get(key) != value:
                raise SystemExit(f"EXISTING_DELTA_CONFLICT:{key}:{matches[0].get(key)!r}!={value!r}")
    else:
        ledger.setdefault("entries", []).append(expected)

    ledger["as_of"] = CONFIRMED_AT
    ledger["continuity_confirmed_through"] = CONFIRMED_AT
    ledger["ledger_id"] = "USER_TRANSACTION_DELTA_LEDGER_CURRENT_20260811"
    ledger["snapshot_type"] = "USER_CONFIRMED_CONTINUITY_AND_TRANSACTION_DELTA"
    ledger["status"] = "USER_CONFIRMED_DELTA_PENDING_POSITION_MATERIALIZATION"
    ledger["unapplied_delta_count"] = sum(
        1 for row in ledger.get("entries", []) if row.get("status") == "CONFIRMED_BY_USER"
    )
    ledger["orders"] = 0
    ledger["trade_authority"] = "NONE"

    evidence = {
        "evidence_id": "POSITION_UPDATE_2026_08_11_USER_CONFIRMATION",
        "confirmed_at": CONFIRMED_AT,
        "confirmation_authority": "USER",
        "real_account": {
            "transaction": {
                "trade_date": "2026-08-06",
                "security_id": "110017.OF",
                "security_name": "易方达增强回报债券A",
                "action": "SELL_ALL",
                "quantity": QUANTITY,
                "gross_amount": GROSS_AMOUNT,
                "fees": FEES,
                "net_settlement_amount": NET_SETTLEMENT,
                "settlement_status": "PENDING_CASH_SETTLEMENT",
                "execution_cash_available": False,
            },
            "all_other_positions_and_cash_changes": "NONE_REPORTED",
        },
        "simulation_account": {
            "changes_since_prior_confirmed_state": "NONE_REPORTED",
        },
        "continuity_confirmed_through": CONFIRMED_AT,
        "economic_mutations_authorized": {
            "remove_110017_position": True,
            "recognize_pending_settlement_receivable": True,
            "treat_receivable_as_execution_cash": False,
            "other_real_mutations": False,
            "simulation_mutations": False,
            "candidate_mutations": False,
            "orders": False,
        },
        "trade_authority": "NONE",
    }

    write(LEDGER, ledger)
    write(EVIDENCE, evidence)
    print(json.dumps({
        "delta_id": DELTA_ID,
        "unit_price_derived_from_confirmed_amounts": UNIT_PRICE,
        "net_settlement_amount": NET_SETTLEMENT,
        "settlement_status": "PENDING_CASH_SETTLEMENT",
        "continuity_confirmed_through": CONFIRMED_AT,
        "unapplied_delta_count": ledger["unapplied_delta_count"],
        "orders": 0,
        "trade_authority": "NONE",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
