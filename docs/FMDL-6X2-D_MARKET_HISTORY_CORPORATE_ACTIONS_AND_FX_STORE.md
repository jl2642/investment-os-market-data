# FMDL-6X2-D — Market History, Corporate Actions & FX Store

## Evidence and capacity boundary

The accepted zero-cost route is Yahoo Query1/Query2 Chart as a **non-decision-grade fallback**, not an official market-data source. Stooq remains disabled. A dual-route 2010-present backfill for all 8,785 securities would exceed the current GitHub runtime and repository-size contract. The first production Release therefore creates a sharded, resumable baseline:

- 64 deterministic representative securities receive captured dual-route daily OHLCV, dividend and split histories from 2010-01-01 through 2026-07-21;
- every remaining Security is retained in the backfill queue, not silently omitted;
- both Yahoo routes must succeed and reconcile before rows enter the accepted store;
- accepted Yahoo rows remain `NON_DECISION_GRADE_FALLBACK` and cannot independently support investment decisions;
- ECB official CNY/EUR, HKD/EUR and USD/EUR histories are combined to derive USD/CNY and USD/HKD with full lineage;
- Frankfurter is support-only and cannot replace ECB history.

## Completion claim

This phase accepts the market/reference **production mechanism and initial evidence baseline**. It does not claim that all-universe history is complete. Later bounded shard runs may reduce the backfill queue without changing the evidence grade.

## No investment mutation

Research production remains separate from brokerage, portfolio and trade authority. No Candidate Pool, simulation, real-account or order mutation is authorized.
