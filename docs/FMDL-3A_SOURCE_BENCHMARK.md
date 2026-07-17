# FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map

## 1. Final state

`FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN`

FMDL-3A executed real free/free-tier source routes on GitHub-hosted infrastructure. The accepted candidate is:

- run: `FMDL3A_20260718T004613+0800`;
- generated at: `2026-07-18T00:51:58+08:00`;
- accepted workflow: `29597406995`;
- candidate artifact: `8413745443`;
- artifact digest: `sha256:a4e44f8417d773c6495360703bcdf0b43fd2441353374d432c7b9cea0be16a99`;
- independent validation: `36 / 36 PASS`;
- hard failures: `0`;
- authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`;
- trade authority: `NONE`;
- next phase: `FMDL-3B`.

This acceptance freezes source routes and measured gates. It does not claim that the full-market financial statement store, normalized statements, financial factors or valuation Current already exist.

## 2. Deterministic stress sample

The benchmark used 13 issuers across:

- Shanghai Main Board;
- Shenzhen Main Board;
- ChiNext;
- STAR Market;
- Beijing Stock Exchange;
- general non-financial companies;
- banks;
- insurance;
- securities firms;
- pre-profit or negative-earnings issuers.

The sample is a source capability and failure-mode test, not a statistical backtest or full-market coverage claim.

## 3. Measured results

| Gate | Result |
|---|---:|
| Official disclosure call success | `100%` |
| Eastmoney fallback notice success | `100%` |
| SH/SZ primary three-statement bundle | `100%` |
| SH/SZ Sina fallback three-statement bundle | `100%` |
| Supported-universe statement coverage | `100%` |
| Official filing-to-report-period PIT match | `100%` |
| Supported-universe current capitalization coverage | `100%` |
| BSE official document route | `100%` |
| Future financial availability | `0` |
| Future-effective share-count use | `0` |
| Supported / quarantined / blocked symbols | `11 / 2 / 0` |
| Full-sample quarantine ratio | `15.3846%` |

Supporting source success:

- Eastmoney financial indicators: `90%` of the extended stress sample;
- Eastmoney historical valuation: `90%`;
- Eastmoney share-capital history: `90%`;
- Eastmoney dividends: `80%`;
- Eastmoney buybacks: `100%`.

The lower extended-source ratios are caused by the BSE route gap and remain visible. They are not filled or reclassified as success.

## 4. Frozen source decisions

### 4.1 Announcement, revision and PIT identity

Primary:

- `CNINFO_OFFICIAL_DISCLOSURE`;
- role: official announcement identity, filing link, report-period match, correction/revision sequence and BSE source-document route;
- measured call success: `100%`;
- official PIT match: `100%`.

Fallback:

- `EASTMONEY_NOTICE_FALLBACK`;
- role: degraded SH/SZ metadata continuity only;
- it may not silently upgrade to official evidence.

### 4.2 Structured financial statements

SH/SZ primary:

- `EASTMONEY_STATEMENTS`;
- balance sheet, income statement and cash-flow bundle;
- bundle success: `11 / 11` supported SH/SZ stress issuers.

SH/SZ fallback:

- `SINA_STATEMENTS`;
- bundle success: `11 / 11` supported SH/SZ stress issuers.

BSE:

- tested structured Eastmoney and Sina routes did not produce a usable BSE three-statement bundle;
- `835185.BJ` and `430047.BJ` are therefore `QUARANTINED`, not supported and not deleted;
- both retain valid CNINFO official periodic-report document routes;
- FMDL-3B must implement official-document extraction and normalization before any BSE financial-factor eligibility.

### 4.3 Current capitalization and valuation semantics

Accepted current-price source:

- `FMDL1_ACCEPTED_CURRENT_PRICE`;
- source: accepted `outputs/current/DAILY_MARKET_SNAPSHOT.csv`;
- role: latest completed-session close;
- supported-universe coverage: `100%`.

Accepted share-count source:

- `EASTMONEY_EFFECTIVE_SHARE_CAPITAL`;
- adapter: `stock_zh_a_gbjg_em`;
- role: latest positive total shares and listed floating A shares with `share_effective_date <= price_as_of_date`;
- supported-universe coverage: `100%`;
- future-effective share rows accepted: `0`.

Accepted derived capitalization:

- `COMPOSITE_CURRENT_CAPITALIZATION`;
- `total_market_cap = accepted_close × latest_effective_total_shares`;
- `float_market_cap = accepted_close × latest_effective_float_A_shares`;
- formula replay: `100%`;
- supported-universe coverage: `100%`.

Decision-grade PE and PB are **not** accepted from a provider in FMDL-3A. FMDL-3D must recompute them using point-in-time earnings and equity denominators. Negative, zero or otherwise invalid denominators must publish a `NOT_MEANINGFUL` status rather than a synthetic ratio.

### 4.4 Rejected current valuation routes

The following were tested and rejected for GitHub-hosted production:

- `EASTMONEY_CURRENT_VALUATION`: aggregate and split-market endpoints repeatedly disconnected;
- `XUEQIU_CURRENT_VALUATION`: all 13 stress calls returned an unusable response structure or remote disconnect;
- `EASTMONEY_INDIVIDUAL_INFO`: all 13 stress calls returned non-JSON empty responses.

These failures remain evidence in the source index. They are not automatic fallbacks.

### 4.5 Supporting sources

- `EASTMONEY_FINANCIAL_INDICATORS`: cross-check and factor-input support only;
- `EASTMONEY_HISTORICAL_VALUATION`: conditional provider-ratio cross-check for SH/SZ;
- `EASTMONEY_SHARE_CAPITAL`: historical share-count cross-check for SH/SZ;
- `EASTMONEY_DIVIDENDS`: primary SH/SZ dividend-event source, with BSE gap visible;
- `EASTMONEY_BUYBACKS`: primary buyback-event source.

Provider-calculated financial indicators and valuation ratios never replace source-reported facts or FMDL-computed ratios.

## 5. Frozen numeric gates

FMDL-3B inherits these minimum gates:

- official disclosure success: `>=95%`;
- SH/SZ primary statement bundle: `>=95%`;
- SH/SZ fallback statement bundle: `>=80%`;
- supported-universe statement coverage: `>=95%`;
- official PIT match: `>=90%`;
- supported-universe current capitalization coverage: `>=95%`;
- full-sample controlled statement quarantine: `<=16%` at this accepted stress-sample baseline;
- zero uncontrolled blocked sample symbols;
- zero future financial availability;
- zero future-effective share-count use;
- zero missing source identity;
- zero trade authority.

The `16%` quarantine cap is not permission to quarantine arbitrary issuers. It records the measured `2 / 13` BSE limitation and requires an explicit official-document recovery route.

## 6. Accepted datasets

- `FMDL3A_BENCHMARK_ROWS.csv`;
- `FMDL3A_SOURCE_SUMMARY.csv`;
- `FMDL3A_COVERAGE_MAP.csv`;
- `FMDL3A_POINT_IN_TIME_EVIDENCE.csv`;
- `FMDL3A_SUPPORT_QUARANTINE_MAP.csv`;
- `FMDL3A_CAPITALIZATION_EVIDENCE.csv`;
- `FMDL3_SOURCE_INDEX.csv`;
- `FMDL3A_SOURCE_DECISION.json`;
- `FMDL3A_VALIDATION.json`;
- `FMDL3A_MANIFEST.json`.

After main-branch publication, canonical paths are:

- `outputs/financials/benchmark/current/`;
- `outputs/financials/source_index/current/`;
- `outputs/status/FMDL3A_LAST_SUCCESS.json`.

## 7. Controlled limitations

1. Tested free structured sources do not support BSE three-statement normalization at the accepted standard.
2. BSE remains controlled quarantine until FMDL-3B official CNINFO document extraction is accepted.
3. Public real-time valuation endpoints were unstable or unusable on GitHub Runner.
4. Current capitalization is therefore derived from accepted price and PIT-effective shares.
5. Provider PE/PB is not decision-grade; FMDL-3D recomputes ratios.
6. Financial availability is daily-resolution only and creates no intraday factor authority.

## 8. FMDL-3B entry condition

FMDL-3B is authorized to build the point-in-time financial statement store and normalization layer using the frozen routes above. It must not bypass the BSE recovery requirement, source lineage, revision retention, missingness rules or Current/LKG publication contract.
