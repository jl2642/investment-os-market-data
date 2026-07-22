# FMDL-6X1-FINAL Acceptance Criteria

The phase is accepted only when all gates below pass.

## Release-chain integrity

- All four prior Last-success pointers exist.
- Release IDs, statuses and next gates match the frozen contract.
- `trade_authority` is `NONE` in every phase.
- Current and immutable Release assets are byte-identical.

## Cross-phase semantic integrity

- A keeps the brokerage gate closed and the research gate controlled-open.
- B keeps XNYS/XNAS/XASE, channel eligibility pending, portfolio admission unauthorized and unknown records quarantined.
- C preserves official-first routing, zero paid cost, non-decision-grade market fallbacks and Stooq challenge rejection.
- D preserves the six-stage 6X2 plan, SEC official-only evidence, zero paid budget, atomic promotion and LKG protection.

## Operational resilience

- Same-input replay is byte deterministic.
- All nine failure injections are detected.
- Clean-room restore succeeds from the frozen minimal asset list.
- Failed or partial runs cannot replace Current or Last-known-good.
- Immutable Release collision hard-fails.

## Final activation

- Research Production Gate = `OPEN_FOR_FMDL6X2_DATA_PRODUCTION`.
- Brokerage & Real-Account Gate = `CLOSED_NO_CHANNEL`.
- Seven FMDL-6X2 startup assets are present.
- Final status = `FMDL6X1_FINAL_ACCEPTED`.
- Next gate = `FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION`.
