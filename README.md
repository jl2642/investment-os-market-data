# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Completed phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed phase: **FMDL-2 — A-share Factor & Screening Funnel**
- Active phase: **FMDL-3 — Financial & Valuation Data Hardening**
- Completed engineering gate: **FMDL-3 Overall Architecture & Phased Plan**
- Next execution phase: **FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Latest stable A-share market-data Current

- Run ID: `FMDL1BC_20260717T174015+0800`
- As-of date: `2026-07-17`
- Universe / snapshot rows: `5,528 / 5,528`
- Hard quality failures: `0`
- Market-wide provider: `sina_public` explicit free fallback
- Status: `PUBLISHED_WITH_WARNINGS`
- Event flags: `7`
- Stable path: `outputs/current/`
- Investment OS interface: `outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`

## Accepted FMDL-2 releases

### Historical source route

- Primary: `sina_daily / AKShare stock_zh_a_daily`, QFQ
- Primary benchmark: `119/120` successful (`99.17%`)
- Restricted fallback: `tencent_hist / stock_zh_a_hist_tx`, SH/SZ Main price-and-amount only
- Degraded on GitHub runner: `eastmoney_hist / stock_zh_a_hist`

### Immutable full-market historical base

- Release: `FMDL2B2_29556547410_1`
- As-of date: `2026-07-16`
- Universe attempted / usable series: `5,529 / 5,525`
- History rows: `2,494,405`
- Parquet store: `131.6084 MiB` across `24` logical shards
- Controlled quarantine: `4`
- Duplicate / future / impossible-OHLC rows: `0 / 0 / 0`
- Status: `ACCEPTED_WITH_CONTROLLED_FOUR_SYMBOL_QUARANTINE`

### History Current

- Release: `FMDL2B4_20260717T174137+0800`
- As-of date: `2026-07-17`
- Composite symbols / rows: `5,525 / 2,499,921`
- Validated incremental rows: `5,518`
- Full-series repairs: `2` symbols / `917` rows
- Suspended or no-append symbols: `4`
- Accepted current-session ratio: `99.945682%`
- Stable path: `outputs/history/current/`

### Factor Current

- Release: `FMDL2B4_FACTOR_20260717T174336+0800`
- As-of date: `2026-07-17`
- Factor contract: `1.0.0`
- Factors: `26`
- Universe and wide rows: `5,528`
- Symbol-factor detail rows: `143,728`
- Valid / Partial / Suspect / Blocked: `5,360 / 164 / 0 / 4`
- Available / missing factor values: `142,610 / 1,118`
- Hard failures: `0`
- Stable path: `outputs/factors/current/`
- Authority: research priority only; no candidate-pool promotion or trade authority

### Screening Current

- Release: `FMDL2C_20260717T210036+0800`
- As-of date: `2026-07-17`
- Universe / named rows: `5,528 / 5,528`
- Core investable / watch eligible / review only / excluded: `5,001 / 16 / 139 / 372`
- Raw sleeve hits / distinct candidates: `150 / 134`
- Research Longlist: `100`
- Priority A / B / C: `20 / 40 / 40`
- Primary Longlist sleeves — defensive / trend / breakout / recovery: `30 / 29 / 22 / 19`
- Quality and independent validation: `PASS / PASS`
- Stability status: `ACCEPTED_FMDL2D_OPERATIONAL_STABILITY`
- Stable path: `outputs/screens/current/`
- Authority: research-priority queue only; no alpha claim, live candidate-pool promotion or trade authority

### FMDL-2 Final Current

- Final release: `FMDL2D_20260717T220406+0800`
- Published at: `2026-07-17T22:04:09+08:00`
- Status: `FMDL2_FINAL_ACCEPTED_WITH_CONTROLLED_LIMITATIONS`
- Replay window: six sessions from `2026-07-10` through `2026-07-17`
- Same-date screening universe / sleeves / Longlist / funnel replay: `PASS / PASS / PASS / PASS`
- Historical factor anchor: `143,728 / 143,728` matching cells (`100%`)
- Average / minimum consecutive Longlist overlap: `76.6% / 72.0%`
- Average Top-20 overlap: `70.0%`
- Median common-name rank Spearman: `0.7553`
- Average primary-sleeve retention: `99.50%`
- Maximum board share / HHI: `38.0% / 0.2830`
- Current Priority-A structural-fragility share: `30.0%`
- Independent validation: `PASS`
- Stable path: `outputs/stability/current/`
- Authority: operational research stability only; no alpha claim, candidate-pool promotion or trade authority

## FMDL-3 accepted architecture Current

- Architecture release: `FMDL3_ARCH_20260717T223136+0800`
- Published at: `2026-07-17T22:31:36+08:00`
- Status: `FMDL3_ARCHITECTURE_ACCEPTED`
- Architecture state: `FROZEN_FOR_FMDL3A_EXECUTION`
- Initial accepted workflow: `29588007161` — success
- Accepted Head revalidation: `29588217734` — success
- Candidate artifact: `8409825884`
- Artifact digest: `sha256:a3d92f538d3f16738ca099c85447b98211a5d2306165eac86d51cc49890b3f39`
- Main validation run: `FMDL3_ARCH_20260717T223135+0800`
- Machine checks: `14 / 14 PASS`
- Hard failures: `0`
- Stable path: `outputs/architecture/current/`
- Last-success pointer: `outputs/status/FMDL3_ARCHITECTURE_LAST_SUCCESS.json`
- Contract: `config/fmdl3_program_contract.json`
- Architecture: `docs/FMDL-3_ARCHITECTURE.md`
- Point-in-time policy: `docs/FMDL-3_POINT_IN_TIME_POLICY.md`
- Phased plan: `docs/FMDL-3_PHASED_PLAN.md`
- Acceptance: `docs/FMDL-3_ARCHITECTURE_ACCEPTANCE.md`
- Authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`
- Trade authority: `NONE`
- Next phase: `FMDL-3A`

The architecture acceptance does not claim that financial sources have been selected or that financial, factor or valuation Current datasets already exist. Those require real execution in FMDL-3A through FMDL-3E.

## FMDL-3 frozen architecture

### Point-in-time and revision control

FMDL-3 separates report period, announcement date, announcement timestamp, market availability, retrieval time and revision-effective interval. Restatements create new versions and never overwrite historical values silently.

### Required sector profiles

- `GENERAL_NON_FINANCIAL`
- `BANK`
- `INSURANCE`
- `SECURITIES_AND_BROKERAGE`
- `PRE_PROFIT_OR_NEGATIVE_EARNINGS`

### Canonical datasets

- `fmdl3_source_index`
- `fmdl3_financial_fact_raw`
- `fmdl3_financial_statement_normalized_long`
- `fmdl3_comparability_bridge`
- `fmdl3_financial_factor_detail`
- `fmdl3_valuation_snapshot`
- `fmdl3_shareholder_return_event`
- `fmdl3_final_release`

### Zero-tolerance gates

- zero point-in-time leakage;
- zero silent restatement overwrite;
- zero invalid ratio denominator published as valid;
- zero neutral fill for missing financial data;
- zero decision-grade rows without source lineage;
- zero failed or quarantined release replacing Current;
- zero trade authority.

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning, historical storage, factor computation, screening, replay, point-in-time financial evidence, financial factors, valuation data and Current publication. It does not own final company research conclusions, investment recommendations, target prices, position sizing, portfolio migration or order execution. Those remain with Public Equity Investing, Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — source, universe, history, factor, screening, financial, valuation, availability and quality contracts.
2. `schemas/` — canonical dataset, manifest, release, financial-fact, factor and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` and `scripts/` — normalization, QA, refresh, repair, factor, screening, PIT replay, LKG and quarantine logic.
5. `datasets/history/` — immutable, incremental and repair market-history layers.
6. `outputs/current/` — stable FMDL-1 market-data Current.
7. `outputs/history/current/` — composite history Current.
8. `outputs/factors/current/` — market-behaviour factor Current.
9. `outputs/screens/current/` — research-priority screening Current.
10. `outputs/stability/current/` — final FMDL-2 replay and stability acceptance.
11. `outputs/architecture/current/` — accepted FMDL-3 architecture Current.
12. `outputs/financials/`, `outputs/financial_factors/`, `outputs/valuation/`, `outputs/shareholder_returns/` — planned FMDL-3 data families.
13. `outputs/fmdl3/current/` — planned FMDL-3 Final Current.
14. `outputs/status/` — last-run and last-success operating states.
15. `outputs/investment_os/` — machine-validated consumer pointers.
16. `.github/workflows/` — validation, scheduled production and controlled recovery automation.

## Canonical documents

- `docs/DATA_CONTRACT.md`
- `docs/SOURCE_REGISTRY.md`
- `docs/QUALITY_GATES.md`
- `docs/UPDATE_CADENCE.md`
- `docs/INVESTMENT_OS_INTERFACE.md`
- `docs/FMDL-1A_ARCHITECTURE.md`
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
- `docs/FMDL-3_ARCHITECTURE.md`
- `docs/FMDL-3_POINT_IN_TIME_POLICY.md`
- `docs/FMDL-3_PHASED_PLAN.md`
- `docs/FMDL-3_ARCHITECTURE_ACCEPTANCE.md`

## FMDL roadmap

- FMDL-0 Public Equity Investing Integration ✅
- FMDL-1 A-share Full-Market Data MVP ✅
- FMDL-2 A-share Factor & Screening Funnel ✅
  - FMDL-2A Factor Contract & Historical Source Benchmark ✅
  - FMDL-2B Historical Store & Basic Factor Engine ✅
  - FMDL-2C Screening Sleeves & Funnel ✅
  - FMDL-2D Replay, Stability & Final Acceptance ✅
- FMDL-3 Financial & Valuation Data Hardening 🚧
  - FMDL-3 Overall Architecture & Phased Plan ✅
  - FMDL-3A Source Benchmark, Point-in-Time Contract & Coverage Map ⏭️
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
