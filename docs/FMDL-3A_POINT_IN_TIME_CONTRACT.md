# FMDL-3A Point-in-Time Contract

## 1. Contract status

This contract is source-benchmark specific and inherits the FMDL-3 architecture policy.

It freezes a daily-resolution availability model for FMDL-3B. It does not authorize intraday financial-factor use.

## 2. Required temporal fields

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

Unknown timestamps remain null. They are not reconstructed from report-period labels.

## 3. Daily availability rule

### 3.1 Official filing metadata exists

For an official filing announced on calendar date `D`:

- retain the raw platform timestamp when provided;
- for daily-resolution research, set `available_from` to the next verified A-share trading session at `09:30:00+08:00`;
- the rule is deliberately conservative and uniform across evening, date-only and ambiguous timestamp records.

### 3.2 Official metadata is unavailable

A third-party announcement record may be retained as:

`DEGRADED_FALLBACK`

It may support investigation and recovery but is not decision-grade until reconciled with an official filing identity.

### 3.3 Report period

`report_period_end` is an accounting-period key only.

The following are prohibited:

- assigning availability to the report-period end;
- assigning availability to an expected publication date;
- assigning availability from the first date seen at the data provider;
- using a later revised value in an earlier as-of replay.

## 4. Trading calendar

The benchmark uses an explicit A-share trading calendar.

A weekend-only approximation is not accepted for decision-grade publication. If the calendar route fails, the benchmark must fail the point-in-time gate.

## 5. Revision sequence

For each issuer, report period and filing family:

1. order identified full-report filings by official announcement time;
2. assign `revision_sequence = 1` to the first public version;
3. assign increasing sequence numbers to corrections, revised reports and updated full reports;
4. set the prior version's `superseded_at` to the later version's `available_from`;
5. retain every version and source link.

Keywords such as `更正`, `修订`, `更新后` and `补充` are revision signals, not sufficient proof by themselves. FMDL-3B must reconcile title, period, issuer and source document identity.

## 6. Statement-provider timestamps

Structured providers may expose `NOTICE_DATE`, `UPDATE_DATE`, `更新日期` or similar fields.

These fields are retained and benchmarked, but they do not outrank official filing metadata. They may be used for:

- retrieval monitoring;
- provider freshness checks;
- conflict detection;
- fallback investigation.

They may not replace the official `available_from` rule without a separately accepted source-contract revision.

## 7. Point-in-time eligibility

At requested as-of timestamp `T`, a version is eligible only when:

- `available_from <= T`;
- `effective_from <= T`;
- `superseded_at` is null or `T < superseded_at`;
- source lineage exists;
- record quality is not invalid, failed or quarantined.

## 8. Zero-tolerance failures

- report period used as announcement date;
- availability before the announcement;
- silent overwrite of a prior revision;
- a missing source identity in a decision-grade row;
- unresolved provider conflict in published Current;
- fallback metadata presented as official;
- any trade authority.
