# FMDL-6C — 24-Security Benchmark Pool

## 1. Objective

FMDL-6C creates a fixed 24-security **technical benchmark pool** for the bounded US-equity pilot. It is designed to test identity, listing, source, accounting, corporate-action and replay edge cases in FMDL-6D and FMDL-6E.

The pool is not a research Longlist, candidate pool, simulation portfolio, real-account portfolio or investment recommendation.

## 2. Entry and source bindings

The phase is bound to:

- FMDL-6A Release `FMDL6A_20260722_99a4726452b1`;
- FMDL-6B Release `FMDL6B_20260722_de3d0a9b7703`;
- the accepted SEC external-execution decision from FMDL-6B;
- current Nasdaq Trader listed-security directories;
- a hashed selected-row SEC official-reference snapshot retrieved through the approved ChatGPT-web route.

The SEC selected-row snapshot records the official source URL, retrieval time, canonical selected-row SHA-256, source authority and no-silent-replacement rule. It does not claim to preserve the SHA-256 of the complete upstream SEC file.

## 3. Pool composition

| # | Ticker | MIC | Type | Main technical cases |
|---:|---|---|---|---|
| 1 | AAPL | XNAS | Common | domestic base, split and dividend |
| 2 | NVDA | XNAS | Common | high growth, recent large split |
| 3 | META | XNAS | Common | ticker-change lineage |
| 4 | BRK-A | XNYS | Common | class A, punctuated ticker |
| 5 | BRK-B | XNYS | Common | class B, punctuated ticker |
| 6 | GOOGL | XNAS | Common | voting class |
| 7 | GOOG | XNAS | Common | non-voting class |
| 8 | FOXA | XNAS | Common | class A voting-right difference |
| 9 | FOX | XNAS | Common | class B voting-right difference |
| 10 | PBR | XNYS | ADR | IFRS, commodity cycle, state influence |
| 11 | BABA | XNYS | ADR | FPI US-GAAP, VIE structure |
| 12 | ASML | XNAS | Foreign ordinary | IFRS, foreign ordinary share |
| 13 | SHEL | XNYS | ADR | IFRS energy major |
| 14 | SHOP | XNAS | Foreign ordinary | Canadian 40-F and IFRS |
| 15 | SPOT | XNYS | Foreign ordinary | IFRS and direct-listing history |
| 16 | ARM | XNAS | ADR | recent IPO and short US history |
| 17 | NVO | XNYS | ADR | IFRS healthcare and distributions |
| 18 | TSM | XNYS | ADR | IFRS foundry and geopolitical exposure |
| 19 | EQIX | XNAS | Equity REIT | REIT / FFO-AFFO normalization |
| 20 | PLD | XNYS | Equity REIT | industrial REIT |
| 21 | JPM | XNYS | Common | bank-specific statements and capital |
| 22 | GE | XNYS | Common | spin-off parent lineage |
| 23 | GEV | XNYS | Common | spin-off child and short history |
| 24 | UEC | XASE | Common | NYSE American and smaller-cap venue |

The pool contains 24 securities and 21 issuers. It covers XNAS, XNYS and XASE; common stock, ADR, foreign ordinary shares and equity-REIT common stock; domestic 10-K, foreign 20-F/40-F and REIT/bank reporting profiles.

## 4. Identity model

Each row preserves four distinct concepts:

- immutable issuer key: `SEC:CIK:<CIK10>`;
- share-class key;
- security key;
- current listing observation key.

A current directory snapshot does **not** prove the historical effective-from date of a listing. Therefore FMDL-6C publishes:

- `USLISTOBS:<MIC>:<TICKER>:20260722` as a current observation locator;
- `canonical_listing_key = null`;
- `listing_history_status = CURRENT_SNAPSHOT_ONLY`.

Canonical effective-dated listing keys remain deferred until FMDL-6D or a later historical-source step verifies the actual effective date.

## 5. Live listing validation

GitHub Actions retrieves:

- `nasdaqlisted.txt`;
- `otherlisted.txt`.

Every selected row must:

- exist in the expected directory;
- match XNAS, XNYS or XASE;
- have `ETF = N`;
- have `Test Issue = N`.

The full directory payloads are not committed. The captured evidence retains source URL, retrieval time, payload SHA-256, byte count, row count, GitHub Actions compatibility and the 24 selected directory rows.

## 6. Acceptance

Acceptance requires:

- exactly 24 unique securities;
- at least 20 unique issuers;
- all three venues;
- all four included instrument types;
- multi-class, punctuated ticker, ticker change, ADR, foreign ordinary, REIT, XASE, spin-off, IPO, bank and XBRL-complexity cases;
- all 24 current listings confirmed by official directories;
- deterministic replay from the captured directory evidence;
- zero candidate, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## 7. Permanent boundaries

FMDL-6C does not:

- build the US full universe;
- create historical price or financial warehouses;
- normalize SEC Company Facts;
- calculate factors or screens;
- graduate any security into research or investment state;
- resolve historical listing effective dates without evidence;
- authorize Decision-grade market data or trading.

## 8. Exit

Expected status:

`FMDL6C_24_SECURITY_BENCHMARK_POOL_ACCEPTED`

Next gate:

`FMDL-6D_MINIMAL_END_TO_END_DATA_CHAIN`
