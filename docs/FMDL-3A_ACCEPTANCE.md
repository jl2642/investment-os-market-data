# FMDL-3A — Final Acceptance

## Acceptance state

`FMDL3A_ACCEPTED_SOURCE_ROUTE_AND_COVERAGE_GATES_FROZEN`

FMDL-3A has completed real source benchmarking, point-in-time contract validation, coverage mapping, source-route selection, rejected-route registration and independent acceptance on GitHub-hosted infrastructure.

This acceptance authorizes FMDL-3B. It does not claim that a full-market normalized statement store, financial-factor Current, valuation Current, investment conclusion or trade permission already exists.

## Accepted candidate evidence

- workflow run: `29597406995` — `SUCCESS`;
- candidate run: `FMDL3A_20260718T004613+0800`;
- generated at: `2026-07-18T00:51:58+08:00`;
- candidate artifact: `8413745443`;
- artifact digest: `sha256:a4e44f8417d773c6495360703bcdf0b43fd2441353374d432c7b9cea0be16a99`;
- independent validation: `36 / 36 PASS`;
- hard failures: `0`;
- authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`;
- trade authority: `NONE`;
- next phase: `FMDL-3B`.

## Accepted measured metrics

- deterministic stress sample: `13` issuers;
- supported / quarantined / blocked: `11 / 2 / 0`;
- official disclosure call success: `100%`;
- fallback notice call success: `100%`;
- SH/SZ primary three-statement bundle: `100%`;
- SH/SZ fallback three-statement bundle: `100%`;
- supported-universe statement coverage: `100%`;
- official filing-to-report-period match: `100%`;
- supported-universe current capitalization coverage: `100%`;
- BSE official document source availability: `100%`;
- full-sample controlled quarantine ratio: `15.3846%`;
- future financial information: `0`;
- future-effective share-count use: `0`.

Supporting-source success:

- financial indicators: `90%`;
- historical provider valuation: `90%`;
- historical share capital: `90%`;
- dividends: `80%`;
- buybacks: `100%`.

## Accepted source routes

### Financial availability and revisions

- primary: `CNINFO_OFFICIAL_DISCLOSURE`;
- fallback: `EASTMONEY_NOTICE_FALLBACK`, degraded metadata only;
- availability: next verified A-share trading session at `09:30+08:00`;
- restatements: new revision sequence, zero silent overwrite.

### Structured financial statements

- SH/SZ primary: `EASTMONEY_STATEMENTS`;
- SH/SZ fallback: `SINA_STATEMENTS`;
- BSE: controlled quarantine pending FMDL-3B CNINFO official-document extraction.

### Current price and capitalization

- price: accepted FMDL-1 latest completed-session close;
- shares: latest positive Eastmoney share-capital row effective no later than the price date;
- total market cap: close multiplied by effective total shares;
- floating market cap: close multiplied by effective listed floating A shares;
- provider PE/PB: support only;
- decision-grade PE/PB: recompute in FMDL-3D with PIT financial denominators.

### Shareholder-return evidence

- dividends: Eastmoney SH/SZ event route, with BSE gap visible;
- buybacks: Eastmoney event route.

## Rejected routes

The following routes were tested and are not production fallbacks:

1. Eastmoney aggregate and split-market current valuation — repeated GitHub Runner disconnects;
2. Xueqiu per-symbol valuation — unusable response structure or disconnect for `13 / 13` stress calls;
3. Eastmoney individual-info route — non-JSON empty response for `13 / 13` stress calls;
4. tested free BSE structured three-statement routes — no accepted bundle.

Rejected routes remain in the source index for auditability and future re-benchmarking.

## Controlled limitations

1. Two BSE stress issuers remain quarantined from structured financial facts.
2. FMDL-3B must implement official CNINFO document extraction before BSE factor eligibility.
3. Capitalization is derived rather than taken from a provider's live aggregate valuation endpoint.
4. Provider PE/PB is not decision-grade.
5. Financial PIT resolution is daily, not intraday.
6. The 13-issuer sample validates route capability and failure modes; it is not a full-market coverage claim.

## Canonical candidate files

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

After main publication:

- `outputs/financials/benchmark/current/`;
- `outputs/financials/source_index/current/`;
- `outputs/status/FMDL3A_LAST_SUCCESS.json`.

## FMDL-3B authorization

FMDL-3B may now implement the point-in-time statement store and normalization layer. It must preserve:

- official availability and revision identity;
- raw facts and source lineage;
- SH/SZ primary/fallback routing;
- BSE quarantine and official-document recovery;
- no missing-value imputation;
- no future-effective share use;
- fail-closed Current and Last-known-good;
- zero trade authority.
