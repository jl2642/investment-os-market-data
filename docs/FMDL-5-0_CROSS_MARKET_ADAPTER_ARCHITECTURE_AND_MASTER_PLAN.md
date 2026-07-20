# FMDL-5-0｜Cross-Market Adapter Architecture & Master Plan

## 1. Objective

Extend the accepted A-share Investment OS to Hong Kong Stock Connect and U.S.-listed equities without rebuilding the core decision system.

Base Canonical Release: `INVESTMENT_OS_R8_20260720_501345e84562`.

FMDL-5 and FMDL-6 adapt market identity, calendars, currencies, prices, corporate actions, disclosures, accounting taxonomies, market factors and portfolio exposure semantics. They reuse the accepted Evidence Envelope, Research Object, graduation, state-domain separation, Thesis, Attribution, Feedback, Current/Immutable/Archive/LKG and zero-trade-authority controls.

## 2. Shared cross-market architecture

```text
Official effective-dated universe
→ Market security master
→ Calendar / currency / FX
→ Price and corporate actions
→ Financial disclosure adapter
→ Point-in-time normalized evidence
→ Market factor extension
→ Existing screening funnel
→ Existing Public Equity Research router
→ Existing Candidate / Simulation / Real-account gates
→ Existing Thesis / Attribution / Feedback
```

No adapter may bypass the following separations:

```text
Research graduation ≠ candidate admission
Candidate admission ≠ simulation admission
Simulation admission ≠ real-account admission
Real-account action requires user confirmation
trade_authority = NONE
```

## 3. FMDL-5 fixed implementation plan — 8 formal subphases

1. `FMDL-5A` Market Contract & Universe Boundary
2. `FMDL-5B` HK Security Master & Market Semantics
3. `FMDL-5C` Price, Volume, Corporate Action & FX Store
4. `FMDL-5D` HKEX Disclosure & Financial Normalization
5. `FMDL-5E` Hong Kong Factor & Screening Adapter
6. `FMDL-5F` Public Equity Research Adapter
7. `FMDL-5G` Investment OS Integration
8. `FMDL-5-FINAL` Operational Acceptance

Maximum total rounds including repairs: **10**.

The official Southbound eligible-security lists are effective-dated and distinguish active eligibility from later changes. FMDL-5A must preserve buy-and-sell, sell-only, removed, suspended and data-incomplete states rather than keeping an undifferentiated ticker list.

## 4. FMDL-6 fixed implementation plan — 10 formal subphases

1. `FMDL-6A` U.S. Universe & Security Contract
2. `FMDL-6B` Ticker, CIK & Entity Identity
3. `FMDL-6C` U.S. Price & Corporate Action Store
4. `FMDL-6D` SEC Financial Store
5. `FMDL-6E` U.S. Financial & KPI Normalization
6. `FMDL-6F` U.S. Factor Engine
7. `FMDL-6G` U.S. Screening Funnel
8. `FMDL-6H` Public Equity Research & Valuation Adapter
9. `FMDL-6I` Investment OS Cross-Market Integration
10. `FMDL-6-FINAL` Operational Acceptance

Maximum total rounds including repairs: **13**.

The SEC adapter will use unauthenticated `data.sec.gov` submissions and XBRL APIs and the nightly bulk archives for large retrievals. It must preserve filing timestamp, fiscal period, amendment/restatement status and taxonomy lineage.

## 5. Free-source hierarchy

### Hong Kong

1. HKEX Southbound eligible-security lists and Stock Connect notices
2. HKEXnews issuer disclosures
3. Free market-price provider with explicit fallback and date validation
4. Derived data only when raw source and transformation are registered

### United States

1. SEC EDGAR submissions and XBRL APIs
2. SEC nightly bulk archives
3. Exchange/security-master official references where available
4. Free market-price and corporate-action provider with explicit fallback

A third-party source may provide convenience, but may not silently become the authority for eligibility, entity identity or official filings.

## 6. One-subphase completion contract

Every formal subphase must contain all of the following before it is accepted:

- Contract
- Implementation
- Tests
- GitHub Actions CI
- Acceptance decision
- Main publication with Current, immutable Release, Archive and Last-success

A repair round is allowed only for a failed acceptance gate, upstream source break or material schema defect. Cosmetic renaming, open-ended analysis and unscoped feature expansion do not justify a new round. Any additional split requires written change control identifying the blocker, new output and unchanged downstream gate.

## 7. FMDL-5 final acceptance targets

- Complete active Southbound buy-and-sell universe with effective dates
- Security identity and A/H mapping
- Price, corporate-action, currency and calendar lineage
- Governed 100-name screening Longlist
- 15–20 formal Research Objects
- 5–8 graduated or Shadow Track cases
- Required A/H, high-dividend, WVR/internet and corporate-action cases
- State-domain isolation, failure injection, rollback and LKG
- Zero automatic candidate, simulation, real-account or order mutation

## 8. FMDL-6 final acceptance targets

- 1,000–1,500 investable listed-equity benchmark universe
- Ticker/CIK/entity and share-class/ADR mapping
- SEC submissions and Company Facts point-in-time store
- GAAP/IFRS FPI and non-GAAP/SBC normalization controls
- 150-name Longlist, 30-name research cohort, 10 formal Research Objects
- 3–5 benchmark graduation cases
- Cross-market exposure, currency and duplicate-company controls
- State-domain isolation, failure injection, rollback and LKG
- Zero automatic trading authority

## 9. Exit and next gate

FMDL-5-0 exits only when the master plan is schema-valid, tests and CI pass, and the accepted plan is published on `main`.

Next gate: `FMDL-5A_MARKET_CONTRACT_AND_UNIVERSE_BOUNDARY`.
