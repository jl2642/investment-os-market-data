# FMDL-6X4-E — Cross-market Comparability & Operating Runbook

## Objective

FMDL-6X4-E converts the accepted A-share, Hong Kong Stock Connect and US research-adapter states into one auditable cross-market operating framework. It defines what may be compared, what requires explicit normalization, what remains context-only, and what must fail closed.

The stage does **not** create a global stock rank, merge incompatible factor scores, mutate the Investment OS Candidate Pool, open formal simulation, connect a brokerage channel or issue an investment recommendation.

## Authoritative entry state

- FMDL-6X4-D Release 45 is accepted and opens only the 6X4-E gate.
- Investment OS Release 8 remains the accepted A-share canonical base.
- FMDL-5-FINAL Release 18 remains the accepted Hong Kong Stock Connect overlay.
- FMDL-6X3-FINAL and FMDL-6X4-D remain the accepted US research-production and simulation-control sources.
- `trade_authority = NONE` across all sources and outputs.

## Cross-market boundary

Three market capability records are registered:

1. **A-share** — operational existing Investment OS with the accepted full-market evidence chain, research Longlist and human-governed candidate core.
2. **Hong Kong Stock Connect** — operational FMDL-5 overlay with 644 Southbound securities, 613 common equities, 28 factors, 100 Longlist names and bounded formal research objects.
3. **US equity** — research architecture operational over 8,785 securities, but formal candidate, decision-grade market-data, valuation, peer and performance-claim gates remain closed.

Operational capability is not treated as proof of persistent alpha. Market coverage counts are not treated as directly comparable investment opportunity counts.

## Comparability model

Fourteen dimensions are assessed separately for each market:

- Security identity
- Issuer and cross-listing relationships
- Instrument profile
- Market-data grade
- Accounting standard and reporting periodicity
- Currency and FX
- Corporate actions
- Sector and industry taxonomy
- Factor definition
- Valuation readiness
- Peer-group readiness
- Research-object maturity
- Candidate-graduation authority
- Performance-attribution grade

Each Market × Dimension record receives one of three classes:

- `DIRECT_WITH_EXPLICIT_NORMALIZATION`
- `PARTIAL_CONTEXT_ONLY`
- `NOT_COMPARABLE_FAIL_CLOSED`

No dimension permits ticker-only matching, neutral fill, silent source substitution, inferred TTM, unregistered accounting-period conversion, mixed local-currency comparison or a forced common score.

## Operating runbook

The frozen twelve-step runbook is:

1. Entry-gate and pointer binding
2. Source freshness and data-grade check
3. Market-specific ingestion and QC
4. Security identity and cross-listing reconciliation
5. Accounting, currency and corporate-action normalization
6. Factor, valuation and peer comparability assessment
7. Research evidence, thesis and falsifier refresh
8. Cross-market duplication and replacement review
9. Candidate graduation and human-approval gate
10. Shadow attribution and simulation control
11. Failure recovery, LKG and rollback
12. Operating review, publication and FINAL handoff

The cadence registry freezes Daily, Weekly, Monthly, Quarterly and Event-driven controls. `EACH_RUN` controls execute at entry and recovery boundaries.

## Fail-closed controls

The following conditions block or downgrade outputs:

- stale or mismatched as-of data;
- data-grade downgrade;
- Security or Issuer identity collision;
- unresolved A/H, ADR or share-class duplication;
- accounting-period or accounting-standard mismatch;
- missing FX or corporate-action evidence;
- factor-definition or universe mismatch;
- missing valuation or peer readiness;
- missing, withdrawn or expired human approval;
- Current, Release, Manifest or deterministic-replay mismatch.

The required recovery order is immutable Release, Current and normalized output under the accepted Last-success and LKG pointers.

## Published products

The stage publishes:

- Cross-market Capability Report
- Comparability Matrix
- Normalization Rule Registry
- Operating Runbook and Cadence Registry
- Escalation and Recovery Report
- Operating Queues
- Final Gate Report
- Source Binding
- FMDL-6X4-FINAL Handoff
- Quality Report, Decision, Manifest and deterministic registry shards

Seven domains × 64 buckets produce 448 deterministic logical shards.

## Completion boundary

Acceptance means the three-market capability boundaries, dimension-level comparability matrix and operating runbook are deterministic, recoverable and fail closed. It does not mean that the markets share one factor model, one valuation basis, one peer taxonomy, one performance record or one investable global ranking.

## Required exit

`FMDL6X4E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK_ACCEPTED`

## Next gate

`FMDL-6X4-FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE`
