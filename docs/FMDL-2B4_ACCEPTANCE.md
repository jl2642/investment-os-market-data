# FMDL-2B-4 Acceptance — Incremental Update, Refresh & Final FMDL-2B Acceptance

## Acceptance state

`ACCEPTED_WITH_CONTROLLED_FOUR_SYMBOL_QUARANTINE_AND_TWO_FULL_SERIES_REPAIRS`

FMDL-2B-4 has passed real next-session operation, independent history/factor validation, same-date replay and main-branch Current publication on GitHub-hosted runners. FMDL-2B is formally complete.

The phase remains market-data and research-evidence infrastructure only. It creates no screening sleeve, Longlist, factor-alpha claim, portfolio change or trade authority.

## Canonical main-branch publication

- Merge commit: `89d26d0a17ac0b997300665a2ab950a3b441f48b`
- FMDL-1 Current: `FMDL1BC_20260717T174015+0800`
- History Current: `FMDL2B4_20260717T174137+0800`
- Factor Current: `FMDL2B4_FACTOR_20260717T174336+0800`
- As-of date: `2026-07-17`
- History publication: `PUBLISHED_WITH_WARNINGS`
- Factor publication: `PUBLISHED_WITH_WARNINGS`
- Investment OS interface: `ACTIVE`, bound to the same FMDL-1 Current
- Trade authority: `NONE`

Canonical paths:

- `outputs/current/`
- `outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`
- `outputs/history/current/`
- `outputs/factors/current/`
- `outputs/status/FMDL2B4_LAST_SUCCESS.json`

## Real operating evidence

### Full operation

- GitHub Actions workflow run: `29570328833` — `SUCCESS`
- Operating artifact: `8402901468`
- Artifact digest: `sha256:3fd11084d8b60f74ffe607c0b79ae7373025bca0754abd709fe6a7d028ee59cd`
- Evidence history release: `FMDL2B4_20260717T173535+0800`
- Evidence factor release: `FMDL2B4_FACTOR_20260717T173703+0800`
- As-of date: `2026-07-17`
- Independent candidate validation: `PASS`

### Same-date replay

- GitHub Actions workflow run: `29571792315` — `SUCCESS`
- Replay artifact: `8403451997`
- Artifact digest: `sha256:8935b1f87da9397a1a31025310285aa18a42e90edc43682f6b073662c5e61a0d`
- Second operation state: `NO_OP_ALREADY_CURRENT`
- History Current release-file hash: unchanged
- Factor Current release-file hash: unchanged
- History and factor LKG identities: preserved

## FMDL-1 Current transition

The accepted A-share Current moved from:

- `2026-07-16`, `5,529` Universe symbols;

to:

- `2026-07-17`, `5,528` Universe symbols.

The one-symbol Universe reduction is retained as the accepted current-universe result. B4 does not silently force the prior 5,529-symbol identity onto a newer Current release.

## History Current result

| Metric | Result |
|---|---:|
| Current Universe symbols | 5,528 |
| Composite history symbols | 5,525 |
| Composite history rows | 2,499,921 |
| Validated incremental rows | 5,518 |
| Full-series repair symbols | 2 |
| Full-series repair rows | 917 |
| Suspended/no-append symbols | 4 |
| Unresolved quarantines | 4 |
| Accepted current-session ratio | 99.945682% |
| Duplicate symbol-date rows | 0 |
| Future rows | 0 |
| Impossible-OHLC rows | 0 |
| Delta files | 1 |
| Repair files | 1 |
| Hard failures | 0 |

The composite store is resolved as:

`immutable FMDL-2B-2 base + validated daily delta + explicit full-series repair overrides`.

The accepted FMDL-2B-2 base remains immutable.

## Two full-series repairs

The `2026-07-17` snapshot contained impossible current-session OHLC observations for:

- `688237.SH`
- `688277.SH`

The engine did not append those rows, fill zero prices, copy the close into open/high/low or relax the OHLC gate. Both symbols were routed to the accepted Sina full-history source and successfully rebuilt as controlled full-series repairs.

The repair series were independently revalidated before entering the composite Current.

## Four continuing quarantines

The inherited controlled quarantines remain:

- `688089.SH`
- `688143.SH`
- `688173.SH`
- `689009.SH`

No repair was fabricated. The three persistent impossible-OHLC histories and the one unavailable-provider history remain excluded from factor-ready history and retain explicit blocked/missing states.

## Factor Current result

| Metric | Result |
|---|---:|
| Current Universe / wide rows | 5,528 |
| Symbol-factor detail rows | 143,728 |
| Factor count | 26 |
| Valid symbols | 5,360 |
| Partial symbols | 164 |
| Suspect symbols | 0 |
| Blocked symbols | 4 |
| Available factor values | 142,610 |
| Missing factor values | 1,118 |
| Hard failures | 0 |

The factor refresh reuses the accepted FMDL-2B-3 formulas, minimum-observation rules, QFQ price basis, liquidity capability controls, direction-aware percentiles and missingness policy.

No unavailable factor receives zero, a neutral percentile or a neutral z-score.

## Operating controls accepted

The following controls passed:

1. latest-completed-session freshness gate;
2. one-session full-market incremental append;
3. explicit snapshot-to-QFQ continuity validation;
4. impossible current-session OHLC routing to full-series repair;
5. inherited-quarantine retry without fabricated repair;
6. deterministic repair > delta > base composite precedence;
7. component, row and aggregate hash validation;
8. zero duplicate, future and impossible-OHLC promoted rows;
9. full-market 26-factor recalculation at the same history as-of date;
10. independent history/factor candidate validation;
11. atomic history Current and factor Current publication;
12. failed-candidate dual-LKG preservation;
13. same-date deterministic no-op replay;
14. automatic Investment OS interface rebinding after FMDL-1 Current changes;
15. free-tier targeted-repair and delta-compaction controls.

## Runtime defects found and closed

Real acceptance identified and closed three implementation/system defects:

1. indexed snapshot rows initially lost the canonical symbol field;
2. two impossible current-session OHLC rows initially reached the fast-append candidate before being routed to repair;
3. the FMDL-1 daily Current could advance while the Investment OS consumer interface remained bound to the prior release.

All three now have explicit implementation controls. The daily FMDL-1 workflow automatically rebuilds and validates the consumer interface after Current publication.

## Workflow hygiene

- FMDL-1 daily production is schedule/manual only;
- ordinary code pushes no longer launch a competing daily production run;
- B4 pull requests run deterministic validation only;
- B4 main-branch implementation merge performs controlled production publication;
- ongoing B4 operation runs after the normal FMDL-1 daily window;
- superseded B4 runs are cancelled;
- failed B4 runs preserve both history and factor LKG releases.

## Controlled limitations and non-claims

1. The current history is not a survivorship-free point-in-time Universe backtest.
2. Free-source QFQ and provider continuity remain controlled operating risks.
3. A multi-session gap remains fail-closed and requires a manual full rebase.
4. Factor stability and economic alpha remain FMDL-2D work.
5. Financial, valuation, market-cap, dividend and analyst factors remain FMDL-3 work.
6. B4 does not construct screening sleeves or a Longlist.
7. No candidate pool, simulation account, real account or trade state changed.

## Final FMDL-2B judgment

FMDL-2B is complete:

- FMDL-2B-1 proved the historical-store architecture;
- FMDL-2B-2 built the accepted immutable full-market base;
- FMDL-2B-3 built and validated the 26-factor full-market engine;
- FMDL-2B-4 made both layers incrementally maintainable, fail-closed and Last-known-good controlled.

## Authorized next phase

`FMDL-2C — Screening Sleeves & Funnel`

FMDL-2C may design investability gates, factor sleeves, sleeve-specific ranking and the full-market screening funnel. It must consume only the published history/factor Current interfaces and must retain the research-only/no-trade authority boundary.
