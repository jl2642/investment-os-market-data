# Source Registry v1.0.0

## 1. Policy

The project uses only free or free-tier data sources. A source is not trusted merely because a library returns a table. Each adapter must record the actual upstream route, retrieval time and observed fields.

The registry distinguishes:

- **adapter**: code invoked by this repository;
- **upstream provider**: the public site or exchange endpoint ultimately supplying the data;
- **dataset capability**: fields and markets expected from the route;
- **operating status**: whether the route is approved, degraded, disabled or experimental.

## 2. Approved initial adapter

### AKShare

- Registry ID: `akshare`
- Cost: free/open-source
- Role: primary Python adapter for FMDL-1 MVP
- Status: `APPROVED_FOR_MVP_TESTING`
- Authentication: none expected for selected public interfaces
- Permitted datasets:
  - A-share security list
  - A-share daily spot/close snapshot
  - Trading calendar where stable
  - Selected valuation and market-cap fields where supplied
- Restrictions:
  - No assumption of commercial SLA
  - Upstream field names and routes may change
  - Every interface must be wrapped behind a local adapter
  - Direct library output cannot be published without normalization and QA

AKShare is an adapter family, not a single source of truth. The runtime manifest must record the exact function name and, where known, the underlying provider route.

## 3. Upstream provider classes

The initial adapter may expose data sourced from public market-information routes such as exchange pages or major public finance portals. These are registered as provider classes rather than guaranteed endpoints until verified in FMDL-1B/C.

| Provider ID | Intended role | Initial status |
|---|---|---|
| `sse_public` | Shanghai security identity/calendar cross-check | EXPERIMENTAL |
| `szse_public` | Shenzhen security identity/calendar cross-check | EXPERIMENTAL |
| `bse_public` | Beijing security identity/calendar cross-check | EXPERIMENTAL |
| `eastmoney_public` | Broad A-share market snapshot fields | APPROVED_FOR_MVP_TESTING |
| `sina_public` | Limited fallback/cross-check where adapter support exists | EXPERIMENTAL |

No provider class becomes an active fallback until its adapter and field mapping are tested.

## 4. Source priority by dataset

### a_share_universe

1. Primary AKShare universe interface selected in FMDL-1B.
2. Exchange/public cross-check for counts and symbol identity where feasible.
3. Previous last-known-good universe only as a stale reference, never silently relabelled current.

### daily_market_snapshot

1. Primary AKShare all-A-share spot/close interface selected in FMDL-1C.
2. Secondary public interface only after field-level reconciliation is implemented.
3. Previous last-known-good snapshot may remain the current accepted release when a new run fails, but its original `as_of_date` and stale status remain unchanged.

### trading_calendar

1. Stable exchange or AKShare calendar interface.
2. Weekday heuristic is never sufficient by itself to declare a Chinese trading day.

## 5. Source status values

- `APPROVED_FOR_MVP_TESTING`
- `ACTIVE_PRIMARY`
- `ACTIVE_FALLBACK`
- `DEGRADED`
- `DISABLED`
- `EXPERIMENTAL`
- `RETIRED`

Promotion from testing to active requires a successful real-data run and documented field mapping.

## 6. Failure and fallback rules

- Retry only transient network or server failures with bounded exponential backoff.
- Do not retry schema or semantic failures as if they were network failures.
- A fallback dataset must pass the same canonical schema and QA gates as the primary.
- Mixing fields from multiple sources requires field-level provenance.
- Conflicting source values are not averaged automatically.
- If no candidate passes, quarantine the run and retain the last-known-good output.

## 7. Source evidence required in each manifest

- adapter name and version;
- exact adapter function/endpoint identifier;
- upstream provider ID when known;
- retrieval start/end timestamps;
- source-reported trading/as-of date;
- raw row/column counts;
- response or raw-file hash where retained;
- warnings, retries and fallback use.

## 8. Prohibited practices

- Paid API calls or unapproved trial-credit consumption.
- Browser-session cookies or personal credentials committed to the repository.
- Hidden scraping that violates an explicit access restriction.
- Fabricating unavailable values.
- Treating a stale prior snapshot as current.
- Publishing a source result without schema and quality validation.

## 9. FMDL-1B/C promotion requirement

The production adapter selection must update this registry with:

- exact AKShare function names;
- observed column mappings;
- upstream source class;
- successful sample date;
- limitations and fallback status.
