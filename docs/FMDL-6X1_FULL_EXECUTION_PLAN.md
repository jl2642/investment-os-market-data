# FMDL-6X1 — Channel & Investable-Universe Refresh: Fixed Execution Plan

## Purpose

Convert the accepted FMDL-6 resume-ready pilot into a controlled, research-production-ready US-equity program without pretending that the user currently has a US brokerage channel.

## Fixed phase sequence

1. `FMDL-6X1-A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT`
2. `FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY`
3. `FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION`
4. `FMDL-6X1-D_FULL_BUILD_CONTRACT_AND_FMDL6X2_HANDOFF`
5. `FMDL-6X1-FINAL_OPERATIONAL_ACCEPTANCE`

The phase has exactly five planned rounds. At most two targeted repair rounds are permitted, and only for a failed acceptance gate, a material source break, or a material identity/schema defect.

## Governing distinction

FMDL-6X1 uses two independent gates:

- **Research Production Gate** — authorizes construction of a channel-agnostic US research universe, data history, factors, screening and research objects.
- **Brokerage & Real-Account Gate** — authorizes broker-specific eligibility, simulation-to-real migration and real-account recommendations. This remains closed until a real channel and account constraints exist.

Opening the Research Production Gate never opens the Brokerage & Real-Account Gate.

## Phase boundaries

### FMDL-6X1-A

Audit the accepted pilot and Release-8 canonical package; preserve the pilot as immutable prior evidence; split the former single activation gate into the two gates above; authorize planning and implementation of research production while keeping account integration blocked.

### FMDL-6X1-B

Define the anticipated research universe independently of any broker. Separate `RESEARCH_ELIGIBLE`, `CHANNEL_ELIGIBILITY_PENDING`, and `EXCLUDED`. Freeze instrument types, venues, identity semantics, ADR/FPI/REIT handling and explicit exclusions.

### FMDL-6X1-C

Revalidate official and free/free-tier routes under current conditions. Measure access, coverage, latency, stability, rate limits, revision/PIT capability, cost and GitHub-hosted execution suitability. No silent substitution is permitted.

### FMDL-6X1-D

Freeze the full-build contract: Security Master scope, active/delisted identity history, market history, corporate actions, SEC filings/facts, storage, sharding, Current/Release/Archive/LKG, quality gates, cost ceilings and FMDL-6X2 entry conditions.

### FMDL-6X1-FINAL

Perform independent validation, same-input replay, failure injection, clean-room restore and immutable publication. Promote only the research-production authorization; retain zero candidate, simulation, real-account and order mutation.

## Permanent authority boundary

`trade_authority = NONE`.

No automatic order execution is part of FMDL-6X1 or any later FMDL phase. Real-account action remains user-confirmed and broker/account-specific.
