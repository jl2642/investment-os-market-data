# FMDL-5C｜Price, Volume, Corporate Action & FX Store

## Objective

Build a point-in-time Hong Kong market-data layer for the accepted 644-security Southbound universe without using paid market-data subscriptions and without mutating any Investment OS decision state.

## Source hierarchy

### Price and volume

1. `YAHOO_CHART_FREE_UNOFFICIAL` — primary historical raw OHLCV, vendor adjusted close, cash-dividend and split events.
2. `EASTMONEY_PUSH2HIS_FREE_UNOFFICIAL` — per-security fallback when Yahoo is unavailable or returns insufficient observations.
3. HKEX identity and current trading/corporate-action pages — official corroboration only.

HKEX official bulk day-end and historical price files are paid data products. FMDL-5C therefore labels all free price rows as `UNOFFICIAL_FREE_VENDOR`; it never presents them as official HKEX market data.

### Corporate actions

- Yahoo chart events provide cash-dividend and split transport.
- HKEX Newly Listed Securities provides official current listing, consolidation and related-code events where available.
- Full issuer-disclosure extraction and confirmation remain a FMDL-5D responsibility.

Raw prices and vendor-adjusted prices are stored separately. An adjusted close never overwrites the raw close.

### FX

The official HKMA `er-eeri-daily` Open API supplies:

- HKD per USD;
- HKD per CNY;
- observation date;
- retrieval time and source-page hash.

## Outputs

- full daily OHLCV Parquet store;
- latest per-security snapshot;
- corporate-action event table;
- official daily FX table;
- failure and provider-routing table;
- source registry;
- quality report;
- acceptance decision and manifest.

## Acceptance gates

- exactly 644 source securities are bound to FMDL-5B-2;
- at least 95% have a recent latest price;
- at least 90% have usable historical observations;
- no duplicate security/date rows;
- no negative prices or volumes;
- at least 700 official FX observations;
- Current, immutable Release, Archive and Last-success are published only after main acceptance;
- candidate, simulation, real-account and order mutation counts remain zero;
- `trade_authority = NONE`.

## Limitations

Free endpoints can be rate-limited or change without notice. Provider failures must not be converted into empty prices, and a failed run must not replace Current or Last-known-good. Price evidence is suitable for screening, research and monitoring only after downstream freshness and quality checks; it is not order-routing data.

## Exit

Expected status:

`FMDL5C_PRICE_VOLUME_CORPORATE_ACTION_AND_FX_STORE_ACCEPTED`

Next gate:

`FMDL-5D_HKEX_DISCLOSURE_AND_FINANCIAL_NORMALIZATION`
