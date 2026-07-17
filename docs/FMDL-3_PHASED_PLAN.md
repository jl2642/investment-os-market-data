# FMDL-3 — Phased Execution Plan

## 1. Program objective

Build an auditable, point-in-time financial and valuation layer for the full eligible A-share Universe, suitable for downstream Public Equity Investing research and Investment OS decision gates.

The program is intentionally sequenced. No later phase may bypass an unresolved source, temporal or normalization defect from an earlier phase.

## 2. Frozen phase order

1. `FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map`
2. `FMDL-3B — Financial Statement Store & Normalization`
3. `FMDL-3C — Financial Quality, Growth & Balance-Sheet Factors`
4. `FMDL-3D — Valuation, Capitalization, Dividend & Shareholder-Return Layer`
5. `FMDL-3E — Incremental Refresh, Replay & Final Acceptance`

## 3. FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map

### 3.1 Purpose

Select feasible free or free-tier source routes and convert the architecture-level PIT policy into source-specific operating rules.

### 3.2 Required workstreams

#### A. Source inventory

Benchmark candidate routes for:

- issuer and exchange filings;
- structured financial statements;
- announcement dates and timestamps;
- revised and restated filings;
- current and historical share counts;
- market capitalization and valuation fields;
- dividend and buyback events;
- industry and sector-profile identity.

#### B. Real issuer benchmark

Use a deterministic stratified sample that covers:

- Shanghai and Shenzhen Main Boards;
- STAR Market;
- ChiNext;
- Beijing Stock Exchange where source support exists;
- general non-financial companies;
- banks;
- insurers;
- securities companies;
- negative-earnings and pre-profit issuers;
- different filing periods and revision cases.

The benchmark must measure actual retrieval success, field completeness, latency, source stability and data-definition consistency on GitHub-hosted runners.

#### C. PIT source contract

Freeze:

- source-specific announcement-date fields;
- exact timestamp or conservative date-only convention;
- after-close availability treatment;
- filing revision and restatement identity;
- current-only provider restrictions;
- comparative-column treatment;
- provider change detection.

#### D. Coverage map

Publish measured coverage by:

- board;
- sector profile;
- statement type;
- reporting period;
- field family;
- announcement date;
- exact timestamp availability;
- revision-history support;
- valuation and shareholder-return domain.

#### E. Source decision

Select:

- primary route by domain;
- explicit fallback by domain;
- unsupported or audit-only fields;
- retry and degradation policy;
- source storage and redistribution posture.

### 3.3 Deliverables

- `docs/FMDL-3A_SOURCE_BENCHMARK_PLAN.md`
- `docs/FMDL-3A_SOURCE_DECISION.md`
- `docs/FMDL-3A_POINT_IN_TIME_CONTRACT.md`
- `docs/FMDL-3A_COVERAGE_MAP.md`
- `config/fmdl3_source_routes.json`
- `config/fmdl3_availability_policy.json`
- `config/fmdl3_sector_profiles.json`
- source benchmark evidence under `outputs/benchmark/fmdl3a/`
- machine-readable acceptance result.

### 3.4 Hard exit gates

- all required sector profiles represented in the benchmark;
- at least one tested primary route for source index and statements;
- explicit route or unsupported state for every target domain;
- announcement-date availability measured, not assumed;
- no provider presented as historical PIT-capable without revision evidence;
- numeric coverage thresholds frozen from measured results;
- zero unresolved architecture contradictions;
- independent validation PASS;
- trade authority NONE.

### 3.5 Prohibited shortcuts

- choosing a provider from documentation without runner testing;
- using current restated values as historical evidence;
- testing only current Longlist names;
- omitting banks, insurers or securities companies;
- treating missing announcement dates as report-period dates;
- proceeding to full-market extraction without measured runtime and storage design.

## 4. FMDL-3B — Financial Statement Store & Normalization

### 4.1 Purpose

Build the point-in-time source index, raw fact layer, canonical long-form statement store and comparability lineage.

### 4.2 Recommended substeps

#### FMDL-3B-1 — Field Registry & Normalization Pilot

- freeze canonical field taxonomy;
- build raw and normalized schemas;
- pilot representative general and financial-sector issuers;
- validate signs, units, currencies, periods and basis;
- validate restatement version intervals.

#### FMDL-3B-2 — Full-Universe Initial Statement Build

- ingest the accepted Universe;
- shard by deterministic issuer groups;
- publish immutable source-index and statement base;
- quarantine unresolved issuers without blocking accepted coverage;
- measure statement and period completeness.

#### FMDL-3B-3 — Comparability & Restatement Hardening

- detect changed labels and disclosure bases;
- retain original and revised values;
- create comparability bridges;
- detect provider backfills and silent changes;
- validate replay against known revision cases.

#### FMDL-3B-4 — Statement Current & Acceptance

- publish normalized long-form Current;
- generate optional wide views;
- publish missingness and conflict maps;
- freeze Last-known-good and correction policy.

### 4.3 Deliverables

- field registry and sector mappings;
- source index;
- raw fact store;
- normalized statement long table;
- comparability bridge;
- revision ledger;
- statement quality and coverage reports;
- Current and Last-known-good pointers.

### 4.4 Hard exit gates

- zero future facts in replay;
- zero silent restatement overwrite;
- zero source-less decision-grade facts;
- zero duplicate canonical fact versions for the same effective interval;
- balance, subtotal and cash-flow checks preserved when applicable;
- all unresolved conflicts classified;
- accepted Current reproducible from source index and configuration;
- independent validation PASS.

## 5. FMDL-3C — Financial Quality, Growth & Balance-Sheet Factors

### 5.1 Purpose

Transform accepted point-in-time statements into transparent issuer-level factor evidence.

### 5.2 Factor families

#### Profitability and return

- ROE;
- ROA where meaningful;
- ROIC for supported non-financial issuers;
- gross, operating and net margins;
- margin stability and trend.

#### Cash conversion and accruals

- operating cash flow versus earnings;
- free-cash-flow conversion where supported;
- accrual intensity;
- cash earnings quality;
- working-capital cash consumption.

#### Growth

- revenue growth;
- operating profit growth;
- net income growth;
- operating cash-flow growth;
- multi-period growth consistency;
- growth-quality and base-effect diagnostics.

#### Balance sheet and resilience

- leverage and net debt where meaningful;
- interest coverage;
- current and quick liquidity where meaningful;
- debt maturity or short-term debt burden where available;
- capital intensity;
- asset-turnover and working-capital efficiency;
- sector-specific capital and solvency factors.

### 5.3 Applicability contract

Every factor must state:

- sector profile;
- required inputs;
- calculation formula;
- PIT availability rule;
- denominator validity;
- applicability state;
- missingness behaviour;
- quality and confidence;
- source lineage;
- rank eligibility.

### 5.4 Deliverables

- `config/fmdl3_factor_contract.json`
- factor schemas;
- factor engine;
- wide and long factor Current;
- factor status and coverage tables;
- sector-aware applicability map;
- full-market candidate and validation artifacts.

### 5.5 Hard exit gates

- zero future input use;
- zero neutral fill;
- zero invalid denominator published as valid;
- zero ordinary-company metric forced onto an excluded financial profile;
- formulas and input lineage preserved;
- factor availability and quality measured by sector profile;
- deterministic replay for accepted sample and full-market Current;
- independent validation PASS.

## 6. FMDL-3D — Valuation, Capitalization, Dividend & Shareholder-Return Layer

### 6.1 Purpose

Create timestamp-aligned market-value and shareholder-return evidence using accepted financial denominators and corporate-action states.

### 6.2 Required workstreams

#### Capitalization

- accepted price timestamp;
- total shares and free-float shares;
- share-count effective dates;
- issuance, repurchase, split and conversion adjustments;
- total and free-float market capitalization.

#### Valuation

- PE TTM and other accepted earnings bases;
- PB;
- PS;
- supported EV metrics;
- valuation validity and invalidity reasons;
- sector-aware ratio families;
- current and historical valuation state.

#### Shareholder return

- cash dividends;
- payout and retention metrics;
- dividend stability;
- buyback announcements and completion evidence;
- issuance and dilution evidence;
- shareholder-yield components when supported.

### 6.3 Deliverables

- valuation and share-count contracts;
- corporate-action/effective-share-count layer;
- valuation snapshot Current;
- dividend and shareholder-return event Current;
- denominator-validity map;
- valuation coverage and staleness report.

### 6.4 Hard exit gates

- zero future financial denominator use;
- zero future share-count use;
- zero negative or zero earnings represented as valid attractive PE;
- zero unsupported EV metric published as valid;
- valuation numerator and denominator timestamps preserved;
- corporate-action lineage complete for accepted rows;
- independent validation PASS.

## 7. FMDL-3E — Incremental Refresh, Replay & Final Acceptance

### 7.1 Purpose

Turn the accepted FMDL-3 datasets into an operating Current with scheduled refresh, failure recovery and point-in-time replay evidence.

### 7.2 Refresh lanes

Different data families may require different cadences:

- filing and announcement discovery;
- statement and revision ingestion;
- daily capitalization and valuation refresh;
- dividend and buyback event refresh;
- periodic full reconciliation;
- correction and repair runs.

Exact schedules are frozen after source behaviour is measured.

### 7.3 Replay and stability

FMDL-3E must include:

- same-input deterministic replay;
- known historical filing-date replay;
- known restatement replay;
- valuation denominator availability replay;
- provider-change detection;
- Current versus archived release reconciliation;
- coverage and staleness stability across multiple refreshes.

### 7.4 Final publication

Publish:

- `outputs/fmdl3/current/FMDL3_FINAL_RELEASE.json`;
- accepted manifests and Current pointers;
- `outputs/status/FMDL3_LAST_SUCCESS.json`;
- coverage, limitation and source-conflict states;
- handoff contract for FMDL-4.

### 7.5 Hard exit gates

- all global zero-tolerance gates pass;
- source, statement, factor, valuation and shareholder-return Current states are mutually consistent;
- Last-known-good survives simulated failures;
- point-in-time replay passes;
- controlled limitations are explicit;
- no live candidate-pool promotion;
- trade authority NONE;
- final independent validation PASS.

## 8. Program-wide development rules

### 8.1 Full-market first

Collection and normalization target the full eligible A-share Universe. The FMDL-2 Longlist may prioritize benchmark review but cannot define fundamental coverage.

### 8.2 Pilot before full build

Every new source route, statement model and specialized sector profile requires a representative pilot before full-market execution.

### 8.3 Candidate before Current

No phase writes directly to Current. Candidate output must pass schema, quality and independent validation before publication.

### 8.4 Failure preserves LKG

A failed or quarantined candidate cannot replace Last-known-good.

### 8.5 Evidence before score

A factor or valuation score cannot exist without valid canonical facts and source lineage.

### 8.6 No hidden manual patch

Manual corrections require an explicit repair input, reason, source and immutable lineage. Silent edits to published rows are prohibited.

## 9. Acceptance sequence

The authorized execution chain is:

```text
FMDL-3 Architecture Acceptance
  -> FMDL-3A Source Benchmark & PIT Contract
  -> FMDL-3B Statement Store & Normalization
  -> FMDL-3C Financial Factors
  -> FMDL-3D Valuation & Shareholder Return
  -> FMDL-3E Refresh, Replay & Final Acceptance
  -> FMDL-4 Research Handoff
```

The immediate next task after this plan is accepted is:

`FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map`
