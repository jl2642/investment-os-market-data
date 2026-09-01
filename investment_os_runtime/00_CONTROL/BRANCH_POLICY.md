# Branch Policy

This policy is subordinate to `SYSTEM_CURRENT.json`.

## Long-lived branches

Only two branches are intended to remain long-lived:

- `main` — canonical code, contracts and small governed state.
- `operating-current` — runtime pointers, latest-attempt receipts and last-known-good domain state.

## Temporary branches

`agent/*` and `automation/*` branches are temporary implementation or runtime transport surfaces. They are not authorities merely because they exist.

New temporary branches must have one explicit consumer or merge target. After their result has been merged, consumed, or represented by an immutable receipt/artifact, the branch is eligible for deletion. S4 will perform the first broad historical branch cleanup after the simplified production chain is accepted.

## Runtime evidence

A run branch may transport a governed result, but runtime truth belongs to the `operating-current` receipt/index and immutable workflow artifacts. A retained run branch must never be treated as a third canonical state plane.

## Data policy

New large generated datasets must not be duplicated across release/current/candidate/archive paths merely to express status. Current state should converge toward lightweight pointers, manifests and checksums. Historical bulk-data compaction is deferred until after S4 acceptance to avoid mixing repository-history surgery with investment-chain repair.

## Safety boundary

No branch policy grants trade authority. `orders=0` and `trade_authority=NONE` remain binding.
