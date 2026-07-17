# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Completed phase: **FMDL-1 — A-share Full-Market Data MVP**
- Active phase: **FMDL-2 — A-share Factor & Screening Funnel**
- Completed subphase: **FMDL-2A — Factor Contract & Historical Source Benchmark**
- Next production batch: **FMDL-2B — Historical Store & Basic Factor Engine**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Latest stable A-share Current release

- Run ID: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Universe rows: `5,529`
- Snapshot rows: `5,529`
- Hard quality failures: `0`
- Market-wide provider: `sina_public` explicit free fallback
- Status: `PUBLISHED_WITH_WARNINGS`
- Event flags: `7`
- Stable path: `outputs/current/`
- Investment OS interface: `outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`

## FMDL-2A accepted historical route

- Benchmark run: `FMDL2A_R2_20260717T101323+0800`
- Benchmark scope: deterministic `120`-symbol cross-board sample
- Primary: `sina_daily / AKShare stock_zh_a_daily`, QFQ
- Primary scale success: `119/120` (`99.17%`)
- Restricted fallback: `tencent_hist / stock_zh_a_hist_tx`, SH/SZ Main price-and-amount only
- Degraded on GitHub runner: `eastmoney_hist / stock_zh_a_hist`
- Readiness: `READY_FOR_FMDL_2B`
- Authority: research-priority evidence only; no factor alpha claim and no trade authority

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning, factor-data preparation and publication. It does not own investment recommendations, position sizing, portfolio migration or order execution. Those remain with Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — machine-readable source, universe, schedule, factor and quality rules.
2. `schemas/` — canonical dataset, manifest, release and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` — normalization, QA, event flags, LKG publication and quarantine logic.
5. `datasets/` — dated raw/processed evidence and later historical cache.
6. `outputs/current/` — stable current market-data release.
7. `outputs/investment_os/` — machine-validated consumer pointer.
8. `outputs/benchmark/` — source-selection evidence.
9. `outputs/archive/` and `outputs/quarantine/` — accepted metadata and failed-run evidence.
10. `.github/workflows/` — validation, production and benchmark automation.

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
- `docs/FMDL-1F_INTERFACE_AND_FINAL_ACCEPTANCE.md`
- `docs/FMDL-2A_FACTOR_CONTRACT.md`
- `docs/FMDL-2A_BENCHMARK_PLAN.md`
- `docs/FMDL-2A_SOURCE_DECISION.md`
- `docs/FMDL-2B_ENGINEERING_REQUIREMENTS.md`
- `docs/FMDL-2A_ACCEPTANCE.md`

## Core datasets and controls

- `a_share_universe`
- `daily_market_snapshot`
- `trading_calendar`
- `dataset_manifest`
- `current_release`
- `operating_status`
- `market_event_flags`
- `investment_os_market_data_interface`
- `fmdl2_factor_registry`
- `fmdl2_historical_source_routes`

Every published dataset carries a schema version, source timestamp, generation timestamp, QA state, row count, hash and last-known-good lineage. Failed candidate updates are quarantined and must never replace a valid current snapshot. Missing factor inputs remain missing and never become neutral scores or zeros.

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP ✅
  - FMDL-1A-R Production Architecture & Contract Completion ✅
  - FMDL-1B/C A-share Universe Builder + Daily Market Snapshot ✅
  - FMDL-1D/E Data Quality Hardening + Scheduled Automation ✅
  - FMDL-1F Investment OS Interface + Final Acceptance ✅
- FMDL-2 A-share Factor & Screening Funnel 🚧
  - FMDL-2A Factor Contract & Historical Source Benchmark ✅
  - FMDL-2B Historical Store & Basic Factor Engine ⏭️
  - FMDL-2C Screening Sleeves & Funnel
  - FMDL-2D Replay, Stability & Final Acceptance
- FMDL-3 Financial & Valuation Data Hardening
- FMDL-4 Public Equity + Investment OS Integration
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
