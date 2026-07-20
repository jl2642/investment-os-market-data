# FMDL-3E-B/C — Market and Financial PIT Incremental Refresh

## Purpose

Validate the first real operating deltas against the frozen FMDL-3D Baseline-0:

1. a strictly advancing completed A-share market-session path;
2. first-disclosure financial PIT arrival;
3. correction, supplement or restatement revision-chain replay;
4. explicit affected-symbol and affected-period routing;
5. immutable baseline and source-file protection.

## Phase boundary

This phase creates and accepts delta assets only. It does not yet propagate changes into financial factors, capitalization, valuation, shareholder return or FMDL-3D Unified Current. Downstream propagation, full-vs-incremental equality, failure injection and rollback are FMDL-3E-D/E.

## Operating modes

- `fixture`: deterministic unit and PR validation using generated market values; financial cases use real accepted historical PIT revision chains from FMDL-3B-4.
- `live`: production mode when FMDL-1 Current contains a completed market session strictly later than Baseline-0.
- `real_completed_session_replay`: production-eligible acceptance fallback when no post-Baseline completed session yet exists. It uses the accepted FMDL-1 snapshot's actual `prev_close -> close` transition for the latest real completed session, preserves Baseline-0 unchanged and records that post-Baseline live advancement has not yet been observed.

The replay fallback is not a synthetic price test and does not relabel intraday data as completed-session data. It exists so operational mechanics can be accepted without waiting for clock time while the absence of a post-Baseline live event remains explicit.

## Acceptance

- FMDL-3E-A pointer and Baseline-0 identity align;
- all frozen FMDL-3D source hashes remain unchanged;
- the tested market-session pair strictly advances and symbol coverage is at least 99%;
- replay acceptance uses actual accepted completed-session `prev_close` and `close` values;
- event IDs are unique and every event has explicit affected scope;
- at least one first-disclosure case and one revision case exist;
- old document versions remain preserved in the version ledger;
- future information count is zero;
- authority is research evidence only and trade authority is `NONE`.

## Controlled limitation

When replay mode is used, `post_frozen_baseline_advance_observed=false` is carried in Decision, Release and Last-success. FMDL-3E-D/E may use the accepted replay delta for deterministic propagation tests, while later scheduled operation can replace it with a true post-Baseline live increment without altering Baseline-0.

## Exit

`FMDL3EBC_MARKET_AND_FINANCIAL_INCREMENTAL_REFRESH_ACCEPTED`

Next gate:

`FMDL-3E-DE_PROPAGATION_RESILIENCE_AND_REPLAY`

Canonical production publication trigger: `2026-07-20T10:44+08:00`; no contract, dataset or acceptance semantics changed.
