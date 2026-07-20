# FMDL-3E-D/E — Downstream Propagation, Deterministic Replay and Resilience

## Objective

Close FMDL-3E by proving that accepted FMDL-3E-B/C delta assets can be propagated into a new unified research-evidence state without mutating the frozen FMDL-3D baseline, and that the operating chain is deterministic, idempotent and recoverable.

## FMDL-3E-D — Propagation

The propagation candidate:

- consumes the accepted FMDL-3E-BC Last-success and immutable delta assets;
- applies accepted completed-session close changes to capitalization, price-linked valuation and shareholder-return yield fields;
- preserves controlled nulls and all `trade_authority=NONE` boundaries;
- records FMDL-3E-BC and FMDL-3E-DE lineage in every row;
- produces both an incremental result and an independently constructed full-rebuild reference;
- requires zero row or field mismatch between the two paths.

Financial replay events in the current accepted FMDL-3E-BC release are document-version PIT events. They update event lineage and affected-scope evidence but do not fabricate unavailable pre-revision structured numeric values.

## FMDL-3E-E — Resilience

Acceptance requires:

- replaying the same accepted delta twice produces zero change;
- duplicate market-symbol injection is rejected;
- future financial-event injection is rejected;
- corrupted semantic hash is rejected;
- failed candidates do not mutate Current or Last-success;
- all frozen source hashes remain unchanged;
- independent validation reproduces every semantic hash.

The first canonical publication establishes the initial FMDL-3E Final Current and Last-success. A post-publication replay is then run against those non-null pointers to prove that failure injection preserves an already-existing LKG, rather than only proving that no state is created when no prior LKG exists.

## Publication

Successful acceptance publishes:

- immutable Release;
- Current;
- Archive;
- `outputs/status/FMDL3E_LAST_SUCCESS.json`.

No score, alpha claim, target price, candidate-pool mutation, portfolio action or trade authority is created.

## Exit

`FMDL3E_INCREMENTAL_PROPAGATION_RESILIENCE_AND_REPLAY_ACCEPTED`

Next gate:

`FMDL-4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION`
