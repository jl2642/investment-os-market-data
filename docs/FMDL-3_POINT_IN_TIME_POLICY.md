# FMDL-3 Point-in-Time, Availability & Restatement Policy

## 1. Policy status

`FROZEN_FOR_FMDL3A_SOURCE_BENCHMARK`

This policy defines how FMDL-3 prevents financial data that became public later from appearing in an earlier historical replay.

## 2. Five distinct dates

FMDL-3 must not collapse the following dates:

1. `report_period_end` — when the economic period ended;
2. `announcement_date` — the verified public disclosure date;
3. `announcement_timestamp` — exact disclosure time when available;
4. `available_from` — earliest timestamp at which the system permits market use;
5. `source_retrieved_at` — when FMDL retrieved the source.

`report_period_end` is never a substitute for public availability.

## 3. Version interval

Each fact version carries:

- `revision_sequence`;
- `effective_from`;
- `superseded_at`.

A replay selects the version whose interval contains the requested `as_of_timestamp` and whose `available_from` is not later than the replay timestamp.

## 4. Source timing cases

### 4.1 Exact timestamp available

Use the verified timestamp. FMDL-3A must determine whether the source timestamp is exchange-local and whether after-close disclosures become usable on the next trading session for daily research outputs.

### 4.2 Date only

Use a conservative convention frozen in FMDL-3A. The convention must avoid same-day use when disclosure timing is unknown and must be encoded in configuration rather than analyst judgement.

### 4.3 Announcement date unavailable

The fact cannot enter decision-grade point-in-time output. It may remain in an audit-only raw layer with `missing_required_source`.

### 4.4 Provider supplies only current restated history

The provider route is not sufficient for survivorship-safe point-in-time replay unless historical versions can be reconstructed from primary filings or archived provider evidence. The route may still support Current after explicit labeling, but cannot be presented as historical PIT evidence.

## 5. Derived-value availability

A derived value becomes available at the maximum `available_from` of every required input.

Examples:

- TTM revenue uses four valid quarters and inherits the latest availability time;
- year-over-year growth requires both current and comparison periods to be available;
- ROE requires point-in-time earnings and equity inputs;
- PE requires the market numerator at the valuation timestamp and a financial denominator available no later than that timestamp.

## 6. Restatements and corrections

### 6.1 New version, never overwrite

A correction or restatement creates a new source record and new canonical fact revision.

### 6.2 Historical replay

A replay before the correction announcement uses the earlier version even when the corrected value is now known.

### 6.3 Current

Current may use the latest accepted revision, but its manifest and row lineage retain the superseded values and source IDs.

### 6.4 Provider backfills

When a provider silently changes historical values, FMDL must detect changed source hashes or values. Unexplained changes enter a conflict or quarantine state until reconciled.

## 7. Period construction rules

- cumulative and single-quarter values are separate bases;
- derived single-quarter values require comparable cumulative inputs;
- TTM must not combine incompatible bases or duplicate cumulative periods;
- fiscal period labels alone do not prove period dates;
- comparative columns inside a new filing inherit the new filing's availability date unless an earlier source independently disclosed them;
- recast historical comparatives are new versions visible from the recast announcement date.

## 8. Corporate actions and share counts

Valuation requires share-count evidence effective at the market timestamp. Issuance, repurchase, conversion, split and other share-count events must have effective dates and source lineage. A newly disclosed current share count must not be projected backward without evidence.

## 9. PIT quality states

- `PIT_VALID`
- `PIT_VALID_CONSERVATIVE_DATE_FALLBACK`
- `PIT_PARTIAL_MISSING_EXACT_TIME`
- `PIT_BLOCKED_MISSING_ANNOUNCEMENT_DATE`
- `PIT_BLOCKED_UNRESOLVED_REVISION`
- `PIT_BLOCKED_PROVIDER_CURRENT_ONLY`
- `PIT_QUARANTINED_SOURCE_CONFLICT`

Only valid states may enter decision-grade replay. Permitted partial states and tolerances must be frozen in FMDL-3A.

## 10. Zero-tolerance tests

FMDL-3E must demonstrate:

- zero rows with `available_from > as_of_timestamp`;
- zero use of report-period end as availability date;
- zero silent restatement overwrites;
- zero derived values available before their latest component;
- zero Current rows missing source IDs;
- zero unresolved conflicting versions published as valid;
- zero future share-count or corporate-action states in historical valuation.

## 11. Controlled limitations

FMDL-3 may initially lack exact intraday disclosure timestamps for some sources. Such limitations are acceptable only when a conservative explicit availability convention prevents future leakage and the affected coverage is measured.

A current-only financial provider may be useful for present-day screening but cannot be used to claim historical point-in-time validity.

## 12. Next implementation step

FMDL-3A must test candidate sources for:

- announcement-date availability;
- access to original and revised filings;
- historical provider-version behaviour;
- field-level source lineage;
- sector coverage;
- GitHub runner stability;
- redistribution and storage constraints.
