# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Active phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed subphase: **FMDL-1A-R — Production Architecture & Contract Completion**
- Next production batch: **FMDL-1B/C — A-share Universe Builder + Daily Market Snapshot**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning and publication. It does not own investment recommendations, position sizing, portfolio migration or order execution. Those remain with Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — machine-readable source, universe, schedule and quality rules.
2. `schemas/` — canonical dataset and manifest schemas.
3. `ingestion/` — source adapters added in FMDL-1B/C.
4. `pipeline/` — normalization, QA, versioning and publishing logic added in FMDL-1B/C/D.
5. `datasets/` — dated raw/processed snapshots and last-known-good state.
6. `outputs/` — stable Investment OS consumption files.
7. `docs/` — governance, contracts and acceptance evidence.
8. `scripts/` — deterministic validation utilities.
9. `.github/workflows/` — scheduled automation added in FMDL-1E.

## Canonical documents

- `docs/FMDL-1A_ARCHITECTURE.md`
- `docs/DATA_CONTRACT.md`
- `docs/SOURCE_REGISTRY.md`
- `docs/QUALITY_GATES.md`
- `docs/UPDATE_CADENCE.md`
- `docs/INVESTMENT_OS_INTERFACE.md`
- `docs/FMDL-1A-R_ACCEPTANCE.md`

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
- FMDL-2 A-share Factor & Screening Funnel
- FMDL-3 Financial & Valuation Data Hardening
- FMDL-4 Public Equity + Investment OS Integration
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
