# FMDL-7D — Scheduled Operations, Monitoring, Staleness & Cost Controls

## Objective

FMDL-7D converts the accepted cross-market research, state and attribution system into a bounded operating-control plane. It freezes when the system runs, what each cadence must produce, how staleness and failures are detected, when Current may be promoted, how Last-known-good is protected and when work must stop because runtime, retry, network or artifact budgets have been exhausted.

This stage does not fetch a new market snapshot, confirm account changes after 2026-07-20, issue a live trade recommendation, mutate Candidate Pool, simulation, real-account or rules, repack the File Library Canonical ZIP or create orders.

## Authoritative entry state

- FMDL-7C Release 51 is accepted.
- The bound real account, simulation book and Candidate Core remain Last-known-good as of 2026-07-20 close and are not claimed as current after that date.
- FMDL-6X4-E supplies the accepted cross-market operating-runbook base.
- Investment OS Release 8 remains the binary Canonical base.
- FMDL-5 and FMDL-6 remain accepted Hong Kong and US immutable overlays.
- `trade_authority = NONE` remains unchanged.

## Cadence model

Six cadences are frozen:

1. **Daily** — source freshness, pointer health, market-adapter status, account-state confirmation gate and alerts.
2. **Weekly** — Candidate Core, Active Memo, thesis, falsifier, duplication and simulation-control review.
3. **Monthly** — real-account and simulation attribution, full PnL bridge, candidate-outcome coverage, rule proposals and operating-cost review.
4. **Quarterly** — financial, valuation, research-object, data-source and graduation-readiness refresh acceptance.
5. **Annual** — strategy effectiveness, rule effectiveness, source resilience, Canonical hygiene and next-year operating plan.
6. **Event-driven** — registered filing, price, thesis, data-quality, pointer or state-change events with idempotency and governed routing.

The cron expressions are interpreted in UTC but documented and governed in `Asia/Shanghai`. They are control-plane schedules, not authorization for portfolio action.

## Monitoring and staleness

The monitoring registry covers pointer and Release identity, missing sources, stale data, market-session mismatch, schema or contract failure, Manifest and SHA failure, deterministic replay, partial publication, runtime, retries, artifact volume, state confirmation, unauthorized mutation, duplicate events, internal cost units and missing service-window success.

Staleness is domain-specific. Market prices, real-account state, simulation state, Candidate state, Active Memo triggers, financial statements, valuation context, thesis records, attribution and Canonical pointers do not share one blanket threshold. A stale input may still support historical review while being blocked from current live-action use.

## Cost controls

Each cadence receives an explicit envelope for:

- maximum runtime minutes;
- internal compute-budget units;
- maximum network requests;
- maximum artifact volume;
- maximum retries.

These are operational ceilings, not claims about external vendor prices. A breach stops or defers noncritical work and generates an escalation record. It never upgrades data quality, extends retry loops indefinitely or authorizes silent source substitution.

## Replay and failure recovery

Twelve replay scenarios cover same-input determinism, daily health checks, weekly reviews, month-end, quarter-end, year-end, duplicate events, stale sources, partial publication, timeout and retry budgets, cost and artifact budgets and unauthorized mutation.

Ten explicit failure fixtures must be rejected. On integrity or publication failure, Current cannot be replaced and LKG remains authoritative. A market-specific degradation may produce a health report, but it cannot produce a partially promoted Canonical state.

## Publication products

The accepted stage publishes:

- source binding;
- cadence registry;
- eighteen-step operating runbook;
- monitoring registry;
- staleness policies;
- cost-control registry;
- replay acceptance;
- escalation registry;
- failure-injection report;
- gate matrix;
- quality report, decision, Release, Manifest and FMDL-7E handoff;
- eight domains × 64 buckets = 512 deterministic logical shards.

## Completion boundary

Acceptance means the operating schedules, monitoring semantics, staleness gates, resource ceilings, replay rules and escalation paths are deterministic and fail closed. It does not mean that a new current portfolio state has been confirmed, persistent alpha has been proven, the File Library package has been refreshed or automated trading is authorized.

## Required exit

`FMDL7D_SCHEDULED_OPERATIONS_MONITORING_STALENESS_AND_COST_CONTROLS_ACCEPTED`

## Next gate

`FMDL-7E_FAILURE_RECOVERY_CLEAN_ROOM_RESTORE_AND_CANONICAL_REFRESH`
