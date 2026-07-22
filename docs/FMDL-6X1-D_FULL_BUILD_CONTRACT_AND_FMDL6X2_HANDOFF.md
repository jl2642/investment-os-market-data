# FMDL-6X1-D — Full-Build Contract & FMDL-6X2 Handoff

## Purpose

Freeze the production architecture for the full US-equity Security Master, historical identity, market, corporate-action, FX, SEC filing and financial-fact stores before any full-build row is created.

This phase converts the accepted FMDL-6X1-B universe boundary and FMDL-6X1-C live source decision into a bounded engineering contract. It does not itself build the universe or mutate Investment OS state.

## Binding decisions

1. **Current identity first.** FMDL-6X2 starts with a complete current `XNYS` / `XNAS` / `XASE` Security Master using the two working Nasdaq Trader official directories.
2. **Historical identity is reconstructed, not invented.** Exact effective dates require official evidence. Bounded event windows and observation-only records remain explicitly lower-confidence.
3. **SEC remains official-only for decision-grade identity, filings and facts.** GitHub-hosted direct requests are blocked by repeatable 403 responses. Controlled ChatGPT-web, local-runner or self-hosted official retrieval is the interim execution route. Third-party SEC proxies are not authorized.
4. **Free market history remains non-decision-grade until reconciled.** Yahoo dual Chart routes are an interim fallback; Stooq is disabled after HTML challenge detection.
5. **ADR and special-instrument conflicts go to review queues.** No unresolved ADR, composite security or conflicting classification becomes core research eligible.
6. **No partial promotion.** A failed or incomplete shard cannot replace Current or LKG.
7. **No brokerage dependency.** Research production can be completed without a US brokerage channel; channel and portfolio admission remain pending.

## Fixed FMDL-6X2 sequence

- `FMDL-6X2-A` — Current Security Master Production
- `FMDL-6X2-B` — Issuer Identity, Classification & Review Queues
- `FMDL-6X2-C` — Historical Listing & Lifecycle Backfill
- `FMDL-6X2-D` — Market History, Corporate Actions & FX Store
- `FMDL-6X2-E` — SEC Filings & Financial Facts Store
- `FMDL-6X2-FINAL` — Full Store Reconciliation & Operational Acceptance

This is the fixed six-round FMDL-6X2 program. Repairs are limited to failed acceptance gates, source breakage or material schema/identity defects.

## History targets

- Historical identity target: `2005-01-01` onward, with earlier official evidence retained when available.
- Market history initial target: `2010-01-01` onward.
- SEC filing/fact target: `2009-01-01` onward, subject to actual official source availability and accession lineage.

These are coverage targets, not permission to fabricate unavailable history.

## Publication model

Every domain uses Work → Candidate → Current → Immutable Release → Archive, plus per-domain LKG and program Last-success. Current promotion is atomic and requires complete domain manifests and quality gates.

## Authority boundary

`trade_authority = NONE`.

No candidate, simulation, real-account or order state may change in FMDL-6X1-D or FMDL-6X2.
