# FMDL-6B — Source Interface & Access Benchmark

## 1. Objective

FMDL-6B performs a live access benchmark for the source interfaces required by the bounded US equity pilot. It does not build a US Security Master, price warehouse, financial-fact store, factor engine, research Longlist, candidate pool, simulation account or real-account route.

The phase answers five operational questions:

1. Can GitHub Actions reach the required official SEC interfaces with an identified User-Agent?
2. Can the repository reach a current official listed-security reference?
3. Is at least one free daily OHLCV route usable for a small technical sample?
4. Is at least one free corporate-action event route usable for a small technical sample?
5. Is at least one USD/CNY and USD/HKD reference-rate route usable?

## 2. Entry gate

The phase is bound to:

- FMDL-6A Release: `FMDL6A_20260722_99a4726452b1`
- FMDL-6A status: `FMDL6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY_ACCEPTED`
- next gate from FMDL-6A: `FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK`

## 3. Interface families

### SEC identity and submissions

Live probes:

- SEC company ticker / exchange reference;
- SEC submissions JSON for a fixed reference issuer.

The route must expose CIK, ticker, exchange, accession, form, filing date and acceptance-time lineage. Ticker and exchange remain listing attributes, not immutable security identity.

### SEC Company Facts and XBRL

Live probe:

- SEC Company Facts JSON for a fixed reference issuer.

The route must expose taxonomy namespaces, concepts, units, forms, filing dates and accession lineage. Passing this interface benchmark does not mean the financial normalization layer is complete or Decision-grade.

### Official listed-security reference

Live probes:

- Nasdaq Trader `nasdaqlisted.txt`;
- Nasdaq Trader `otherlisted.txt`;
- SEC ticker / exchange reference as controlled official support.

The directories are current-state references. They do not establish historical membership, delisted history or permanent issuer identity by themselves.

### Daily market, corporate action and FX

Live probes:

- Stooq daily OHLCV;
- Yahoo chart endpoints for daily observations and dividend / split events;
- ECB reference-rate API for USD, CNY and HKD against EUR;
- Frankfurter as a free FX fallback.

Free market and corporate-action routes remain pilot-only. FMDL-6B does not authorize Decision-grade use, factor calculation, screening or portfolio integration.

## 4. Benchmark evidence

Every route records:

- provider and endpoint;
- official or fallback status;
- HTTP and access result;
- latency;
- response size and SHA-256;
- field coverage and sample count;
- available history window;
- rate-limit headers when exposed;
- GitHub Actions compatibility;
- point-in-time and revision posture;
- failure category and error message;
- route decision.

The raw observation snapshot is immutable within a Release. Normalization and candidate generation are replayed from that captured snapshot.

## 5. Acceptance policy

Hard requirements:

- all three required SEC official routes succeed;
- a current security-directory route succeeds;
- at least one daily OHLCV route succeeds;
- at least one dividend or split event route succeeds;
- at least one USD/CNY and USD/HKD FX route succeeds;
- the routes are usable in GitHub Actions;
- no candidate, simulation, real-account or order mutation occurs.

Controlled limitations are acceptable when explicitly recorded, including:

- Nasdaq current directories degrade to SEC current support;
- ECB FX degrades to a free fallback;
- free market or corporate-action data remains pilot-only;
- current directories do not establish historical membership;
- SEC Company Facts normalization remains deferred.

## 6. Failure taxonomy

The benchmark distinguishes:

- DNS / connectivity failure;
- TLS / certificate failure;
- HTTP 4xx block or authentication failure;
- HTTP 429 rate limit;
- HTTP 5xx upstream failure;
- timeout;
- empty response;
- schema or parser drift;
- insufficient field coverage;
- insufficient history;
- unavailable corporate-action events;
- unavailable FX pairs;
- unknown failure.

Failed or degraded routes cannot replace Last Known Good.

## 7. Publication model

A successful main run publishes:

- `outputs/fmdl6b/current`
- `datasets/fmdl6b/releases/<release_id>`
- `outputs/fmdl6b/archive/<release_id>`
- `outputs/status/FMDL6B_LAST_SUCCESS.json`

The package includes the raw observations, normalized interface benchmark, source registry, failure taxonomy, decision, validation, Release and Manifest.

## 8. Permanent boundaries

- the benchmark does not create the 24-security pool;
- source accessibility is not source completeness;
- source accessibility is not Decision-grade data approval;
- no full universe or history is built;
- no research or investment conclusion is produced;
- no candidate, simulation or real-account state is changed;
- no order is produced;
- `trade_authority = NONE`.

## 9. Exit

Expected exit status:

`FMDL6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK_ACCEPTED`

Next gate:

`FMDL-6C_24_SECURITY_BENCHMARK_POOL`
