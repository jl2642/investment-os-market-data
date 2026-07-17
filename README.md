# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Completed phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed phase: **FMDL-2 — A-share Factor & Screening Funnel**
  - **FMDL-2A — Factor Contract & Historical Source Benchmark**
  - **FMDL-2B — Historical Store & Basic Factor Engine**
    - **FMDL-2B-1 — Historical Store Architecture & Full-Market Pilot**
    - **FMDL-2B-2 — Full-Universe Sharded Initial Backfill**
    - **FMDL-2B-3 — Basic Factor Engine**
    - **FMDL-2B-4 — Incremental Update, Refresh & Final Acceptance**
  - **FMDL-2C — Screening Sleeves & Funnel**
  - **FMDL-2D — Replay, Stability & Final FMDL-2 Acceptance**
- Next production phase: **FMDL-3 — Financial & Valuation Data Hardening**
- Next engineering gate: **FMDL-3 Overall Architecture & Phased Plan → FMDL-3A Source Benchmark, Point-in-Time Contract & Coverage Map**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Latest stable A-share Current release

- Run ID: `FMDL1BC_20260717T174015+0800`
- As-of date: `2026-07-17`
- Universe rows: `5,528`
- Snapshot rows: `5,528`
- Hard quality failures: `0`
- Market-wide provider: `sina_public` explicit free fallback
- Status: `PUBLISHED_WITH_WARNINGS`
- Event flags: `7`
- Stable data path: `outputs/current/`
- Investment OS interface: `outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`

## Accepted historical, factor, screening and stability releases

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

### FMDL-2B-2 immutable full-market base

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
- Status: `ACCEPTED_WITH_CONTROLLED_FOUR_SYMBOL_QUARANTINE`
- Authority: immutable historical evidence; no factor rank, alpha claim or trade authority

### FMDL-2B-3 initial full-market factor candidate

- Run ID: `FMDL2B3_20260717T162732+0800`
- As-of date: `2026-07-16`
- Factor contract: `1.0.0`
- Factors: `26`
- Universe and wide rows: `5,529`
- Symbol-factor detail rows: `143,754`
- Valid / Partial / Suspect / Blocked: `5,361 / 164 / 0 / 4`
- Available factor values: `142,625` (`99.2146%`)
- Hard failures: `0`
- Status: `ACCEPTED_WITH_CONTROLLED_PARTIAL_AND_FOUR_SYMBOL_QUARANTINE`

### FMDL-2B-4 history Current

- Release: `FMDL2B4_20260717T174137+0800`
- As-of date: `2026-07-17`
- Composite history symbols: `5,525`
- Composite history rows: `2,499,921`
- Validated incremental rows: `5,518`
- Full-series repair symbols: `2`
- Full-series repair rows: `917`
- Suspended/no-append symbols: `4`
- Controlled quarantine: `4`
- Duplicate / future / impossible-OHLC rows: `0 / 0 / 0`
- Accepted current-session ratio: `99.945682%`
- Status: `PUBLISHED_WITH_WARNINGS`
- Stable path: `outputs/history/current/`

### FMDL-2B-4 factor Current

- Release: `FMDL2B4_FACTOR_20260717T174336+0800`
- As-of date: `2026-07-17`
- Factor contract: `1.0.0`
- Factors: `26`
- Universe and wide rows: `5,528`
- Symbol-factor detail rows: `143,728`
- Valid / Partial / Suspect / Blocked: `5,360 / 164 / 0 / 4`
- Available / missing factor values: `142,610 / 1,118`
- Hard failures: `0`
- Status: `PUBLISHED_WITH_WARNINGS`
- Stable path: `outputs/factors/current/`
- Authority: research priority only; no candidate-pool promotion or trade authority

### FMDL-2C screening Current

- Release: `FMDL2C_20260717T210036+0800`
- As-of date: `2026-07-17`
- Input factor Current: `FMDL2B4_FACTOR_20260717T174336+0800`
- Publication status: `PUBLISHED`
- Universe / named rows: `5,528 / 5,528`
- Core investable / watch eligible: `5,001 / 16`
- Review only / excluded: `139 / 372`
- Raw sleeve hits / distinct candidates: `150 / 134`
- Research Longlist: `100`
- Priority A / B / C: `20 / 40 / 40`
- Raw sleeve counts — defensive / trend / breakout / recovery: `40 / 40 / 40 / 30`
- Primary Longlist sleeves — defensive / trend / breakout / recovery: `30 / 29 / 22 / 19`
- Named Longlist rows: `100 / 100`
- Hard failures: `0`
- Quality and independent validation: `PASS / PASS`
- Cross-sleeve method: `70% within-sleeve rank percentile + 30% raw sleeve score + capped confirmation bonus`
- Stable path: `outputs/screens/current/`
- Authority: research-priority queue only; no factor-alpha claim, live candidate-pool promotion or trade authority

### FMDL-2D accepted stability candidate

- Run: `FMDL2D_20260717T215113+0800`
- Workflow: `29585053689` — success
- Candidate artifact: `8408829195`
- As-of date: `2026-07-17`
- Replay window: six sessions from `2026-07-10` through `2026-07-17`
- Same-date screening universe / sleeves / Longlist / funnel replay: `PASS / PASS / PASS / PASS`
- Historical factor anchor: `143,728 / 143,728` matching cells (`100%`)
- Minimum Longlist rows: `100`
- Average / minimum consecutive Longlist overlap: `76.6% / 72.0%`
- Average Top-20 overlap: `70.0%`
- Median common-name rank Spearman: `0.7553`
- Average primary-sleeve retention: `99.50%`
- Maximum board share / HHI: `38.0% / 0.2830`
- Current Priority-A structural-fragility share: `30.0%`
- Candidate status / independent validation: `PASS_WITH_CONTROLLED_LIMITATIONS / PASS`
- Hard failures / controlled warnings: `0 / 0`
- Candidate path: `outputs/stability/candidate/`
- Stable Current path after merge publication: `outputs/stability/current/`
- Authority: operational research stability only; no alpha claim, candidate-pool promotion or trade authority

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning, immutable and incremental history storage, factor computation, transparent screening, research-priority ranking, replay, stability controls and Current publication. It does not own final company research conclusions, investment recommendations, position sizing, portfolio migration or order execution. Those remain with Public Equity Investing, Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — source, universe, schedule, history, factor, refresh, screening, replay and quality rules.
2. `schemas/` — canonical dataset, history-row, manifest, release, interface and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` and `scripts/` — normalization, QA, history ingestion, incremental refresh, repair, factor computation, screening, replay, stability, LKG and quarantine logic.
5. `datasets/history/base/` — immutable accepted historical base.
6. `datasets/history/incremental/` — validated daily history deltas.
7. `datasets/history/repair/` — explicit full-series repair overrides.
8. `outputs/current/` — stable FMDL-1 Current market-data release.
9. `outputs/history/current/` — stable composite history Current.
10. `outputs/factors/current/` — stable basic-factor Current.
11. `outputs/screens/current/` — stable research-priority screening Current.
12. `outputs/stability/current/` — final FMDL-2 replay and stability acceptance.
13. `outputs/status/` — last run and last successful operating states.
14. `outputs/investment_os/` — machine-validated consumer pointer.
15. `outputs/benchmark/` — source and pilot evidence.
16. `.github/workflows/` — validation, scheduled production and controlled recovery automation.

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
- `docs/FMDL-2B3_BASIC_FACTOR_ENGINE.md`
- `docs/FMDL-2B3_ACCEPTANCE.md`
- `docs/FMDL-2B4_INCREMENTAL_REFRESH.md`
- `docs/FMDL-2B4_CURRENT_INTERFACES.md`
- `docs/FMDL-2B4_ACCEPTANCE.md`
- `docs/FMDL-2C_SCREENING_FUNNEL.md`
- `docs/FMDL-2C_ACCEPTANCE.md`
- `docs/FMDL-2D_REPLAY_STABILITY.md`
- `docs/FMDL-2D_ACCEPTANCE.md`
- `docs/FMDL-2D_ROADMAP_REVIEW.md`

## Core datasets and controls

- `a_share_universe`
- `daily_market_snapshot`
- `market_event_flags`
- `investment_os_market_data_interface`
- `a_share_daily_history`
- `fmdl2_history_store`
- `fmdl2_incremental_history`
- `fmdl2_full_series_repairs`
- `fmdl2_history_current`
- `fmdl2_basic_factor_table`
- `fmdl2_basic_factor_detail`
- `fmdl2_basic_factor_status`
- `fmdl2_factor_current`
- `fmdl2_screening_universe`
- `fmdl2_screening_sleeve_detail`
- `fmdl2_screening_longlist`
- `fmdl2_screening_funnel`
- `fmdl2_screening_current`
- `fmdl2_replay_longlists`
- `fmdl2_rank_transitions`
- `fmdl2_sleeve_transitions`
- `fmdl2_structural_fragility_review`
- `fmdl2_final_release`
- `fmdl2b4_last_run`
- `fmdl2b4_last_success`
- `fmdl2c_last_success`
- `fmdl2d_last_success`

Every published dataset carries a schema version, source timestamp, generation timestamp, QA state, row count, hash and Last-known-good lineage. Failed history, factor, screening or stability candidates cannot replace Current. Missing history or factor inputs remain missing and never become neutral scores or zeros. Screening output is a research-priority queue and never creates trade permission.

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP ✅
  - FMDL-1A-R Production Architecture & Contract Completion ✅
  - FMDL-1B/C A-share Universe Builder + Daily Market Snapshot ✅
  - FMDL-1D/E Data Quality Hardening + Scheduled Automation ✅
  - FMDL-1F Investment OS Interface + Final Acceptance ✅
- FMDL-2 A-share Factor & Screening Funnel ✅
  - FMDL-2A Factor Contract & Historical Source Benchmark ✅
  - FMDL-2B Historical Store & Basic Factor Engine ✅
    - FMDL-2B-1 Historical Store Architecture & Full-Market Pilot ✅
    - FMDL-2B-2 Full-Universe Sharded Initial Backfill ✅
    - FMDL-2B-3 Basic Factor Engine ✅
    - FMDL-2B-4 Incremental Update, Refresh & Final Acceptance ✅
  - FMDL-2C Screening Sleeves & Funnel ✅
  - FMDL-2D Replay, Stability & Final FMDL-2 Acceptance ✅
- FMDL-3 Financial & Valuation Data Hardening ⏭️
  - FMDL-3 Overall Architecture & Phased Plan
  - FMDL-3A Source Benchmark, Point-in-Time Contract & Coverage Map
  - FMDL-3B Financial Statement Store & Normalization
  - FMDL-3C Financial Quality, Growth & Balance-Sheet Factors
  - FMDL-3D Valuation, Capitalization, Dividend & Shareholder-Return Layer
  - FMDL-3E Incremental Refresh, Replay & Final Acceptance
- FMDL-4 Public Equity Investing + Investment OS Integration
  - FMDL-4A Research Handoff Contract
  - FMDL-4B Candidate Research & Graduation
  - FMDL-4C Investment OS Re-entry & Decision-Gate Integration
  - FMDL-4D Closed-Loop Attribution & Thesis Tracking
- FMDL-5 Hong Kong Stock Connect Adapter
- FMDL-6 US Equity Research Benchmark Pool
- FMDL-7 Operating Acceptance
