# FMDL-6D｜Minimal End-to-End Data Chain

## 1. Purpose

FMDL-6D proves that the accepted US-market architecture can carry a bounded sample through one auditable data chain:

`FMDL-6C identity → daily market and corporate-action observations → official FX → selected SEC filing facts → availability fields → source lineage → immutable release`.

It is an interface and data-contract acceptance phase. It is not a US investable universe, research Longlist, candidate pool, factor engine, simulation admission, real-account admission or order path.

## 2. Frozen sample

### Market and corporate-action sample — 8 securities

| Security | Technical role |
|---|---|
| AAPL | Domestic common-stock base, split and dividend events |
| BRK-B | Punctuated ticker and multiple share classes |
| BABA | ADR and foreign-private-issuer structure |
| ASML | Foreign ordinary share and IFRS reporting |
| EQIX | Equity REIT |
| JPM | Bank-specialized reporting |
| GEV | Spin-off child and short public history |
| UEC | NYSE American and smaller-cap venue |

### Financial fact sample — 4 issuers

AAPL, BABA, EQIX and JPM are retained as a deliberately heterogeneous SEC filing sample covering domestic US-GAAP, foreign-private-issuer, REIT and bank reporting profiles.

The sample is small by design. FMDL-6-0 requires only a `SMALL_SAMPLE_PRICE_AND_CORPORATE_ACTION_STORE` and a `SEC_SUBMISSION_AND_FINANCIAL_FACT_SAMPLE`; it does not authorize an all-24 financial normalization run or a full-market build.

## 3. Source routes

- Daily OHLCV and dividend/split events: Yahoo query1 with query2 fallback, accepted only as free pilot data.
- FX: official ECB daily reference series, deriving USD/CNY and USD/HKD from currency-per-EUR observations.
- Financial facts: selected presentation facts from official SEC filing HTML captured through the FMDL-6B-approved `CHATGPT_WEB` route.
- Identity: accepted FMDL-6C Current benchmark pool.

Every route records source URL, retrieval timestamp, payload or selected-snapshot SHA-256, parser version, source authority and no-silent-replacement policy.

## 4. Point-in-time posture

FMDL-6D does not claim that a free market-data response reconstructs what was historically knowable on each observation date. Market, corporate-action and FX records therefore receive a conservative `available_from_utc` equal to the capture timestamp.

The SEC selected-fact sample does not contain complete filing-acceptance timestamps for every fact. Its availability is conservatively bounded to the official-filing retrieval timestamp. No look-ahead-safe historical research claim is authorized by this release.

## 5. Acceptance gates

- exactly 8 market securities;
- at least 250 daily observations per security and 2,000 in total;
- at least 100 observations for each FX pair;
- exactly 4 financial issuers, at least 2 facts per issuer and at least 10 facts in total;
- identity, market, event, FX and financial links are complete;
- availability and source-lineage fields are complete;
- same-input replay reproduces the canonical and per-file hashes;
- candidate, simulation, real-account and order mutations remain zero;
- `trade_authority = NONE`.

## 6. Published products

- `FMDL6D_MARKET_STORE.json`
- `FMDL6D_FX_STORE.json`
- `FMDL6D_FINANCIAL_FACT_SAMPLE.json`
- `FMDL6D_CHAIN_RECORDS.json`
- `FMDL6D_AVAILABILITY.json`
- `FMDL6D_SOURCE_REGISTRY.json`
- `FMDL6D_DECISION.json`
- `FMDL6D_VALIDATION.json`
- `FMDL6D_RELEASE.json`
- `FMDL6D_MANIFEST.json`

Publication follows Current, immutable release, Archive and `FMDL6D_LAST_SUCCESS.json` only after PR acceptance and a successful main run.

## 7. Controlled limitations

- free market data is not Decision-grade;
- Yahoo point-in-time and revision guarantees are not documented;
- the SEC snapshot retains selected fact rows and source metadata, not the full filing payload;
- selected facts are not production CompanyFacts/XBRL normalization;
- full-universe, full-history, factors, screening and Investment OS integration remain closed.

## 8. Exit

Accepted status: `FMDL6D_MINIMAL_END_TO_END_DATA_CHAIN_ACCEPTED`.

Next gate: `FMDL-6E_QUALITY_FAILURE_AND_COST_BENCHMARK`.
