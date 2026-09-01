# Portfolio Maintenance Input Contract

Status: CURRENT ON MERGE  
Authority: `investment_os_runtime/00_CONTROL/SYSTEM_CURRENT.json`

## Purpose

Keep Real and Simulation portfolio state continuously usable without turning screenshots or the ChatGPT Library into a second database.

## User input boundary

The user is expected to report only economic facts the system cannot reliably learn from public data:

- actual Real or Simulation buys, sells, transfers or other executed position changes;
- external cash deposits or withdrawals that change deployable account cash;
- private compensation, settlement or entitlement events that are not yet observable as ordinary holdings;
- a broker/account correction when the system explicitly surfaces an unresolved reconciliation exception.

The user is **not** expected to repeatedly upload full holding screenshots when no private economic fact changed.

## System-owned maintenance

Without a new user transaction, the system owns maintenance of:

- listed-security prices and fund NAVs;
- public dividends, splits and other public corporate actions, with fail-closed handling where broker-specific tax/fee treatment cannot be known;
- Real and Simulation market values and performance;
- unrealized P&L, account-level P&L where the source ledger supports it, concentration and account weights;
- portfolio monitoring flags;
- event/evidence-driven holding reunderwriting priority;
- current public fundamental, valuation and announcement evidence.

Real and Simulation remain logically separate account books even when a security appears in both.

## Reconciliation rule

A broker or simulation snapshot may be used as a bounded reconciliation checkpoint. It may confirm current quantity, displayed cost basis, account cash and account totals, but the system must not invent missing transactions to explain drift.

When a snapshot establishes a new source baseline:

1. already-incorporated historical transaction deltas remain in the audit ledger;
2. those deltas are marked non-applicable to future position mutation so they cannot be double-applied;
3. unexplained display-cost or cash drift is disclosed rather than backfilled with fabricated transaction history;
4. market/NAV refreshes never mutate quantity.

## Research and decision boundary

Portfolio maintenance has two different coverage concepts:

- **performance monitoring coverage**: every current Real/Simulation holding should be maintained mechanically;
- **investment recommendation coverage**: only positions with current decision-grade underwriting receive ADD/HOLD/TRIM/EXIT style recommendations.

Missing decision-grade underwriting must create a reunderwriting backlog, not make the holding disappear from monitoring.

Deep semantic D2 work is prioritized by current evidence, concentration, drawdown and review triggers. It does not create orders and does not grant execution authority.

## Safety

- automatic broker orders: prohibited;
- automatic Real/Simulation transaction inference: prohibited;
- automatic quantity mutation from market drift: prohibited;
- orders = 0;
- trade_authority = NONE.
