# FMDL-2A Acceptance — Factor Contract & Historical Source Benchmark

## Acceptance state

`ACCEPTED_WITH_CONTROLLED_SOURCE_RISK`

FMDL-2A freezes the permitted market-behaviour factor contract and selects a technically viable free historical-data route for FMDL-2B. It does not build the full historical store, calculate production factor tables, rank stocks, demonstrate alpha or create trading authority.

## Release evidence

- Factor contract version: `1.0.0`
- Benchmark version: `2.0.0`
- Benchmark run: `FMDL2A_R2_20260717T101323+0800`
- GitHub Actions run: `29549125979` — `SUCCESS`
- Benchmark artifact digest: `sha256:7754a1fecbbc969cc55e48b5eed6a04a744a5ea97058ab4055276e64ffb797dc`
- Accepted FMDL-1 Current run: `FMDL1BC_20260716T165927+0800`
- Current as-of date: `2026-07-16`
- AKShare version: `1.18.64`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`
- Trade authority: `NONE`

## Accepted factor scope

The registry contains market-behaviour factors only:

- 20/60/120/250-session returns and medium-term momentum;
- distance to 52-week high and trend consistency;
- volatility, downside volatility, drawdown, worst-day and extreme-move diagnostics;
- turnover amount, turnover stability and volume-ratio diagnostics;
- active-trading, suspension and zero-turnover controls;
- same-date broad-market and board-neutral cross-sectional outputs.

All missing values remain missing. Future data is forbidden. Financial, valuation, market-cap, dividend and analyst-estimate factors remain prohibited until FMDL-3.

## Accepted source route

### Primary

`Sina / AKShare stock_zh_a_daily`, QFQ.

120-symbol cross-board scale result:

- 119/120 successful (`99.17%`);
- latest-session ratio `99.16%`;
- OHLC, volume and amount schemas `100%` on successful series;
- SH Main `100%`, SZ Main `100%`, STAR `95%`, ChiNext `100%`, BSE `100%`;
- median latency `1.4144s`, p95 `1.9839s`.

### Restricted fallback

`Tencent / AKShare stock_zh_a_hist_tx` is accepted for QFQ price and amount only on SH/SZ Main after Sina failure. It lacks validated historical volume and cannot be silently mixed with a Sina series.

### Degraded

`Eastmoney / AKShare stock_zh_a_hist` is not selected on GitHub-hosted runners because smoke success was only `26.67%` with repeated connection closures.

## Acceptance gates passed

- FMDL-1 consumer interface validation passed;
- factor registry regression tests passed;
- deterministic board-stratified sample generation passed;
- real GitHub-hosted free-source benchmark completed;
- full-scale primary and restricted fallback capabilities were recorded;
- provider routing, retry, cache and quarantine requirements were frozen;
- factor and source outputs retain research-only/no-trade authority boundaries.

## Controlled risks and non-claims

1. A 120-symbol benchmark is not the 5,529-symbol initial backfill.
2. Free public providers may throttle or block GitHub runner IPs.
3. One Sina sample failed and STAR success was 95%; FMDL-2B must retry and quarantine per symbol.
4. Tencent was tested only on a fallback subsample and cannot supply volume factors.
5. Corporate-action and QFQ continuity still require replay tests in FMDL-2B.
6. Technical data availability does not demonstrate factor alpha or investment value.
7. No output from FMDL-2A may change a candidate pool, simulation account or real account.

## Authorized next phase

`FMDL-2B — Historical Store & Basic Factor Engine`

FMDL-2B must follow `docs/FMDL-2B_ENGINEERING_REQUIREMENTS.md` and may be accepted only after full-universe multi-shard backfill, resumability, controlled quarantine, factor calculation, anti-leakage tests and incremental-update verification.
