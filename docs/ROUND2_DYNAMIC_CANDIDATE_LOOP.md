# Round 2 — Full-market screening to governed Candidate loop

## Purpose

Round 2 connects the accepted A-share full-market screen to Candidate operations without converting a ranking signal into an automatic investment decision.

The loop consumes the exact immutable screening artifact produced by the governed FMDL daily transaction. On a completed weekly watermark it updates an observation ledger, applies hysteresis, creates a Candidate change proposal and publishes the result to a unique `automation/candidate-dynamic-<run_id>-a<attempt>` branch. `main` remains the sole Canonical and is never pushed directly.

## Mutation authority

The only route eligible for deterministic mutation is `research_queue_members`:

- a new security needs at least two consecutive qualifying Longlist appearances;
- weekly admissions and exits are capped;
- sleeve concentration is capped;
- only names originally admitted by this dynamic loop can be automatically removed;
- legacy Research Queue exits are proposal-only;
- Candidate Core, Shadow Track and Ready for User Decision are never changed automatically.

Every generated branch must pass a Draft PR, exact Candidate delta validation, full diff review, lineage review and zero unresolved review-thread gate before an authorized merge.

## Operating states

- `ROUND2_OPERATING_OBSERVATION`: engineering is installed but fewer than three completed weekly cycles have been observed.
- `ROUND2_PRODUCTION_ACCEPTED`: at least three completed weekly cycles have passed while all governance controls remain intact.

Neither state authorizes portfolio trades. Real-account positions, simulation positions, decisions and orders are outside this workflow. `orders=0` and `trade_authority=NONE` are permanent boundaries.
