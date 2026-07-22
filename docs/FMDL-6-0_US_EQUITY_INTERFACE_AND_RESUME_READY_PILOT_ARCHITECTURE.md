# FMDL-6-0 — US Equity Interface & Resume-Ready Pilot Architecture

## 1. Decision

FMDL-6 is no longer authorized as an immediate full-universe US equity production build.

The accepted execution posture is:

`INTERFACE_AND_SMALL_BENCHMARK_ONLY`

The current objective is to build, test, freeze and publish a **resume-ready US equity interface pilot** that can be restored from GitHub state without relying on chat history. The pilot must not create a US candidate pool, simulation exposure, real-account exposure, order, broker connection or trade authority.

## 2. Why FMDL-6 remains phased

A 24-security pilot is smaller than a full-market build, but the architecture remains non-trivial because the following problems still exist:

- issuer, security, listing and share-class identity are not interchangeable;
- ticker and exchange identifiers can change while the economic issuer continues;
- one issuer may have multiple listed share classes;
- ADRs and foreign private issuers require an explicit link to the underlying issuer or home-market security;
- SEC filings require filing, accession, acceptance-time, taxonomy and revision lineage;
- US GAAP and IFRS foreign private issuer facts are not mechanically identical;
- splits, dividends, acquisitions, spin-offs, delistings and successor entities affect historical continuity;
- free market-data interfaces may be rate-limited, delayed, revised or unavailable on GitHub runners;
- point-in-time availability and Last Known Good controls are required before any research use.

For these reasons, FMDL-6-0 freezes a bounded sequence instead of executing one monolithic smoke test.

## 3. Current program sequence

FMDL-6-0 is the architecture gate. The six post-architecture phases are:

1. **FMDL-6A — US Market Contract & Security Identity**
2. **FMDL-6B — Source Interface & Access Benchmark**
3. **FMDL-6C — 24-Security Benchmark Pool**
4. **FMDL-6D — Minimal End-to-End Data Chain**
5. **FMDL-6E — Quality, Failure & Cost Benchmark**
6. **FMDL-6-FINAL — Resume-Ready Operational Acceptance**

The total planned sequence is seven rounds including FMDL-6-0. The hard cap is nine rounds including targeted repairs. Repair rounds are permitted only for failed acceptance gates, upstream source breaks or material schema/identity defects.

## 4. Controlled supersession of the historical plan

`config/fmdl5_0_cross_market_master_plan.json` remains an immutable historical record. Its original FMDL-6 design described a ten-subphase full US equity build.

FMDL-6-0 does not rewrite or delete that accepted record. It supersedes only the **execution scope**:

- original full-build logic is preserved as deferred backlog;
- current authorization is limited to interface, identity, small-sample data and operational recovery;
- full-universe, factor, screening, research-production and portfolio-integration work is closed until activation.

## 5. Identity architecture

The pilot must separate:

- `ISSUER_ID`
- `SECURITY_ID`
- `LISTING_ID`
- `SHARE_CLASS_ID`
- `CIK`
- `TICKER`
- `EXCHANGE_MIC`
- `INSTRUMENT_TYPE`
- `ADR_UNDERLYING_LINK`
- `PREDECESSOR_SUCCESSOR_LINK`
- effective-from and effective-to timestamps

The canonical security identifier pattern is:

`US:<EXCHANGE_MIC>:<TICKER>:<SHARE_CLASS_OR_INSTRUMENT_CLASS>`

This pattern is a repository identity key, not a broker order symbol.

## 6. Pilot universe boundary

The 24-security benchmark may include:

- US exchange-listed common stocks;
- selected ADRs or foreign private issuers;
- selected equity REITs.

The pilot excludes:

- ETFs and mutual funds;
- closed-end funds;
- preferred stock;
- warrants, rights and units;
- options;
- OTC securities;
- crypto assets.

The benchmark pool is a technical failure-mode test set. It is not a research Longlist, candidate pool or investment recommendation.

## 7. Required interfaces

The architecture requires four interface families:

1. SEC EDGAR identity, submissions and filing metadata;
2. SEC Company Facts / XBRL financial facts;
3. official US exchange or regulatory listed-security reference;
4. free or free-tier daily market, corporate-action and FX data with explicit fallbacks.

FMDL-6-0 does not claim that any interface is already Decision-grade. FMDL-6B must benchmark access, latency, history, rate limits, GitHub Actions compatibility, fields, failure modes and fallback posture.

## 8. Phase exit contracts

### FMDL-6A

Must publish the market boundary, security identity contract, canonical schema and exclusion policy.

### FMDL-6B

Must publish the source registry, access benchmark, fallback taxonomy and source-route decision.

### FMDL-6C

Must publish exactly 24 technical benchmark securities with case coverage, identity bindings and explicit non-candidate authority.

### FMDL-6D

Must publish a small sample of price, corporate action, SEC submission and financial facts with point-in-time availability and source lineage.

### FMDL-6E

Must prove failure handling, Last Known Good preservation, same-input replay and resource/cost scaling estimates.

### FMDL-6-FINAL

Must publish Current, Immutable Release, Archive, Last-success, START_HERE, Activation Gate and Deferred Backlog.

## 9. Deferred full-build phases

The following phases are preserved but not authorized:

- `FMDL-6X1_CHANNEL_AND_INVESTABLE_UNIVERSE_REFRESH`
- `FMDL-6X2_FULL_UNIVERSE_AND_HISTORICAL_BUILD`
- `FMDL-6X3_FACTOR_SCREENING_AND_RESEARCH_PRODUCTION`
- `FMDL-6X4_INVESTMENT_OS_AND_PORTFOLIO_INTEGRATION`

They can be activated only after the user has a real US investment channel, the tradable scope and account constraints are documented, pilot interfaces are revalidated, and the user explicitly approves a full build.

## 10. Resume-ready standard

A future clean conversation must be able to restore the exact state in this order:

1. `outputs/status/FMDL6_0_LAST_SUCCESS.json`
2. `outputs/fmdl6_0/current/FMDL6_START_HERE.md`
3. `outputs/fmdl6_0/current/FMDL6_0_RELEASE.json`
4. `outputs/fmdl6_0/current/FMDL6_ACTIVATION_GATE.json`
5. `outputs/fmdl6_0/current/FMDL6_DEFERRED_BACKLOG.json`

Chat history is not a required recovery dependency.

## 11. Permanent boundaries

- research graduation is not candidate admission;
- candidate admission is not simulation admission;
- simulation admission is not real-account admission;
- real-account action requires user confirmation;
- the 24-security pool is not a candidate pool;
- completion of the pilot is not completion of US investment capability;
- `trade_authority = NONE`.

## 12. Exit and next gate

Expected exit status:

`FMDL6_0_US_EQUITY_RESUME_READY_PILOT_ARCHITECTURE_ACCEPTED`

Next gate:

`FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY`
