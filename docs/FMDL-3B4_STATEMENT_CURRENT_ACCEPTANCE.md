# FMDL-3B-4 — Statement Current & Acceptance

## Purpose

FMDL-3B-4 closes the Financial Statement Store & Normalization phase by binding the accepted FMDL-3B-2 full-Universe statement base to the accepted FMDL-3B-3 comparability and restatement controls.

The output is a compact canonical Statement Current. It does not duplicate the full statement facts. It publishes a verified catalog and immutable pointers over the accepted statement, revision, source-index and comparability assets.

## Entry gates

- FMDL-3B-2 status must be `FMDL3B2_FULL_UNIVERSE_INITIAL_BUILD_ACCEPTED_WITH_CONTROLLED_QUARANTINE`.
- FMDL-3B-3 status must be `FMDL3B3_COMPARABILITY_AND_RESTATEMENT_HARDENING_ACCEPTED`.
- Both independent validations must be `PASS` with no hard failures.

## Acceptance rules

The candidate is accepted only when:

1. all 32 normalized statement shards, 32 revision shards and 32 source-index shards exist;
2. all four FMDL-3B-3 comparability assets exist;
3. the FMDL-3B-3 normalized-fact replay count exactly matches FMDL-3B-2;
4. every period classification is explicit;
5. every restated period blocks unsupported pre-restatement numeric replay;
6. every unresolved period is blocked;
7. all catalog paths are unique and hashable;
8. trade authority remains `NONE`.

## Publication model

An accepted main-branch run publishes:

- immutable Release;
- compact Current;
- Archive copy;
- `outputs/status/FMDL3B4_LAST_SUCCESS.json`.

A failed candidate cannot replace Current or Last-known-good.

## Exit gate

`POINT_IN_TIME_STATEMENT_STORE_ACCEPTED`

The next authorized phase is:

`FMDL-3C — Financial Quality, Growth & Balance-Sheet Factors`

FMDL-3B-4 remains a data and research-evidence layer. It does not create an investment recommendation or trade authority.
