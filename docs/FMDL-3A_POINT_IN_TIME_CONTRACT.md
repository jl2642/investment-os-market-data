# FMDL-3A Point-in-Time Contract

## 1. Contract status

`ACCEPTED_FOR_FMDL3B_EXECUTION`

This contract inherits the FMDL-3 architecture policy and freezes daily-resolution financial availability, revision handling and share-capital effectiveness for FMDL-3B.

Accepted evidence:

- candidate run: `FMDL3A_20260718T004613+0800`;
- workflow: `29597406995` — success;
- official filing-to-period PIT match: `100%`;
- future financial availability: `0`;
- future-effective share-count use: `0`.

It does not authorize intraday financial-factor use or trade authority.

## 2. Required financial temporal fields

Every financial fact intended for point-in-time use must preserve:

- `report_period_start`;
- `report_period_end`;
- `fiscal_period_type`;
- `announcement_date`;
- `announcement_timestamp_raw`;
- `available_from`;
- `source_retrieved_at`;
- `revision_sequence`;
- `effective_from`;
- `superseded_at`.

Unknown timestamps remain null. They are never reconstructed from report-period labels.

## 3. Daily financial availability

### 3.1 Official filing metadata exists

For a CNINFO official filing announced on calendar date `D`:

1. retain the raw platform date or timestamp;
2. retain the official filing title and source link;
3. identify the report period from the full periodic-report identity;
4. at daily research resolution, set `available_from` to the next verified A-share trading session at `09:30:00+08:00`;
5. never use the record before `available_from`.

The rule is deliberately conservative and uniform across evening, date-only and ambiguous timestamp records.

### 3.2 Official metadata is unavailable

A third-party announcement record may be retained as:

`DEGRADED_FALLBACK`

It may support investigation and recovery but is not decision-grade until reconciled with an official filing identity.

### 3.3 Report-period prohibition

`report_period_end` is an accounting key, not an availability date.

The following are prohibited:

- assigning availability to the report-period end;
- assigning availability to an expected publication deadline;
- assigning availability from the first date seen at a provider;
- using a later revised value in an earlier as-of replay.

## 4. Trading calendar

The accepted route uses the explicit Sina A-share trading calendar through AKShare.

A weekend-only approximation is not decision-grade. If the trading-calendar route fails, the financial PIT candidate must fail and Last-known-good must remain unchanged.

## 5. Revision sequence and restatements

For each issuer, report period and filing family:

1. order identified full-report filings by official announcement time;
2. assign `revision_sequence = 1` to the first public version;
3. assign increasing sequence numbers to corrections, revised reports and updated full reports;
4. set the prior version's `superseded_at` to the later version's `available_from`;
5. retain every version, source link and original value;
6. prohibit silent overwrite.

Keywords such as `更正`, `修订`, `更新后` and `补充` are revision signals, not proof by themselves. FMDL-3B must reconcile issuer, report period, title, source document and changed facts.

## 6. Structured-provider timestamps

Provider fields such as `NOTICE_DATE`, `UPDATE_DATE` or `更新日期` are retained for:

- provider freshness monitoring;
- conflict detection;
- retrieval diagnostics;
- degraded recovery.

They do not outrank CNINFO official filing metadata and cannot replace `available_from` without a separately accepted contract revision.

## 7. Share-capital point-in-time rule

Current capitalization uses an accepted FMDL-1 close and an effective share-count record.

For price as-of date `P`:

1. retrieve share-capital history with original source identity;
2. parse `变更日期` as the share-count effective date;
3. retain only rows where `share_effective_date <= P`;
4. require positive `总股本` and positive `已上市流通A股`;
5. select the latest eligible row;
6. prohibit later share counts from entering the calculation.

Derived values:

- `total_market_cap_cny = accepted_close × effective_total_shares`;
- `float_market_cap_cny = accepted_close × effective_float_A_shares`.

Every derived row must preserve:

- price as-of date and source ID;
- accepted price row hash;
- share effective date and source ID;
- total and floating A-share counts;
- formula identity;
- derivation timestamp;
- QA state.

The accepted stress candidate produced `11 / 11` supported-universe capitalization rows and zero future-effective share use.

## 8. Valuation-ratio rule

Provider PE, PB and related ratios are support-only evidence.

Decision-grade ratios must be recomputed in FMDL-3D using:

- the accepted market numerator as of `T`;
- only financial denominator versions eligible at `T`;
- explicit denominator status and sector profile.

Negative, zero, stale, missing or economically invalid denominators must produce a `NOT_MEANINGFUL` or blocked status. They may not produce a synthetic ratio or neutral score.

## 9. BSE controlled quarantine

The tested free structured statement routes did not provide an accepted BSE three-statement bundle.

For BSE issuers:

- CNINFO official periodic-report identity and link are retained;
- financial statement values remain quarantined;
- no financial factor or valuation denominator may be generated from missing structured facts;
- FMDL-3B must build and validate official-document extraction before promotion from quarantine.

Quarantine is an explicit state, not missing-value imputation and not exclusion from the source registry.

## 10. Point-in-time eligibility

At requested as-of timestamp `T`, a financial version is eligible only when:

- `available_from <= T`;
- `effective_from <= T`;
- `superseded_at` is null or `T < superseded_at`;
- source lineage exists;
- record quality is not invalid, failed or quarantined.

A share-count version is eligible only when its effective date is not later than the market-price as-of date.

## 11. Zero-tolerance failures

- report period used as announcement date;
- availability before the official announcement;
- silent overwrite of a prior revision;
- future-effective share count used for current capitalization;
- missing source identity in a decision-grade row;
- unresolved provider conflict in published Current;
- fallback metadata presented as official;
- provider PE/PB presented as decision-grade without PIT recomputation;
- quarantined BSE facts used in factors or valuation;
- any trade authority.
