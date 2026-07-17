# FMDL-2B-4 — Incremental Update, Refresh & Final Acceptance

## 1. Objective

FMDL-2B-4 turns the accepted one-shot historical and factor candidates into a maintainable operating layer. It owns daily history append, targeted QFQ repair, composite-history publication, factor refresh, Last-known-good retention, stale-input blocking and final FMDL-2B operating acceptance.

It does not define stock-selection sleeves, claim factor alpha, promote a Longlist or alter any simulation or real portfolio. Those decisions remain outside FMDL-2B.

## 2. Operating sequence

```text
FMDL-1 CURRENT SNAPSHOT
  -> validate identity, date, hashes and freshness
  -> build history refresh candidate
       -> normal one-session snapshot append
       -> targeted full-series repair for continuity breaks, new symbols and old quarantines
       -> multi-session gap: block and require manual full rebase
  -> validate composite history candidate
  -> calculate full-market factor candidate at the same as-of date
  -> independently validate factor candidate
  -> atomically publish history Current + factor Current
       -> any failure: preserve both prior Last-known-good releases
```

## 3. Why the daily fast path is technically valid

The accepted history base uses forward-adjusted (`qfq`) prices. Under the forward-adjustment convention, the current completed session remains at its observed market price while earlier history is rescaled when a corporate action occurs. Therefore a completed-session market snapshot can be appended as a `qfq_current_session_equivalent` row only after continuity validation.

For each traded symbol, the engine derives the prior reference price from current close and reported percentage change and compares it with the latest accepted QFQ close. A mismatch beyond both the configured relative and absolute tolerances is not appended. It becomes a targeted full-series repair candidate.

This is an explicit composite route, not silent provider mixing. Every appended row retains `sina_public_snapshot` lineage, `qfq_current_session_equivalent` adjustment mode and `VALIDATED_INCREMENTAL` record quality.

## 4. Daily history states

Every current-Universe symbol receives one refresh state:

- `READY_INCREMENTAL` — one validated completed-session row appended;
- `READY_SUSPENDED_NO_APPEND` — current session is suspended or has no valid trade; prior history retained;
- `REPAIRED_FULL_HISTORY` — a full accepted historical series replaces the prior composite series;
- `QUARANTINED` — no accepted factor-ready history exists;
- `REPAIR_REQUIRED` — continuity or identity failure remains unresolved;
- `REMOVED_FROM_CURRENT_UNIVERSE` — retained in historical lineage but excluded from the latest factor Universe.

A failed symbol does not invalidate unrelated accepted symbols, but unresolved coverage or quality above the market-level gate blocks publication.

## 5. Composite store

The operating history store is represented by a manifest rather than by copying the entire 131 MiB base after every session:

```text
accepted immutable base
+ ordered validated daily delta files
+ full-series repair overrides
= current composite history
```

Precedence is:

1. latest accepted full-series repair;
2. latest incremental symbol-date row;
3. immutable base row.

The composite reader verifies every component hash, removes duplicate symbol-date rows by explicit precedence and never mutates the accepted FMDL-2B-2 base.

Daily deltas are compacted after the configured file-count threshold. Compaction is deterministic and preserves the same composite symbol-date result.

## 6. Gap handling

The fast path is authorized only when the latest FMDL-1 snapshot is the immediately following completed market session. A multi-session gap cannot be reconstructed from one latest snapshot and therefore triggers:

`BLOCK_AND_REQUIRE_MANUAL_FULL_REBASE`

The prior history and factor Current releases remain unchanged. The manual full-rebase workflow reuses the accepted 24-shard source route and must independently validate the replacement base before publication.

## 7. Corporate actions and repair

A symbol enters targeted repair when:

- the derived prior reference price disagrees with the latest accepted QFQ close;
- it is new to the latest accepted Universe;
- it was previously quarantined and the current source may now be usable;
- provider or adjustment lineage is not compatible with the current composite contract.

Repair downloads the complete permitted history through the frozen FMDL-2A provider route. A repaired series replaces the entire prior composite history for that symbol. Source rows are never interpolated, patched with close values or silently dropped.

## 8. Factor refresh and publication

The factor refresh reuses the accepted 26-factor FMDL-2B-3 formulas, minimum-observation rules, direction-aware percentiles and missingness policy. It reads the staged composite history candidate and calculates factors exactly at the latest accepted FMDL-1 as-of date.

Publication is atomic across history and factors:

- history candidate PASS + factor candidate PASS -> publish both Current releases;
- either candidate FAIL -> publish neither and preserve both prior LKG releases.

Current factor outputs remain research-priority evidence. They do not create screening sleeves or trade authority.

## 9. Scheduled operation

- FMDL-1 daily Current nominal business time: 17:30 Asia/Shanghai;
- FMDL-2B-4 refresh nominal business time: 18:15 Asia/Shanghai;
- GitHub cron: `15 10 * * 1-5` UTC;
- scheduled refresh is fail-closed when Current is stale, non-trading or not yet published;
- manual dispatch supports controlled acceptance and recovery runs.

## 10. Final acceptance gates

FMDL-2B-4 and the full FMDL-2B phase are accepted only after evidence demonstrates:

1. one-session incremental append over the full accepted Universe;
2. same-date rerun is deterministic and produces a no-op or identical composite result;
3. a synthetic multi-session gap blocks publication and preserves LKG;
4. a synthetic continuity break routes to full-series repair rather than silent append;
5. the four historical quarantines are retried without fabricated repair;
6. composite hashes, row counts and symbol-date uniqueness reproduce;
7. refreshed factor rows cover the latest Universe exactly once;
8. factor as-of date equals history and FMDL-1 Current dates;
9. candidate failure preserves both prior history and factor Current;
10. scheduled and manual workflows remain within the free-tier operating design;
11. no candidate pool, portfolio or trade state changes.

Only after these gates pass may development proceed to FMDL-2C Screening Sleeves & Funnel.
