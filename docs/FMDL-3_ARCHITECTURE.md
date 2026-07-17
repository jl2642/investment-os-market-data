# FMDL-3 — Financial & Valuation Data Hardening Architecture

## 1. Purpose

FMDL-3 extends the accepted A-share market-data and screening layer with auditable financial facts, normalized statements, financial-quality factors, valuation, capitalization, dividends and shareholder-return evidence.

The phase exists because market behaviour alone cannot support a professional investment conclusion. The accepted FMDL-2 Longlist answers **who deserves research attention first**. FMDL-3 adds the accounting and valuation evidence required to decide **what must be rejected, what remains investable, and what can be handed to Public Equity Investing for issuer-level research**.

FMDL-3 is a data and evidence layer. It does not make final investment recommendations and cannot create trade permission.

## 2. Architecture state

`FROZEN_FOR_FMDL3A_EXECUTION`

The architecture and execution sequence are frozen for source benchmarking. Exact providers, measured coverage thresholds and source-specific fallbacks are deliberately deferred to FMDL-3A, where they will be tested on real A-share issuers and GitHub-hosted runners.

## 3. System boundary

### 3.1 FMDL-3 owns

- source and filing identity;
- announcement-date and point-in-time availability control;
- raw financial facts with original labels, units and source values;
- normalized income statement, balance sheet and cash-flow statement facts;
- period, sign, currency, scale and basis normalization;
- restatement lineage and disclosure comparability bridges;
- TTM, annualized and period-growth calculations when valid;
- financial quality, growth, cash-conversion, leverage and resilience factors;
- total and free-float capitalization;
- valuation ratios with denominator-validity states;
- dividends, buybacks, issuance and shareholder-return evidence;
- sector-specific statement and factor routing;
- immutable archives, Current, Last-known-good and replay controls.

### 3.2 FMDL-3 does not own

- final company research conclusions;
- business-quality narratives unsupported by canonical facts;
- earnings estimates or consensus unless a later contract explicitly adds an auditable source;
- target prices or valuation conclusions;
- live Investment OS candidate-pool promotion;
- position sizing, portfolio migration or order execution;
- broker connectivity or trade authority.

## 4. Non-negotiable design principles

### 4.1 Point-in-time before breadth

A smaller dataset that can be reconstructed as it was known on a historical date is superior to a broad dataset that silently inserts later restatements or announcements into the past.

### 4.2 Source identity is part of the value

Every decision-grade fact must resolve to a `source_id`, source type, source location, retrieval time, original provider field and canonical field. A number without lineage is not a valid FMDL-3 fact.

### 4.3 Raw and normalized layers remain separate

The original label, value, sign, unit, currency, period and source basis are preserved. Normalization creates a separate canonical fact and never destroys the source representation.

### 4.4 Missing never becomes neutral

Missing financial values remain missing. They are not converted into zero, peer medians, cross-sectional averages, neutral factor ranks or artificial pass states.

### 4.5 Conflicts remain visible

When providers or filings disagree, the conflict is recorded. Current publication requires an explicit preferred-source rule, version rule, reconciliation or controlled exclusion.

### 4.6 Sector comparability is explicit

Banks, insurers and securities companies do not pass through the ordinary industrial-company statement and factor model. Negative-earnings and pre-profit issuers use denominator restrictions rather than nonsensical PE values.

### 4.7 Data authority is not investment authority

FMDL-3 can produce research-grade evidence and research-priority factors. It cannot recommend a purchase, change the simulation or real portfolio, or authorize a trade.

## 5. Temporal and revision model

Every financial fact must distinguish the economic period from the date the market could know the fact.

### 5.1 Required temporal fields

- `report_period_start`
- `report_period_end`
- `fiscal_period_type`
- `announcement_date`
- `announcement_timestamp`
- `available_from`
- `source_retrieved_at`
- `revision_sequence`
- `effective_from`
- `superseded_at`

### 5.2 As-of eligibility

A fact is eligible for an `as_of_timestamp` only when:

1. `available_from <= as_of_timestamp`;
2. the fact version is effective at that timestamp;
3. the source is not invalid or quarantined;
4. the fact is not superseded before the requested timestamp;
5. the requested calculation has all required period inputs available at that timestamp.

### 5.3 Restatements

A restatement creates a new revision. It must not overwrite the value that was visible before the restatement announcement.

Example:

- original annual report announced on 31 March;
- corrected annual report announced on 20 May;
- replay on 30 April uses the original version;
- replay on 31 May uses the corrected version, with lineage to both versions.

### 5.4 Announcement-time fallback

When a verified announcement date is available but an exact timestamp is not, the dataset may apply a conservative market-availability convention defined in FMDL-3A. The fallback must be explicit and must not use `report_period_end` as the availability date.

### 5.5 TTM and derived calculations

TTM, growth, margins, cash conversion and valuation denominators inherit the latest availability timestamp of all required inputs. A derived value cannot be visible earlier than any component used to calculate it.

## 6. Source and evidence hierarchy

FMDL-3A will benchmark actual routes, but the source hierarchy is frozen:

1. issuer or exchange primary filing;
2. regulatory or exchange structured disclosure;
3. auditable standardized public provider;
4. market-data provider for market numerators and share counts;
5. OCR or narrative extraction as a last resort.

Primary filings own disputed accounting values when they are readable and internally consistent. A provider-standardized value may be preferred for scale only when its definition, source lineage and period mapping are auditable.

### 6.1 Evidence labels

FMDL-3 uses the following evidence posture:

- `fact_source_reported`
- `fact_provider_standardized`
- `derived_calculation`
- `issuer_management_claim`
- `management_adjusted`
- `analyst_adjusted`
- `estimate_consensus`
- `stale_source`
- `contradicted_source`
- `missing_required_source`
- `unknown`

`analyst_adjusted` and `estimate_consensus` are not ordinary FMDL-3 outputs unless a later phase adds a controlled source and explicit contract. They remain reserved labels for downstream compatibility.

## 7. Canonical dataset stack

### 7.1 `fmdl3_source_index`

Grain: one row per source document or structured extraction.

Purpose:

- identify the source;
- record issuer, document type, period and announcement date;
- preserve source rank and retrieval state;
- provide the root lineage ID for every downstream fact.

### 7.2 `fmdl3_financial_fact_raw`

Grain: one row per issuer, source, period, original line item and revision.

Required capabilities:

- preserve source label and raw provider field;
- preserve reported scale, unit, currency and sign;
- distinguish reported, adjusted, estimated and narrative facts;
- support duplicate and conflict detection;
- retain document-page, table or structured-field location where available.

### 7.3 `fmdl3_financial_statement_normalized_long`

Grain: one row per issuer, canonical line item, period, basis and revision.

Core fields include:

- `symbol`
- `sector_profile`
- `statement_type`
- `canonical_field_id`
- `original_field_name`
- `report_period_start`
- `report_period_end`
- `fiscal_period_type`
- `value`
- `currency`
- `scale`
- `basis`
- `availability fields`
- `source_id`
- `evidence_label`
- `confidence`
- `record_quality`
- `row_hash`

The long-form statement store is the canonical staging layer. Wide statements are generated views or publication artifacts, not the primary evidence store.

### 7.4 `fmdl3_comparability_bridge`

Grain: one row per affected issuer series and disclosure-basis transition.

It records:

- renamed lines;
- regrouped segments;
- recast periods;
- newly introduced or discontinued disclosures;
- basis changes;
- whether historical values are comparable, comparable with warning, or not comparable;
- model treatment and affected periods.

A changed presentation for one series must not invalidate unrelated statement lines.

### 7.5 `fmdl3_financial_factor_detail`

Grain: one row per issuer, factor, as-of timestamp and factor version.

Initial factor families:

- profitability and return on capital;
- margin level and trend;
- cash conversion and accrual quality;
- revenue, profit and cash-flow growth;
- leverage, coverage and liquidity;
- working-capital and capital-intensity diagnostics;
- balance-sheet resilience;
- dividend capacity and stability;
- sector-specific factors.

Every factor carries applicability, denominator state, input availability, confidence and source lineage.

### 7.6 `fmdl3_valuation_snapshot`

Grain: one row per issuer and market as-of timestamp.

It combines point-in-time financial denominators with accepted market numerators and share-count evidence.

Target families:

- total market capitalization;
- free-float market capitalization;
- PE, PB and PS;
- EV-based metrics when every component is supported;
- dividend yield;
- valuation history and cross-sectional percentiles in a later accepted layer.

Each ratio must state:

- numerator source and timestamp;
- denominator source and availability timestamp;
- denominator basis;
- ratio applicability;
- validity status;
- invalidity reason when not meaningful.

### 7.7 `fmdl3_shareholder_return_event`

Grain: one row per dividend, buyback, issuance or other shareholder-return event.

Events include declaration date, record date, ex-date, payment or completion date, amount, share count effect, status and source lineage.

### 7.8 `fmdl3_final_release`

The FMDL-3 Final Current is a manifest and pointer set over the accepted source index, statements, factors, valuation and shareholder-return datasets. It does not collapse all facts into one untraceable table.

## 8. Sector-profile routing

### 8.1 General non-financial companies

Use the standard three-statement model with ordinary profitability, cash-flow, working-capital, leverage and return-on-capital factors.

### 8.2 Banks

Use bank-specific statement mappings and factors. Ordinary industrial concepts such as EBITDA, net debt and working-capital turnover are not required and may be invalid.

Target specialized concepts may include:

- net interest income and margin when supported;
- loan and deposit growth;
- asset quality and provisions;
- capital adequacy;
- return on equity and book-value valuation;
- dividend capacity.

Exact fields and source feasibility are frozen in FMDL-3A/3B.

### 8.3 Insurance companies

Use insurance-specific mappings. Ordinary revenue and operating-cash-flow comparisons may not be directly comparable.

Target concepts may include premium growth, investment result, reserve or solvency evidence, return on equity, book value and dividend capacity when supported.

### 8.4 Securities and brokerage companies

Use specialized revenue, investment, capital and balance-sheet mappings. Ordinary industrial leverage and margin tests are not automatically applicable.

### 8.5 Pre-profit or negative-earnings issuers

Negative or non-meaningful earnings do not produce a valid PE. The ratio is emitted as unavailable with a structured invalidity reason. PB, PS or EV metrics may be used only when the relevant denominator and sector interpretation are meaningful.

## 9. Normalization rules

### 9.1 Periods

- annual, semiannual, first-quarter and third-quarter reports are explicitly identified;
- cumulative year-to-date and single-quarter values are distinct;
- single-quarter values may be derived from cumulative disclosures only when both component periods are available and comparable;
- fiscal-year differences are recorded, not assumed away.

### 9.2 Currency and scale

- preserve reported currency and scale;
- publish normalized currency and scale separately;
- foreign-currency translation, when needed, requires an explicit FX source and timing rule;
- no silent unit conversion.

### 9.3 Signs

- preserve reported sign;
- map canonical sign conventions by field;
- cash outflows, expenses, debt and contra-items require explicit sign policy;
- provider sign differences are reconciled, not hidden.

### 9.4 Basis

Keep separate:

- reported statutory values;
- provider-standardized values;
- management-adjusted values;
- derived calculations;
- analyst adjustments;
- consensus estimates.

FMDL-3 Current defaults to reported and auditable standardized facts. Other bases require explicit labels and cannot silently replace reported facts.

## 10. Factor applicability and validity

Every factor has an applicability state:

- `APPLICABLE_VALID`
- `APPLICABLE_PARTIAL`
- `NOT_APPLICABLE_SECTOR`
- `INVALID_DENOMINATOR`
- `MISSING_REQUIRED_INPUT`
- `STALE_INPUT`
- `CONFLICTED_INPUT`
- `QUARANTINED`

Cross-sectional ranking may only use factors in a valid or explicitly permitted partial state. Missing, invalid and not-applicable states do not receive neutral scores.

## 11. Valuation semantics

### 11.1 Market capitalization

Market capitalization requires an accepted price, an effective share count and a timestamp-aligned corporate-action state. A stale or mismatched share count is surfaced as a quality issue.

### 11.2 PE

PE is invalid when earnings are zero, negative, stale beyond policy or based on unavailable future information. FMDL-3 does not encode negative PE as a low or attractive valuation.

### 11.3 PB

PB requires a point-in-time book-value denominator and sector interpretation. Negative equity or material non-comparability produces an invalidity state.

### 11.4 PS

PS requires a meaningful revenue concept. It may be inapplicable or misleading for some financial-sector profiles.

### 11.5 Enterprise value

EV-based metrics are published only when market capitalization, debt, cash and relevant adjustments are all supported. Missing preferred equity, minority interests or material lease liabilities must be disclosed according to the frozen formula contract.

### 11.6 Dividend and shareholder-return metrics

Dividend yield, payout and stability use dated declared or paid events according to the metric definition. Announced, approved, ex-date and paid states are distinct.

## 12. Quality and publication model

### 12.1 Zero-tolerance failures

- future information in point-in-time output;
- silent restatement overwrite;
- report period used as availability date;
- decision-grade row without source lineage;
- unresolved provider conflict in published Current;
- invalid denominator published as a valid ratio;
- missing value converted into a neutral factor;
- failed or quarantined candidate replacing Current;
- trade authority created by a data publication.

### 12.2 Controlled warnings

Potential controlled warnings include:

- incomplete source coverage;
- delayed filings;
- announcement date available without exact timestamp;
- provider-standardized value pending primary-source tie-out;
- incomplete sector-specific metrics;
- stale market numerator inside a documented tolerance;
- rounded narrative disclosures unsuitable for exact tie-out.

Warnings must remain visible in manifests and row-level quality states.

### 12.3 Archive and Current

- dated accepted releases are immutable;
- corrections create new releases and lineage;
- Current points to the latest accepted release;
- failure preserves Last-known-good;
- every Current dataset has a manifest, hash and parent release;
- FMDL-3E must demonstrate point-in-time replay before final publication.

## 13. Storage and repository layout

Target logical structure:

```text
config/
  fmdl3_program_contract.json
  fmdl3_source_routes.json
  fmdl3_field_registry.json
  fmdl3_sector_profiles.json
  fmdl3_factor_contract.json
  fmdl3_valuation_contract.json

schemas/
  fmdl3_program_contract.schema.json
  fmdl3_source_index.schema.json
  fmdl3_financial_fact_raw.schema.json
  fmdl3_financial_statement_long.schema.json
  fmdl3_financial_factor.schema.json
  fmdl3_valuation_snapshot.schema.json
  fmdl3_shareholder_return_event.schema.json

outputs/
  financials/source_index/current/
  financials/raw_facts/current/
  financials/statements/current/
  financials/comparability/current/
  financial_factors/current/
  valuation/current/
  shareholder_returns/current/
  fmdl3/current/
  status/
```

Large immutable data may remain sharded and compressed. The repository stores accepted data within practical GitHub limits and preserves manifests for external or artifact-backed evidence where full raw source documents cannot be redistributed.

## 14. Integration with FMDL-2

FMDL-3 consumes:

- canonical symbol identity;
- A-share Universe and listing-status flags;
- accepted market price and turnover Current;
- historical market data where valuation history needs market numerators;
- FMDL-2 screening Longlist for priority benchmarking, not as a restriction on full-market data coverage.

Financial data should target the full eligible A-share Universe wherever feasible. FMDL-3 must not collect fundamentals only for the current 100-name Longlist, because that would create research-path dependency and prevent future screening recomputation.

## 15. Handoff to FMDL-4

FMDL-4 receives a research packet, not an opaque score. The packet may include:

- market-behaviour sleeve and rank;
- point-in-time financial quality factors;
- valuation and shareholder-return states;
- sector profile;
- source coverage and confidence;
- comparability and restatement warnings;
- structural rejection tests;
- lineage pointers.

FMDL-4 owns issuer-level interpretation, rejection or advancement, candidate-pool graduation and Investment OS decision gates.

## 16. Security, legal and cost posture

- free and free-tier sources only unless the user explicitly changes policy;
- no credential material committed to the repository;
- GitHub Actions secrets are used only for authorized source routes;
- source terms and redistribution restrictions are respected;
- raw documents are not redistributed when licensing or practical limits prevent it;
- the source index and hashes preserve evidence lineage even when a raw document cannot be stored.

## 17. Final architecture acceptance criteria

This architecture phase is accepted when:

1. the machine-readable contract and schema exist;
2. point-in-time, restatement, source, missingness and sector-routing policies are explicit;
3. FMDL-3A through FMDL-3E have frozen entry and exit gates;
4. canonical datasets and Current paths are defined;
5. zero-tolerance failures and authority boundaries are machine-validated;
6. repository validation passes on GitHub-hosted runners;
7. README identifies FMDL-3A as the next execution phase.

The next authorized phase is:

`FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map`
