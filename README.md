# Investment OS Market Data

Free, auditable market-data layer for the 股票投资助手 / Investment OS.

## Current status

- Program: Full-Market Data Layer (FMDL)
- Completed prerequisite: **FMDL-0 — Public Equity Investing Integration**
- Completed phase: **FMDL-1 — A-share Full-Market Data MVP**
- Completed phase: **FMDL-2 — A-share Factor & Screening Funnel**
- Completed phase: **FMDL-3 — Financial & Valuation Data Hardening**
- Completed phase: **FMDL-4 — Public Equity Investing & Investment OS Integration**
- Completed Hong Kong gates: **FMDL-5-0 / 5A / 5B / 5C / 5D**
- Active phase: **FMDL-5E-R1 — Hong Kong Factor & Screening Adapter targeted repair**
- Next gated phase after formal publication: **FMDL-5F — Public Equity Research Adapter**
- Cost policy: **free and free-tier resources only**
- Execution model: GitHub Actions + open-source/public data adapters
- Trading model: research and decision support only; no broker connection and no automatic order execution

## Active Hong Kong lineage

- FMDL-5C market store: `FMDL5C_20260721_52f17b755436`
- FMDL-5D disclosure and financial store: `FMDL5D_20260721_0aee5654502c`
- FMDL-5E-R1 objective: corrected auditable issuer profiles plus a 100-name formal-sleeve-only Hong Kong research Longlist
- Candidate, simulation, real-account and order mutation: `0`
- Trade authority: `NONE`

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

## System boundary

This repository owns market-data acquisition, normalization, quality control, versioning, historical storage, factor computation, screening, replay, point-in-time financial evidence, financial factors, valuation data and Current publication. It does not own final company research conclusions, investment recommendations, target prices, position sizing, portfolio migration or order execution. Those remain with Public Equity Investing, Investment OS and the user-confirmation gate.

## Canonical architecture

1. `config/` — source, universe, history, factor, screening, financial, valuation, availability and quality contracts.
2. `schemas/` — canonical dataset, manifest, release, financial-fact, factor and operating-state schemas.
3. `ingestion/` — source adapters and explicit provider fallbacks.
4. `pipeline/` and `scripts/` — normalization, QA, refresh, repair, factor, screening, PIT replay, LKG and quarantine logic.
5. `datasets/` — immutable release families.
6. `outputs/` — Current, candidate, archive, status and Investment OS interfaces.
7. `.github/workflows/` — validation, scheduled production and controlled recovery automation.

For detailed phase contracts and acceptance evidence, use the files under `docs/`, `config/`, `outputs/status/` and each release family rather than relying on this summary alone.
