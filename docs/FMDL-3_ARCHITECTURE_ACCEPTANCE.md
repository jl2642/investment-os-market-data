# FMDL-3 Overall Architecture & Phased Plan — Acceptance

## Acceptance state

`FMDL3_ARCHITECTURE_ACCEPTED`

The FMDL-3 architecture, point-in-time policy, phased execution plan, machine-readable program contract, JSON Schema, regression tests, main-branch publication and Last-known-good pointer have all passed. The architecture phase is formally complete and FMDL-3A is authorized.

This acceptance freezes the engineering boundary. It does not claim that any financial source has been selected, that full-market financial coverage exists, or that financial and valuation data are already operating. Those claims require real source benchmarking and execution in FMDL-3A through FMDL-3E.

## Canonical main-branch publication

- Merge commit: `0dbe643190da09dd1f7d4fc39a88dea61b29663c`
- Data publication commit: `dc8dc452040c4f0596e09326dbc938e7a446fc55`
- Architecture release: `FMDL3_ARCH_20260717T223136+0800`
- Published at: `2026-07-17T22:31:36+08:00`
- Status: `FMDL3_ARCHITECTURE_ACCEPTED`
- Architecture state: `FROZEN_FOR_FMDL3A_EXECUTION`
- Validation status: `PASS`
- Hard failures: `0`
- Authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`
- Trade authority: `NONE`

Canonical paths:

- `outputs/architecture/current/FMDL3_ARCHITECTURE_RELEASE.json`
- `outputs/architecture/current/FMDL3_ARCHITECTURE_VALIDATION.json`
- `outputs/architecture/archive/FMDL3_ARCH_20260717T223136+0800/`
- `outputs/status/FMDL3_ARCHITECTURE_LAST_SUCCESS.json`

## Accepted evidence

- Initial accepted workflow run: `29588007161` — `SUCCESS`
- Accepted Head revalidation run: `29588217734` — `SUCCESS`
- Candidate artifact: `8409825884`
- Artifact digest: `sha256:a3d92f538d3f16738ca099c85447b98211a5d2306165eac86d51cc49890b3f39`
- Candidate validation run: `FMDL3_ARCH_20260717T222708+0800`
- Main validation run: `FMDL3_ARCH_20260717T223135+0800`
- Machine checks: `14 / 14 PASS`

## Machine checks

All 14 checks passed:

1. JSON Schema validation;
2. frozen FMDL-3A → FMDL-3E phase order;
3. required sector profiles;
4. required point-in-time temporal fields;
5. canonical dataset stack;
6. global zero-tolerance hard gates;
7. Last-known-good and fail-closed publication;
8. required PIT replay before final acceptance;
9. authority boundary;
10. next-phase pointer;
11. required architecture documents;
12. architecture content contract;
13. PIT policy content contract;
14. phased-plan content contract.

## Frozen architecture decisions

### Point-in-time

FMDL-3 separates report period, announcement date, announcement timestamp, market availability, source retrieval time and revision-effective interval. Report-period end can never be used as the public availability date.

### Restatements

A restatement creates a new revision and never silently overwrites the value that was visible at an earlier historical as-of timestamp.

### Source lineage

Every decision-grade financial fact requires source identity, source location, retrieval time, original provider field, canonical field, evidence label and confidence.

### Missingness and conflicts

Missing values remain missing and never become zero, peer medians or neutral factor scores. Provider conflicts remain visible until explicitly resolved or controlled-excluded.

### Sector profiles

The required initial profiles are:

- general non-financial;
- bank;
- insurance;
- securities and brokerage;
- pre-profit or negative-earnings denominator-restriction profile.

### Canonical dataset stack

The architecture defines:

- source index;
- raw financial facts;
- normalized long-form statements;
- comparability bridge;
- financial factor detail;
- valuation snapshot;
- shareholder-return events;
- FMDL-3 Final Release.

### Authority

The architecture cannot promote a live candidate, change a simulation or real portfolio, connect to a broker, or create trade permission.

## Frozen execution plan

- `FMDL-3A` — Source Benchmark, Point-in-Time Contract & Coverage Map
- `FMDL-3B` — Financial Statement Store & Normalization
- `FMDL-3C` — Financial Quality, Growth & Balance-Sheet Factors
- `FMDL-3D` — Valuation, Capitalization, Dividend & Shareholder-Return Layer
- `FMDL-3E` — Incremental Refresh, Replay & Final Acceptance

No later phase may bypass an unresolved source, PIT, normalization, denominator or sector-routing defect from an earlier phase.

## Controlled limitations

1. Providers and fallback routes have not yet been selected.
2. Numeric coverage floors are not yet frozen because they must be based on measured source results.
3. Announcement-time conventions are architecture-level only until source-specific fields are tested.
4. No financial facts, factors or valuation Current are published by this architecture phase.
5. No issuer has been promoted or rejected based on FMDL-3 evidence.

## Authorized next phase

`FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map`

FMDL-3A must test real free/free-tier source routes on a deterministic, sector-stratified A-share sample and freeze measured source, coverage, timestamp, revision, runtime and storage contracts before FMDL-3B begins.
