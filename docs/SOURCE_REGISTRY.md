# Source Registry v1.1.0

## 1. Policy

The project uses only free or free-tier data sources. A source is not trusted merely because a library returns a table. Each adapter records the actual upstream route, retrieval time, observed fields, retries, fallback use and raw evidence hash where retained.

The registry distinguishes:

- **adapter**: code invoked by this repository;
- **upstream provider**: the public site or exchange endpoint ultimately supplying the data;
- **dataset capability**: fields and markets observed from the route;
- **operating status**: whether the route is active, fallback, degraded, disabled or experimental.

## 2. Active adapter

### AKShare

- Registry ID: `akshare`
- Cost: free/open-source
- Role: Python adapter for the FMDL-1 MVP
- Operating status: `ACTIVE_PRIMARY`
- Verified version: `1.18.64`
- Authentication: none for the selected interfaces
- Real-run sample date: `2026-07-16`
- Real-run market-wide rows: `5,529`

AKShare remains an adapter family rather than a single source of truth. Runtime manifests must record the exact function and upstream provider class.

## 3. Verified functions

| Dataset role | AKShare function | Provider class | Status | Observed result |
|---|---|---|---|---|
| Market-wide primary | `stock_zh_a_spot_em` | `eastmoney_public` | DEGRADED | GitHub Azure runner connection was closed by upstream |
| Market-wide fallback | `stock_zh_a_spot` | `sina_public` | ACTIVE_FALLBACK | 5,529 rows successfully retrieved |
| Shanghai main-board master | `stock_info_sh_name_code("主板A股")` | `sse_public` | ACTIVE_PRIMARY | Successful |
| STAR Market master | `stock_info_sh_name_code("科创板")` | `sse_public` | ACTIVE_PRIMARY | Successful |
| Shenzhen A-share master | `stock_info_sz_name_code("A股列表")` | `szse_public` | ACTIVE_PRIMARY | Successful after one transient retry |
| Beijing Stock Exchange master | `stock_info_bj_name_code()` | `bse_public` | ACTIVE_PRIMARY | Successful |
| Trading calendar | `tool_trade_date_hist_sina()` | `sina_public` | ACTIVE_FALLBACK | Successful |

## 4. Observed field capability

### `stock_zh_a_spot_em` / Eastmoney primary

Expected bulk fields include identity, OHLC, prior close, return, volume, turnover, turnover rate, market capitalization, dynamic PE and PB. This route remains registered because it provides the richest free market-wide schema, but it is currently degraded on GitHub-hosted Azure runners.

### `stock_zh_a_spot` / Sina fallback

Observed bulk fields include:

- exchange-prefixed code and name;
- latest price, price change and percentage change;
- previous close, open, high and low;
- volume in shares and turnover amount;
- source timestamp.

Observed limitations:

- no market-cap fields in this bulk interface;
- no PE/PB fields in this bulk interface;
- source can encode suspended securities with zero prices, which the canonical normalizer classifies as suspended rather than traded;
- repeated excessive calls may cause temporary provider throttling, so the workflow uses bounded calls and one daily operating cadence.

### Exchange masters

The exchange master routes provide canonical identity and listing dates. Shenzhen and Beijing also provide industry fields; Shanghai master routes used here do not supply industry, which explains the controlled universe industry-coverage warning.

## 5. Source priority by dataset

### `a_share_universe`

1. Market-wide identity from the successful registered bulk route.
2. SSE, SZSE and BSE masters for exchange identity and listing-date enrichment.
3. Previous last-known-good universe only as a stale comparison and rollback reference.

### `daily_market_snapshot`

1. `stock_zh_a_spot_em` / `eastmoney_public` when the route passes the same schema and hard quality gates.
2. `stock_zh_a_spot` / `sina_public` as the explicit active fallback.
3. Previous last-known-good snapshot remains current when all new candidates fail, preserving its original `as_of_date`.

### `trading_calendar`

1. `tool_trade_date_hist_sina()` through AKShare.
2. Weekday fallback may support conservative candidate construction but cannot independently promote a dataset to a stable operating release without explicit warning.

## 6. Source status values

- `APPROVED_FOR_MVP_TESTING`
- `ACTIVE_PRIMARY`
- `ACTIVE_FALLBACK`
- `DEGRADED`
- `DISABLED`
- `EXPERIMENTAL`
- `RETIRED`

## 7. Failure and fallback rules

- Retry only transient network or server failures with bounded exponential backoff.
- Do not retry schema or semantic failures as network failures.
- A fallback dataset must pass the same canonical schema and quality gates as the primary.
- Provider fallback must be explicit in the manifest and run report.
- Provider IDs written to manifests must exactly match this registry.
- Mixing fields from multiple sources requires field-level provenance.
- Conflicting values are never averaged automatically.
- If no candidate passes, quarantine the run and retain the last-known-good output.

## 8. Source evidence required in each manifest

- adapter name and version;
- exact adapter function;
- registered upstream provider ID;
- retrieval timestamp;
- source-reported trading/as-of date where available;
- raw evidence hash where retained;
- warnings, retries, fallback use and volume-unit semantics.

## 9. Prohibited practices

- Paid API calls or unapproved trial-credit consumption.
- Browser-session cookies or personal credentials committed to the repository.
- Hidden scraping that violates an explicit access restriction.
- Fabricating unavailable values.
- Treating a stale prior snapshot as current.
- Publishing a source result without schema and quality validation.

## 10. Current conclusion

FMDL-1B/C has verified that free GitHub-hosted full-market acquisition is operational through the registered Sina fallback. Eastmoney remains the richer preferred route but is degraded in the current runner environment. FMDL-1D/E will implement persistent last-known-good promotion and scheduled operating controls around these verified routes.
