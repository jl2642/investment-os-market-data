# FMDL-6X2-C — Historical Listing & Lifecycle Backfill

## Objective

Create the effective-dated listing and lifecycle history domain without converting a current directory into fabricated history.

## Production boundary

The accepted evidence base is every immutable FMDL-6X2-B identity release, each already bound to official Nasdaq Trader current-directory snapshots. Optional SEC, exchange or issuer official evidence bundles may add exact effective dates. No third-party history source is silently substituted.

The initial production run may contain only the activation-date snapshot. In that case it must publish:

- one observation-only active-history anchor for every accepted Listing;
- an explicit coverage gap from 2005-01-01 to the day before the first accepted official snapshot;
- `historical_completion_claimed = false`;
- no fabricated listing, delisting, merger, symbol-change or venue-transfer date.

## Lifecycle logic

Across accepted snapshot dates the engine detects:

- first observed or reappearing Listings;
- disappearance windows;
- stable-Security symbol-change candidates;
- stable-Security venue-transfer candidates;
- combined symbol-and-venue-change candidates.

A disappearance is never called a delisting, merger or acquisition without official cause evidence. Observation dates are not legal effective dates.

## Confidence grades

- `OFFICIAL_EFFECTIVE_DATE`: exact date supported by validated SEC, exchange or issuer official evidence.
- `BOUNDED_EVENT_WINDOW`: change occurred between two accepted snapshots, exact date or cause unconfirmed.
- `OBSERVATION_ONLY`: state was observed on a specific snapshot date.

## Ongoing accumulation

The workflow also listens for successful FMDL-6X2-B production runs, so each accepted daily identity release extends the history domain and allows deterministic event-window detection.

## Exit

`FMDL6X2C_HISTORICAL_LISTING_AND_LIFECYCLE_BACKFILL_ACCEPTED`

Next gate:

`FMDL-6X2-D_MARKET_HISTORY_CORPORATE_ACTIONS_AND_FX_STORE`
