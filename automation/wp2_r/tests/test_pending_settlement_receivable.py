from __future__ import annotations

from automation.wp2_r.finalize_account_summaries import pending_real_settlement_receivable


def test_pending_real_sale_is_receivable_not_execution_cash() -> None:
    ledger = {
        "entries": [
            {
                "account": "REAL",
                "action": "SELL",
                "status": "CONFIRMED_BY_USER",
                "settlement_status": "PENDING_CASH_SETTLEMENT",
                "net_settlement_amount": 100390.95,
            },
            {
                "account": "REAL",
                "action": "SELL",
                "status": "CONFIRMED_BY_USER",
                "settlement_status": "SETTLED",
                "net_settlement_amount": 10.0,
            },
            {
                "account": "SIMULATION",
                "action": "SELL",
                "status": "CONFIRMED_BY_USER",
                "settlement_status": "PENDING_CASH_SETTLEMENT",
                "net_settlement_amount": 20.0,
            },
        ]
    }
    assert pending_real_settlement_receivable(ledger) == 100390.95
