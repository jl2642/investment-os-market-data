# FMDL-2A — Historical Source Decision

## Decision state

`APPROVED_FOR_FMDL_2B_INITIAL_BACKFILL`

This decision selects a technical route for free A-share historical daily data. It does not rank securities, prove factor alpha, change any portfolio or create trade authority.

## Benchmark identity

- Benchmark run: `FMDL2A_R2_20260717T101323+0800`
- GitHub Actions run: `29549125979`
- Artifact digest: `sha256:7754a1fecbbc969cc55e48b5eed6a04a744a5ea97058ab4055276e64ffb797dc`
- AKShare version: `1.18.64`
- Accepted FMDL-1 Current date: `2026-07-16`
- Scale sample: `120` symbols
- Sample SHA-256: `e34b6b5a182ec8e0142aadc84b43efc06158538710b1eb6b204df08fce64c415`

The deterministic sample covered Shanghai Main, Shenzhen Main, STAR, ChiNext and Beijing Stock Exchange, with ST and suspended securities deliberately prioritized before stable-hash filling.

## Primary route

### Sina / AKShare `stock_zh_a_daily`

Selected as the FMDL-2B primary provider.

Scale evidence:

- 120 symbols attempted;
- 119 successful;
- success ratio `99.17%`;
- latest-session ratio `99.16%`;
- OHLC schema ratio `100%`;
- historical-volume schema ratio `100%`;
- historical-amount schema ratio `100%`;
- median latency `1.4144s`;
- p95 latency `1.9839s`;
- board success: SH Main `100%`, SZ Main `100%`, STAR `95%`, ChiNext `100%`, BSE `100%`.

The route is accepted for initial backfill only with two-attempt per-symbol retry, controlled backoff and failed-symbol quarantine.

## Restricted fallback

### Tencent / AKShare `stock_zh_a_hist_tx`

Accepted only as a restricted price-and-amount fallback for Shanghai Main and Shenzhen Main.

Evidence:

- 40-symbol fallback subsample;
- success ratio `100%`;
- latest-session ratio `100%`;
- QFQ OHLC and amount available;
- normalized historical volume unavailable.

Restrictions:

- it cannot supply volume factors;
- it cannot be silently spliced into a Sina series;
- STAR, ChiNext and BSE are not routed to Tencent without separate validation;
- every fallback row must retain provider and capability lineage.

## Degraded route

### Eastmoney / AKShare `stock_zh_a_hist`

Not selected for FMDL-2B on GitHub-hosted runners.

Smoke evidence:

- 15 symbols attempted;
- 4 successful;
- success ratio `26.67%`;
- repeated remote connection closures across major boards.

Eastmoney may be re-benchmarked later but is not part of the production route now.

## Mandatory FMDL-2B controls

1. Partition the 5,529-symbol initial backfill into resumable shards.
2. Retry each symbol twice before quarantine; never restart the whole market for one failed symbol.
3. Store QFQ price and unadjusted source-reported liquidity with separate lineage.
4. Preserve null values; never fill missing observations with zero.
5. Record provider, function, adjustment, board route, retrieval time and hashes per symbol.
6. Handle newly listed securities as partial history rather than failure.
7. Enforce duplicate-date, impossible-OHLC, future-date, freshness and file-hash gates.
8. Append incrementally after initial backfill rather than redownloading full history every day.
9. Run corporate-action and adjustment replay tests before factor-table promotion.
10. Keep all outputs as research-priority evidence with `trade_authority = NONE`.

## Residual risks

- Free providers can throttle or block GitHub runner IPs.
- A 120-symbol benchmark is not a 5,529-symbol production backfill.
- The single failed Sina sample and STAR 95% result require quarantine/retry controls.
- Tencent was not tested full-scale and lacks historical volume.
- Corporate-action accuracy is not yet fully accepted.
- Source readiness does not demonstrate that any factor generates alpha.
