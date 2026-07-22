# FMDL-6-0 — Deferred Full-Build Plan

## Status

`DEFERRED_NOT_AUTHORIZED`

This plan preserves the future US equity production roadmap without activating it.

## Activation prerequisite

The full build remains closed until:

1. the user has a real US market investment channel;
2. the broker/account tradable-security scope is documented;
3. account currency, tax and execution constraints are documented;
4. FMDL-6 pilot interfaces are revalidated against current endpoint and cost conditions;
5. the user explicitly approves the full build.

## FMDL-6X1 — Channel & Investable-Universe Refresh

Purpose:

- bind the real broker or investment channel;
- define eligible exchanges, instruments and account restrictions;
- decide whether ADRs, REITs, ETFs, fractional shares or OTC securities are permitted;
- define base currency, FX conversion, tax, settlement and trading-calendar constraints;
- refresh the full-build source and cost decision.

Exit gate:

`US_CHANNEL_AND_INVESTABLE_UNIVERSE_ACCEPTED`

## FMDL-6X2 — Full Universe & Historical Build

Purpose:

- build the approved full Security Master;
- preserve issuer/security/listing/share-class identity history;
- include active, changed, acquired and delisted identities as required by the approved scope;
- backfill market history, corporate actions, SEC filings and financial facts;
- build Current, Immutable Release, Archive, Last-success and Last Known Good recovery.

This phase remains forbidden during the 24-security pilot.

## FMDL-6X3 — Factor, Screening & Research Production

Purpose:

- establish US-market factor definitions and sector/accounting profiles;
- build production factor history and screening funnels;
- create research Longlists and Public Equity Research Objects;
- define valuation, KPI, catalyst, Prove/Kill and graduation rules;
- prove point-in-time replay and controlled source lineage.

Research graduation must remain separate from candidate admission.

## FMDL-6X4 — Investment OS & Portfolio Integration

Purpose:

- add cross-market duplicate-exposure and issuer-level concentration review;
- create candidate re-entry and Shadow Track routes;
- define simulation admission and real-account admission as separate gates;
- bind actual account constraints and user confirmation;
- perform final operational acceptance.

No automatic order execution is included. `trade_authority = NONE` remains the permanent boundary unless a separate explicitly authorized broker-integration program is created.

## Resume rule

When the activation gate opens, a new conversation must not reconstruct the roadmap from memory. It must read:

1. `FMDL6_LAST_SUCCESS` or the latest FMDL-6 phase pointer;
2. `FMDL6_START_HERE`;
3. the latest Activation Gate;
4. the latest Deferred Backlog;
5. the pilot source benchmark and failure report;
6. the user's documented channel constraints.

The next implementation plan must then update only facts that may have changed, not redesign the accepted identity and state architecture without change control.
