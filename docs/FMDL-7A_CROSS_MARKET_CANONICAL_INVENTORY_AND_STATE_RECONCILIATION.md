# FMDL-7A — Cross-market Canonical Inventory and State Reconciliation

## Purpose

FMDL-7A reconciles the accepted A-share, Hong Kong Stock Connect, US research-adapter and Investment OS operating states into one explicit inventory without refreshing market data, executing research, changing any investment state or prematurely rebuilding the File Library Canonical package.

The stage answers four questions:

1. Which component is the current binary Canonical base and which components remain immutable overlays?
2. What is the latest independently bound state for the real account, simulation book and Candidate Pool?
3. Which data or state domains are stale, unconfirmed or non-Decision-grade?
4. Which duplicate exposures and cross-listing cases require controlled review before any future admission or portfolio action?

## Bound operating base

- Investment OS Release 8 remains the binary Canonical base: `INVESTMENT_OS_R8_20260720_501345e84562`.
- FMDL-5-FINAL remains an accepted, immutable Hong Kong Stock Connect overlay pending the single-package refresh in FMDL-7E.
- FMDL-6X4-FINAL remains the accepted and frozen US research adapter; its market and attribution fallback data are not promoted to Decision-grade.
- FMDL-7-0 Release 48 is the entry authority and opens only FMDL-7A.

## Reconciled investment state

The latest bound portfolio state is the Release 8 operating state as of `2026-07-20_CLOSE`:

- real account: seven holdings, RMB 448,831.42 total assets and RMB 120.49 execution cash;
- simulation book: sixteen holdings, RMB 1,001,714.58 total assets and RMB 219,533.98 available cash;
- Candidate Core: twenty names with six Active Memo thresholds and zero triggered thresholds in the bound review.

These are `LAST_KNOWN_GOOD`, not a claim that no changes occurred after the as-of time. Any post-as-of trade, cash movement, simulation transaction or Candidate Pool change requires explicit user confirmation before FMDL-7C can treat the state as current.

## Freshness and Decision-grade boundaries

- A-share full-market data are anchored to 2026-07-17 and are stale for a new full-market decision. Existing state may be recovered as LKG, but new screening or portfolio conclusions require a refresh.
- The Hong Kong overlay is accepted for research and re-entry review only; graduation does not equal Candidate Pool admission.
- The US adapter is operational for research production and benchmark validation only. Formal candidate promotion, formal simulation, brokerage and performance claims remain closed.
- Research pools, Shadow Tracks and benchmark pools must never be represented as formal candidates or positions.

## Duplicate exposure registry

Three controlled cases are registered:

- real-account same-index exposure: `159612` and `159655`, with no automatic consolidation;
- A/H review: Midea Group `HKEX:00300`;
- A/H review: Wuxi AppTec `HKEX:02359`.

Ticker-only matching and automatic market selection are prohibited.

## File Library reconciliation

The Release 8 Pointer was discoverable and its Release ID and package SHA matched GitHub's accepted Release 8 identity. The binary ZIP was not independently retrievable or byte-verifiable through File Library search in this acceptance run. FMDL-7A therefore records a matched Pointer with binary verification deferred to FMDL-7E; it does not claim the Hong Kong or US overlays are already repacked.

## Outputs

FMDL-7A publishes:

- Canonical inventory;
- Market capability matrix;
- State-domain registry including exact bound holdings and Candidate Core;
- Freshness and staleness registry;
- Cross-market duplication registry;
- File Library reconciliation record;
- Acceptance-gate matrix;
- Deterministic logical-shard registry;
- Quality report, Decision and Manifest.

## Authority boundary

FMDL-7A authorizes inventory, reconciliation, freshness classification and duplication registration only. It authorizes no market-data refresh, research execution, Candidate Pool mutation, simulation mutation, real-account mutation, rule change, Canonical repack, order creation or brokerage execution.

`trade_authority = NONE`

## Exit and next gate

Required exit:

`FMDL7A_CROSS_MARKET_CANONICAL_INVENTORY_AND_STATE_RECONCILIATION_ACCEPTED`

Only following gate:

`FMDL-7B_END_TO_END_RESEARCH_AND_DECISION_LINEAGE_ACCEPTANCE`
