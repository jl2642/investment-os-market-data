# Round 2 — Full-market screening to governed Candidate loop

## Purpose

Round 2 connects the accepted A-share full-market screen to Candidate operations without converting a ranking signal into an automatic investment decision.

The loop consumes the exact immutable screening artifact produced by the governed FMDL daily transaction. On a completed weekly watermark it updates an observation ledger, applies hysteresis and creates a Candidate change proposal. The result is published to a unique `automation/candidate-dynamic-<run_id>-a<attempt>` branch. `main` remains the sole Canonical and is never pushed directly.

## Two-stage Canonical promotion

Round 2 deliberately separates evidence production from Candidate application.

1. **Proposal PR** — contains the observation ledger, change proposal, operating state and an immutable `CANDIDATE_CURRENT_PROPOSED.json`. The Canonical Candidate file is unchanged in this PR.
2. **Candidate application PR** — after the proposal has passed its gates and entered `main`, an authorized observer creates a second PR containing only the exact proposed `CANDIDATE_CURRENT.json`. The Round 2 validator compares it with both the prior Canonical state and the approved proposed snapshot.

This separation prevents legacy WP3-R observation workflows from confusing a governed Candidate change with an unauthorized mutation. It also makes the investment-object delta independently reviewable before it is applied.

## Mutation authority

The only route eligible for deterministic change is `research_queue_members`:

- a new security needs at least two consecutive qualifying Longlist appearances;
- weekly admissions and exits are capped;
- sleeve concentration is capped;
- only names originally admitted by this dynamic loop can be removed through the deterministic dynamic-exit rule;
- legacy Research Queue exits are proposal-only;
- Candidate Core, Shadow Track and Ready for User Decision are never changed automatically.

Every proposal and application must pass a Draft PR, exact Candidate delta validation, full diff review, lineage review and zero unresolved review-thread gate before an authorized merge.

## Operating states

- `ROUND2_OPERATING_OBSERVATION`: engineering is installed but fewer than three completed weekly cycles have been observed.
- `ROUND2_PRODUCTION_ACCEPTED`: at least three completed weekly cycles have passed while all governance controls remain intact.

Neither state authorizes portfolio trades. Real-account positions, simulation positions, decisions and orders are outside this workflow. `orders=0` and `trade_authority=NONE` are permanent boundaries.
