# FMDL-6X1-C — Source, Cost & Execution Route Revalidation

## Objective

Revalidate the source routes required to turn the accepted US research-universe boundary into a production build contract. This phase tests live access, parseability, latency, payload lineage, cost class and GitHub-hosted execution suitability. It does not build the full Security Master, history, factors, candidate pool or portfolio state.

## Required live capability groups

1. **Current security directory** — Nasdaq Trader `nasdaqlisted`, `otherlisted` and the combined directory archive.
2. **SEC identity, submissions and financial facts** — issuer/ticker/exchange reference, submissions history and XBRL company facts.
3. **Market history and corporate actions** — zero-cost fallback observations for daily prices, dividends and splits, explicitly labelled non-decision-grade until reconciled.
4. **FX reference** — official ECB routes where possible, with a free support route for operational continuity.

## Controlled gaps

The phase must not fabricate complete free coverage where none is confirmed.

- Historical delistings, symbol changes and venue transfers require an archival-reconstruction or licensed-source strategy in FMDL-6X1-D.
- ADR underlying, depositary and ratio evidence requires SEC/issuer/depositary filings and a controlled manual-review queue.
- ETF/ETN/CEF and special-instrument classification requires exchange flags plus SEC security descriptions; unresolved conflicts are quarantined.

A controlled gap is acceptable only when it is explicit, has an assigned downstream action and cannot silently contaminate point-in-time data.

## Cost policy

- Current paid-subscription budget: USD 0.
- Paid or API-key routes may be documented but cannot be activated without user approval.
- GitHub Actions soft ceiling: 300 minutes per month for this route family.
- A failed route cannot replace Last-known-good.

## Decision states

Routes may be classified as approved primary, approved support, approved fallback non-decision-grade, controlled external official execution, controlled manual official evidence, gap requiring reconstruction/licensing, or rejected.

## Permanent boundaries

- Candidate, simulation, real-account and order mutations remain zero.
- No live Security Master rows are created.
- `trade_authority = NONE`.

## Required exit

`FMDL6X1C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION_ACCEPTED`

Next gate:

`FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF`
