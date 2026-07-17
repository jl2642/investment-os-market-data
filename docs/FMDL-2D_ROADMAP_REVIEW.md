# FMDL Roadmap Review after FMDL-2D

## Conclusion

The overall sequence remains valid:

1. FMDL-3 — Financial & Valuation Data Hardening
2. FMDL-4 — Public Equity Investing + Investment OS Integration
3. FMDL-5 — Hong Kong Stock Connect Adapter
4. FMDL-6 — US Equity Research Benchmark Pool
5. FMDL-7 — Operating Acceptance

The sequence should not be reordered. FMDL-3 must precede FMDL-4 because the current market-behaviour Longlist cannot support professional investment conclusions without financial quality, capital structure, valuation, dividends and sector-specific evidence.

## Required refinement

The phase labels remain, but FMDL-3 and FMDL-4 should be decomposed before execution.

### FMDL-3 — Financial & Valuation Data Hardening

Recommended subphases:

- **FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map**
  - free/free-tier source inventory;
  - statement, valuation and market-cap field definitions;
  - reporting-period, announcement-date and restatement rules;
  - sector-specific schema boundaries;
  - missingness and provider-conflict policy.
- **FMDL-3B — Financial Statement Store & Normalization**
  - income statement, balance sheet and cash flow;
  - TTM and annualized fields;
  - announcement-date availability control;
  - restatement lineage and audit hashes.
- **FMDL-3C — Financial Quality, Growth & Balance-Sheet Factors**
  - ROE/ROIC, margins, cash conversion, growth, leverage and resilience;
  - sector-aware exclusions and specialized metrics.
- **FMDL-3D — Valuation, Capitalization, Dividend & Shareholder-Return Layer**
  - total and free-float market cap;
  - PE/PB/PS and available enterprise-value metrics;
  - dividend yield/stability, payout and buyback evidence;
  - explicit handling of negative or non-meaningful denominators.
- **FMDL-3E — Incremental Refresh, Replay & Final Acceptance**
  - scheduled updates;
  - point-in-time anti-leakage tests;
  - provider reconciliation;
  - coverage, staleness and Last-known-good publication.

FMDL-3 should begin with a formal overall plan and phased execution contract. It is materially more complex than FMDL-2 because accounting definitions, announcement dates, restatements, sector exceptions and valuation denominators can create silent look-ahead or false comparability.

### FMDL-4 — Public Equity Investing + Investment OS Integration

Recommended subphases:

- **FMDL-4A — Research Handoff Contract**
  - convert Longlist rows into Public Equity Investing idea-generation packets;
  - include exposure proof, expectations risk, first rejection and next workflow;
  - preserve source and score lineage.
- **FMDL-4B — Candidate Research & Graduation**
  - company tearsheet, financial normalization, valuation and catalyst work;
  - candidate rejection/advance decisions;
  - no automatic live-pool promotion.
- **FMDL-4C — Investment OS Re-entry & Decision-Gate Integration**
  - accepted candidate-pool interface;
  - RCM/position-sizing/capital-migration compatibility;
  - simulation and real-capital authority boundaries;
  - explicit user-confirmation gates.
- **FMDL-4D — Closed-Loop Attribution & Thesis Tracking**
  - monitor promoted names;
  - connect thesis status, catalysts, attribution and exit criteria;
  - feed outcomes back into screening research without self-confirming bias.

## FMDL-5 and FMDL-6

The Hong Kong Stock Connect Adapter and US Equity Research Benchmark Pool remain correctly placed after the A-share research and decision loop is connected. Their contracts should reuse the accepted FMDL architecture but preserve market-specific calendars, identifiers, corporate actions, accounting regimes, currencies and trading constraints.

## FMDL-7

FMDL-7 remains the final operating acceptance phase. It should test scheduled reliability, failure recovery, stale-source handling, Last-known-good behavior, cost controls, user-facing runbooks, monitoring and cross-project portability. It should not be used to postpone unresolved data or decision-contract defects from FMDL-3 or FMDL-4.
