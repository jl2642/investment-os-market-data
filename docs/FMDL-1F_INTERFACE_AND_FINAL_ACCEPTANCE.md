# FMDL-1F — Investment OS Interface + Final FMDL-1 Acceptance

## 1. Acceptance state

`ACCEPTED_PENDING_CANONICAL_PACKAGE_BINDING`

FMDL-1F closes the gap between the free A-share data repository and 股票投资助手 / Investment OS. The data repository already owns acquisition, normalization, quality gates, Last-known-good publication and daily operation. This phase defines the exact consumer bundle and validates that Investment OS and Public Equity Investing can read it without acquiring trade authority.

## 2. Canonical consumer pointer

`outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`

The pointer binds consumers to the stable `outputs/current/` release by:

- repository and branch;
- run ID and as-of date;
- publication and QA status;
- provider and controlled warnings;
- exact dataset paths, hashes and row counts;
- freshness rules;
- blocking conditions;
- downstream routing and authority boundary.

The interface does not duplicate the large CSV files. It validates and points to the accepted Current release.

## 3. Consumption order

1. Validate the interface against `schemas/investment_os_market_data_interface.schema.json`.
2. Read `outputs/current/CURRENT_RELEASE.json`.
3. Confirm published status and zero hard failures.
4. Recompute dataset hashes and row counts.
5. Confirm manifests, quality reports, run ID and as-of date align.
6. Apply freshness policies before any full-market screen.
7. Surface soft warnings and market-event flags.
8. FMDL-2 calculates factors and produces a ranked research screen.
9. Public Equity Investing `idea-generation` performs professional research triage.
10. Research evidence re-enters Investment OS at RESEARCH/SCORE and proceeds through hard Gates, portfolio fit, capital migration, pre-trade memo and user confirmation.

## 4. Authority boundary

The market-data repository supplies evidence only. Public Equity Investing supplies research orchestration only. Neither can:

- create BUY/ADD/SELL permission;
- promote a candidate without Investment OS review;
- change real or simulation holdings;
- bypass hard Gates or portfolio fit;
- execute a brokerage order.

All real transactions continue to require explicit user confirmation.

## 5. Current accepted interface

- Current run: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Universe rows: `5,529`
- Snapshot rows: `5,529`
- Event flags: `7`
- Hard quality failures: `0`
- Publication: `PUBLISHED_WITH_WARNINGS`
- Provider: `sina_public`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`

Controlled warnings remain visible:

- incomplete industry coverage;
- no bulk market-cap fields from the active free fallback;
- no bulk valuation fields from the active free fallback;
- one extreme-return event requiring review.

These warnings restrict factor availability but do not invalidate security identity, market coverage, daily price, volume, turnover or suspension status.

## 6. FMDL-0 + FMDL-1 program acceptance

### FMDL-0

`PASS — PUBLIC_EQUITY_INVESTING_ENABLED_RESEARCH_ONLY`

Public Equity Investing is formally integrated as the listed-equity research workflow layer. A 14-route workflow map and structured research handoff exist. Investment OS retains all Gate, portfolio and execution authority.

### FMDL-1

`PASS_WITH_CONTROLLED_WARNINGS_AND_OPERATING_OBSERVATION`

The system now has a free A-share full-market data MVP with:

- 5,529-security market universe;
- daily market snapshot;
- explicit free-source fallback;
- normalized schemas and manifests;
- hard and soft quality gates;
- event flags;
- Last-known-good and quarantine protection;
- weekday scheduled GitHub Actions;
- stable Current release;
- machine-validated Investment OS consumer interface.

The first naturally scheduled main-branch update remains an operating observation item. It is not a development blocker because the complete production path has run successfully on GitHub-hosted runners and the stable Current release is already published.

## 7. Phase boundary

FMDL-1 does not yet rank stocks or build a candidate funnel. That belongs to FMDL-2. FMDL-3 later hardens financial, market-cap and valuation fields. FMDL-4 binds ranked research outputs to the live Investment OS candidate and portfolio workflow.

## 8. Next authorized phase

`FMDL-2 — A-share Factor & Screening Funnel`
