# FMDL-3B-3 — Comparability & Restatement Hardening

## Purpose

FMDL-3B-3 converts the accepted FMDL-3B-2 statement base into an explicit comparability and revision-control layer. It does not recollect the 5,528-symbol statement universe and it does not alter source values. It classifies official disclosures, rebuilds canonical revision chains, blocks silent restatement overwrite, and emits only the exceptions that downstream factor calculations must respect.

## Entry gate

`FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE`

The input release is resolved from `outputs/status/FMDL3B2_LAST_SUCCESS.json` and must contain 32 normalized and 32 revision shards.

## Canonical revision logic

The FMDL-3B-2 CNINFO query intentionally retained every disclosure that matched the periodic-report search. Those rows include full periodic reports, corrected full reports, correction notices, performance-briefing notices, disclosure reminders, sponsor reports, inquiry responses and other ancillary documents. FMDL-3B-3 separates document discovery from accounting revision authority.

Only these classes define the canonical accounting revision chain:

- `PERIODIC_REPORT_FULL`
- `PERIODIC_REPORT_CORRECTED_FULL`

Correction notices remain evidence but do not become a structured-value revision by themselves. Ancillary documents never supersede a periodic report.

When multiple canonical documents exist for the same issuer and period, the latest provider values may be used for Current after the latest corrected filing becomes available. Earlier numeric versions are not reconstructed from the current provider export. Historical replay before the correction is therefore blocked and surfaced, not silently backfilled.

## Comparability rules

YoY and trend comparisons are generated only between the same issuer, statement, canonical field and fiscal-period type. The default state is comparable when currency, units, basis, source route, provider line and revision posture remain controlled.

Exception states:

- `COMPARABLE_WITH_WARNING`: latest values are usable, but a restatement, line rename, source-route change or non-consecutive fiscal year must remain visible.
- `NOT_COMPARABLE`: one or both inputs are not decision grade, or currency, units or basis changed.

The published bridge is exception-only. Absence from the bridge means comparable under the frozen same-field/same-fiscal-period rules; it does not mean that arbitrary periods or unrelated fields may be compared.

## Outputs

- authoritative revision lineage;
- issuer-period revision status;
- fact-level comparability exceptions;
- transition-level comparability bridge;
- classification and exception summaries;
- independent validation, immutable Release, compact Current, Archive and Last-success pointer.

## Authority

Data and research evidence only. `trade_authority = NONE`.

## Exit gate

`FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED`

Next gate: `FMDL-3B-4_STATEMENT_CURRENT_AND_ACCEPTANCE`.
