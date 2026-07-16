# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Active phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed subphase: **FMDL-1A-R — Production Architecture & Contract Completion**
- Completed subphase: **FMDL-1B/C — A-share Universe Builder + Daily Market Snapshot**
- Completed subphase: **FMDL-1D/E — Data Quality Hardening + Scheduled Automation**
- Next production batch: **FMDL-1F — Investment OS Interface + Final FMDL-1 Acceptance**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Latest stable Current release

- Run ID: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Universe rows: `5,529`
- Snapshot rows: `5,529`
- Hard quality failures: `0`
- Market-wide provider: `sina_public` explicit free fallback
- Status: `PUBLISHED_WITH_WARNINGS`
- Event flags: `7`
- Stable path: `outputs/current/`
- Investment OS consumption boundary: pending FMDL-1F

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning and publication. It does not own investment recommendations, position sizing, portfolio migration or order execution. Those remain with Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — machine-readable source, universe, schedule and quality rules.
2. `schemas/` — canonical dataset, manifest, release and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` — normalization, QA, event flags, LKG publication and quarantine logic.
5. `datasets/` — dated raw/processed evidence.
6. `outputs/candidate/` — pre-publication results.
7. `outputs/current/` — stable current market-data release.
8. `outputs/status/` — last run and last successful release state.
9. `outputs/archive/` and `outputs/quarantine/` — accepted metadata and failed-run evidence.
10. `.github/workflows/` — validation, candidate testing and scheduled production.

## Canonical documents

- `docs/FMDL-1A_ARCHITECTURE.md`
- `docs/DATA_CONTRACT.md`
- `docs/SOURCE_REGISTRY.md`
- `docs/QUALITY_GATES.md`
- `docs/UPDATE_CADENCE.md`
- `docs/INVESTMENT_OS_INTERFACE.md`
- `docs/FMDL-1A-R_ACCEPTANCE.md`
- `docs/FMDL-1BC_IMPLEMENTATION.md`
- `docs/FMDL-1BC_ACCEPTANCE.md`
- `docs/FMDL-1DE_IMPLEMENTATION.md`
- `docs/FMDL-1DE_ACCEPTANCE.md`

## Core datasets

- `a_share_universe`
- `daily_market_snapshot`
- `trading_calendar`
- `dataset_manifest`
- `current_release`
- `operating_status`
- `market_event_flags`

Every published dataset carries a schema version, source timestamp, generation timestamp, QA state, row count, hash and last-known-good lineage. Failed candidate updates are quarantined and must never replace a valid current snapshot.

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP 🚧
  - FMDL-1A-R Production Architecture & Contract Completion ✅
  - FMDL-1B/C A-share Universe Builder + Daily Market Snapshot ✅
  - FMDL-1D/E Data Quality Hardening + Scheduled Automation ✅
  - FMDL-1F Investment OS Interface + Final Acceptance ⏭️
- FMDL-2 A-share Factor & Screening Funnel
- FMDL-3 Financial & Valuation Data Hardening
- FMDL-4 Public Equity + Investment OS Integration
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
