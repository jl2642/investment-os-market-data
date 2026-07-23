# FMDL-6X4-D — Simulation-only Pilot, Attribution & Failure Recovery

## Objective

Validate the operational path between the accepted Candidate Graduation interface and a future simulation environment without creating a Candidate Pool promotion, an Investment OS simulation position, a real-account action or an order.

## Roadmap reconciliation

The frozen `FMDL-6X3_X4_DEVELOPMENT_ROADMAP.md` requires `6X4-C → 6X4-D → 6X4-E → 6X4-FINAL`. Release 44 remains immutable, but its legacy handoff directly to FINAL is superseded for active orchestration by the frozen roadmap. This stage therefore enters from accepted Release 44 and exits only to 6X4-E.

## Two-lane pilot

### Actual control lane

All six issuer securities remain blocked by incomplete graduation prerequisites. QQQ remains a reference instrument. The accepted result is zero exposure, zero simulation events and zero state transitions. This proves that the guardrails fail closed.

### Shadow attribution lane

AAPL, MSFT and NVDA are combined into a hypothetical equal-weight research sandbox and compared with QQQ over the five already-registered relative-factor horizons. The lane uses only accepted `NON_DECISION_GRADE_FALLBACK` observations. It is an attribution mechanism test, not an Investment OS portfolio, formal performance record, recommendation or trade signal.

## Attribution controls

Each security receives one-third hypothetical weight. For each horizon:

- shadow portfolio return is the arithmetic mean of the three security returns;
- benchmark return is the registered QQQ return;
- shadow excess return is the arithmetic mean of the three registered excess returns;
- security contributions must sum exactly to shadow excess return;
- data grade and sandbox-only usage are carried to every output.

## Failure and recovery controls

Ten deterministic scenarios cover failed workflow QC, stale market data, invalidated valuation, invalidated peer groups, evidence conflicts, withdrawn human approval, Current/Release mismatch, interrupted publication, duplicate event replay and out-of-order events. Every scenario must fail closed, preserve prior accepted state and identify an explicit recovery path through immutable Release, Last-success, LKG or deterministic replay.

## Authority boundary

- Candidate Pool mutation: prohibited.
- Investment OS simulation-book mutation: prohibited.
- Real-account mutation: prohibited.
- Brokerage and orders: unavailable.
- Investment recommendation: not issued.
- Trade authority: `NONE`.
