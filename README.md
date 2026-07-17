# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Completed phase: **FMDL-1 — A-share Full-Market Data MVP**
- Active phase: **FMDL-2 — A-share Factor & Screening Funnel**
- Completed subphase: **FMDL-2A — Factor Contract & Historical Source Benchmark**
- Completed subphase: **FMDL-2B-1 — Historical Store Architecture & Full-Market Pilot**
- Completed subphase: **FMDL-2B-2 — Full-Universe Sharded Initial Backfill**
- Next production batch: **FMDL-2B-3 — Basic Factor Engine**
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

## Accepted historical route and releases

### FMDL-2A source route

- Primary: `sina_daily / AKShare stock_zh_a_daily`, QFQ
- Primary benchmark: `119/120` successful (`99.17%`)
- Restricted fallback: `tencent_hist / stock_zh_a_hist_tx`, SH/SZ Main price-and-amount only
- Degraded on GitHub runner: `eastmoney_hist / stock_zh_a_hist`

### FMDL-2B-1 real pilot

- Final run: `FMDL2B1_PILOT_20260717T120653+0800`
- GitHub Actions: `29554012101` — success
- Deterministic stress sample: `300` symbols across all five boards
- Usable: `299/300` (`99.67%`)
- Normalized rows: `109,602`
- Six Zstandard Parquet pilot shards: `5.9936 MiB`
- Pilot runtime: `9.2937 minutes`
- Frozen full-backfill design: `24` logical shards, approximately `231` symbols each, initial maximum parallelism `3`

### FMDL-2B-2 full-market historical candidate

- Release: `FMDL2B2_29556547410_1`
- As-of date: `2026-07-16`
- Universe attempted: `5,529`
- Usable historical series: `5,525` (`99.9277%`)
- Controlled quarantine: `4`
- History rows: `2,494,405`
- Parquet base store: `131.6084 MiB`
- Logical shards: `24`
- Accepted future rows: `0`
- Accepted duplicate symbol-date pairs: `0`
- Accepted impossible-OHLC rows: `0`
- Independent validation run: `29563720516` — success
- Status: `ACCEPTED_WITH_CONTROLLED_FOUR_SYMBOL_QUARANTINE`
- Authority: historical evidence only; no factor rank, alpha claim or trade authority

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning, history storage, factor-data preparation and publication. It does not own investment recommendations, position sizing, portfolio migration or order execution. Those remain with Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — machine-readable source, universe, schedule, factor, history-store and quality rules.
2. `schemas/` — canonical dataset, history-row, manifest, release and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` and `scripts/` — normalization, QA, benchmark, history ingestion, LKG and quarantine logic.
5. `datasets/` — dated raw evidence, immutable history bases, daily deltas and refresh overlays.
6. `outputs/current/` — stable current market-data release.
7. `outputs/history/` — historical-store candidate, Current, status, validation and quarantine evidence.
8. `outputs/investment_os/` — machine-validated consumer pointer.
9. `outputs/benchmark/` — source and pilot evidence.
10. `.github/workflows/` — validation, production, benchmark and controlled recovery automation.

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
- `docs/FMDL-2A_ACCEPTANCE.md`
- `docs/FMDL-2B_ENGINEERING_REQUIREMENTS.md`
- `docs/FMDL-2B1_HISTORY_STORE_PILOT.md`
- `docs/FMDL-2B1_ACCEPTANCE.md`
- `docs/FMDL-2B2_FULL_BACKFILL_IMPLEMENTATION.md`
- `docs/FMDL-2B2_ACCEPTANCE.md`

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
- `a_share_daily_history`
- `fmdl2_history_store`
- `fmdl2_full_backfill_plan`
- `historical_candidate_validation`
- `historical_quarantine_retry`

Every published dataset carries a schema version, source timestamp, generation timestamp, QA state, row count, hash and last-known-good lineage. Failed candidate updates are quarantined and must never replace a valid current snapshot. Missing history or factor inputs remain missing and never become neutral scores or zeros.

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP ✅
  - FMDL-1A-R Production Architecture & Contract Completion ✅
  - FMDL-1B/C A-share Universe Builder + Daily Market Snapshot ✅
  - FMDL-1D/E Data Quality Hardening + Scheduled Automation ✅
  - FMDL-1F Investment OS Interface + Final Acceptance ✅
- FMDL-2 A-share Factor & Screening Funnel 🚧
  - FMDL-2A Factor Contract & Historical Source Benchmark ✅
  - FMDL-2B Historical Store & Basic Factor Engine 🚧
    - FMDL-2B-1 Historical Store Architecture & Full-Market Pilot ✅
    - FMDL-2B-2 Full-Universe Sharded Initial Backfill ✅
    - FMDL-2B-3 Basic Factor Engine ⏭️
    - FMDL-2B-4 Incremental Update & Final Acceptance
  - FMDL-2C Screening Sleeves & Funnel
  - FMDL-2D Replay, Stability & Final Acceptance
- FMDL-3 Financial & Valuation Data Hardening
- FMDL-4 Public Equity + Investment OS Integration
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
