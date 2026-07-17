# FMDL-2B-4 Acceptance Plan

FMDL-2B-4 is not accepted by code completion alone. The implementation branch must produce and persist a real next-session history Current and factor Current, then pass deterministic replay and LKG-preservation checks.

## Required real-run evidence

- FMDL-1 Current refreshed to the latest completed A-share session;
- one-session history increment accepted across the current Universe;
- explicit repair attempts for the four inherited quarantines and any continuity breaks;
- composite history with zero duplicate symbol-date, future or impossible-OHLC rows;
- refreshed 26-factor table at the same as-of date;
- independent validation PASS;
- history and factor Current published in one operating transaction;
- scheduled workflow installed but no research PR-triggered production run.

## Required replay evidence

- rerun against the same Current date returns `NO_OP_ALREADY_CURRENT`;
- synthetic corporate-action discontinuity is rejected by the fast path;
- synthetic candidate validation failure preserves both prior Current directories;
- multi-session gap is fail-closed and routes to manual full rebase.

## Promotion rule

Only after the real run and replay evidence pass may the branch receive an `FMDL-2B4_ACCEPTANCE.md`, update the canonical README and merge to main. The next phase will then be FMDL-2C Screening Sleeves & Funnel.
