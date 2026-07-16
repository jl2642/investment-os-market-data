# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Active phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed subphase: **FMDL-1A-R — Production Architecture & Contract Completion**
- Completed subphase: **FMDL-1B/C — A-share Universe Builder + Daily Market Snapshot**
- Next production batch: **FMDL-1D/E — Data Quality Hardening + Scheduled Automation**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Latest real candidate run

- Run ID: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Universe rows: `5,529`
- Snapshot rows: `5,529`
- Hard quality failures: `0`
- Market-wide provider: `sina_public` explicit free fallback
- Status: `ACCEPTED_WITH_CONTROLLED_WARNINGS`
- Current publication boundary: candidate data only; stable `outputs/current/` promotion remains FMDL-1F

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning and publication. It does not own investment recommendations, position sizing, portfolio migration or order execution. Those remain with Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — machine-readable source, universe, schedule and quality rules.
2. `schemas/` — canonical dataset and manifest schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` — normalization, QA, versioning and publishing logic.
5. `datasets/` — dated raw/processed snapshots and last-known-good state.
6. `outputs/` — candidate and stable Investment OS consumption files.
7. `docs/` — governance, contracts and acceptance evidence.
8. `scripts/` — deterministic validation utilities.
9. `.github/workflows/` — validation, candidate build and later scheduled automation.

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

## Core datasets

- `a_share_universe`
- `daily_market_snapshot`
- `trading_calendar`
- `dataset_manifest`
- `data_quality_report`

Every published dataset must carry a schema version, source timestamp, generation timestamp, QA state, row count, hash and last-known-good lineage. Failed candidate updates are quarantined and must never replace a valid current snapshot.

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP 🚧
  - FMDL-1A-R Production Architecture & Contract Completion ✅
  - FMDL-1B/C A-share Universe Builder + Daily Market Snapshot ✅
  - FMDL-1D/E Data Quality Hardening + Scheduled Automation ⏭️
  - FMDL-1F Investment OS Interface + Final Acceptance
- FMDL-2 A-share Factor & Screening Funnel
- FMDL-3 Financial & Valuation Data Hardening
- FMDL-4 Public Equity + Investment OS Integration
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
