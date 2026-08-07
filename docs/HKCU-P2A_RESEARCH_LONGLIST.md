# HKCU Phase 2A — Reproducible Research Longlist

## Purpose

P2A converts the accepted HK Stock Connect Current universe into a reproducible **research longlist**. It is a research-priority layer, not a Candidate Pool, portfolio, order, or trading layer.

Authoritative mother pool:

- `outputs/hkcu1/current/HKCU1_R2E_INVESTABLE_UNIVERSE.csv`
- expected membership is read from the accepted HKCU Current decision at runtime rather than hard-coded.

## Governance boundary

P2A may rank and filter only securities already present in HKCU Current.

It must not:

- add securities outside HKCU Current;
- mutate A-share Candidate Pool or any existing Candidate Current;
- mutate simulation or real-account holdings;
- generate orders;
- grant trade authority.

`trade_authority=NONE` is permanent.

## Data semantics

The accepted HKCU Current embeds the FMDL-5E factor snapshot that was refreshed and accepted as part of the HKCU R2E/R2F release. P2A therefore consumes those embedded factor values and percentiles directly.

The standalone `outputs/fmdl5e/current` tree is **not** an independent authority for P2A membership or freshness. It remains methodology/reference unless its accepted release is explicitly reconciled to the HKCU Current release.

## Screening funnel

1. **Canonical safety gate** — require accepted Current, publication eligibility, R2E gate pass, Southbound buy eligibility, no sell-only rows, Current freshness, allowed FMDL investability status, and `trade_authority=NONE`.
2. **Five formal FMDL-5E sleeves** — reuse the accepted sleeve definitions, factor weights, component minimums, minimum scores, and candidate caps:
   - `QUALITY_COMPOUNDER`
   - `HIGH_DIVIDEND_VALUE`
   - `TREND_LIQUIDITY`
   - `DEFENSIVE_STABILITY`
   - `RECOVERY_WATCH`
3. **Factor breadth / research readiness** — measure available factor percentiles and tag `READY_HIGH`, `READY_CONTROLLED`, or `READY_PARTIAL`. Readiness is not silently converted into a new alpha factor.
4. **Distribution-derived selection** — compute the existing formal-sleeve aggregate ranking and partition the observed aggregate-score distribution with deterministic one-dimensional k-means (`k=3`). The highest-centroid cluster becomes the P2A Longlist.
5. **Safety envelope** — the dynamic result must fall within a broad research-longlist share envelope. The envelope is a fail-closed sanity check, not a fixed target count.
6. **P2B gap ledger** — governance/value-trap, earnings-expectation revision, catalysts, transaction costs/tax, and applicable A/H relative valuation are explicitly marked `P2B_REQUIRED` and contribute zero to the P2A score.

## Why no fixed Longlist count

P2A intentionally does not say “take the top 50/80/100.” A fixed count would create false precision and could force weak names into the research queue or discard names sitting in the same score regime.

The count is therefore an **output of the observed 430-name distribution**, subject only to fail-closed quality and breadth checks.

## Expected outputs

A real run emits:

- `HKCU_P2A_SLEEVE_DETAIL.csv`
- `HKCU_P2A_RESEARCH_LONGLIST.csv`
- `HKCU_P2A_RESEARCH_MISSINGNESS.csv`
- `HKCU_P2A_FUNNEL_COUNTS.csv`
- `HKCU_P2A_QUALITY_REPORT.json`
- `HKCU_P2A_DECISION.json`
- `HKCU_P2A_MANIFEST.json`

The PR workflow also runs an independent output validator and uploads the complete real-run evidence artifact.

## Graduation

P2A passes only when:

- HKCU Current continuity is intact;
- the Longlist is a duplicate-free subset of Canonical;
- formal sleeve evaluation is reproducible;
- distribution selection stays within the safety envelope;
- missing P2B dimensions do not leak into P2A scores;
- all protected mutation counters are zero;
- `trade_authority=NONE`.

A P2A pass permits **P2B Research Enrichment only**. It does not create or graduate a formal Candidate Pool.
