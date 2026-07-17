# FMDL-2D Acceptance — Replay, Stability & Final FMDL-2 Gate

## Acceptance state

`ACCEPTED_PENDING_MAIN_FMDL2_FINAL_PUBLICATION`

FMDL-2D has passed deterministic regression tests, a real six-session full-market factor-and-screen replay, all frozen stability hard gates and independent candidate validation on GitHub-hosted runners. Merge and main-branch final publication are authorized.

The accepted state is operational stability evidence with controlled limitations. It is not a factor-alpha claim, long-horizon backtest, investment recommendation, live Investment OS candidate-pool promotion, portfolio instruction or trade permission.

## Accepted run

- Workflow run: `29585053689` — `SUCCESS`
- Candidate artifact: `8408829195`
- Artifact digest: `sha256:f0b68610a2d5ad99b7b7d4d37995b48ba56b231cef81db0c1dd3f7a35b1034ab`
- FMDL-2D run: `FMDL2D_20260717T215113+0800`
- As-of date: `2026-07-17`
- Replay dates: `2026-07-10`, `2026-07-13`, `2026-07-14`, `2026-07-15`, `2026-07-16`, `2026-07-17`
- Screening Current: `FMDL2C_20260717T210036+0800`
- Factor Current: `FMDL2B4_FACTOR_20260717T174336+0800`
- History Current: `FMDL2B4_20260717T174137+0800`
- Candidate status: `PASS_WITH_CONTROLLED_LIMITATIONS`
- Independent validation: `PASS`
- Hard failures: `0`
- Controlled warnings: `0`

## Same-date deterministic replay

All four accepted screening artifacts were rebuilt from the exact accepted Factor Current and matched Current:

| Artifact | Result |
|---|---|
| Screening universe | `PASS` |
| Sleeve detail | `PASS` |
| Research Longlist | `PASS` |
| Funnel | `PASS` |

The Longlist replay uses ordered `(overall_rank, symbol, longlist_row_hash)` identity. This preserves the accepted canonical row content while avoiding false mismatches caused only by CSV floating-point round-trip representation.

## Six-session operational stability

| Metric | Accepted result | Hard floor/cap |
|---|---:|---:|
| Replay sessions | `6` | `6` minimum |
| Minimum Longlist rows | `100` | `80` minimum |
| Average consecutive Longlist overlap | `76.6%` | `50%` minimum |
| Minimum single-transition Longlist overlap | `72.0%` | `35%` minimum |
| Average Top-20 overlap | `70.0%` | `25%` minimum |
| Median common-name rank Spearman | `0.7553` | `0.15` minimum |
| Average median absolute rank change | `8.5` places | diagnostic |
| Average primary-sleeve retention | `99.50%` | `35%` minimum |
| Average priority-bucket retention | `69.15%` | diagnostic |
| Maximum board share | `38.0%` | `65%` maximum |
| Maximum board HHI | `0.2830` | `0.50` maximum |
| Minimum industry identity coverage | `54.0%` | target `50%` |
| Maximum structural-fragility share | `50.0%` | target `60%` |
| Current Priority-A fragility share | `30.0%` | `35%` maximum |

Every replay date produced a complete 100-name Longlist with the frozen `20 / 40 / 40` Priority-A/B/C structure.

## Transition detail

| Transition | Longlist overlap | Top-20 overlap | Rank Spearman | Primary-sleeve retention |
|---|---:|---:|---:|---:|
| Jul 10 → Jul 13 | `80%` | `65%` | `0.6899` | `98.75%` |
| Jul 13 → Jul 14 | `79%` | `65%` | `0.8325` | `98.73%` |
| Jul 14 → Jul 15 | `75%` | `70%` | `0.7950` | `100%` |
| Jul 15 → Jul 16 | `77%` | `80%` | `0.7553` | `100%` |
| Jul 16 → Jul 17 | `72%` | `70%` | `0.7040` | `100%` |

The final-day turnover was the highest in the window at `28` entrants and `28` exits, but remained above every hard stability floor and preserved all primary sleeve identities for common names.

## Sleeve stability

Average sleeve Jaccard by archetype:

- `DEFENSIVE_STABILITY`: `0.8790`
- `RECOVERY_WATCH`: `0.5990`
- `LIQUID_BREAKOUT`: `0.5817`
- `TREND_PERSISTENCE`: `0.5405`

This is economically coherent: the defensive sleeve is the most persistent, while trend, breakout and recovery sleeves react more to daily price and participation changes. None breached the aggregate Longlist or primary-sleeve hard gates.

## Historical factor anchor

The replayed `2026-07-16` raw factor table was compared with the accepted FMDL-2B-3 factor candidate:

- common symbols: `5,528`
- factor cells compared: `143,728`
- matching cells: `143,728`
- mismatching cells: `0`
- match ratio: `100%`

This confirms that the historical date truncation and factor engine reproduce the previously accepted factor evidence exactly for the common fixed cohort.

## Structural false-positive risk review

FMDL-2D does not claim a realized false-positive rate because no future-return evaluation is performed. It produces an ex-ante rejection-testing queue instead.

For the current 100-name Longlist:

- structural-fragility flags: `46` names;
- Priority A: `6 / 20` flagged;
- Priority B: `14 / 40` flagged;
- Priority C: `26 / 40` flagged.

The most common flags were:

- single-sleeve dependence: `86`;
- negative 20-session return: `27`;
- bottom-quartile Longlist rank: `25`;
- large 120-session drawdown: `9`;
- non-VALID factor record: `2`;
- liquidity near the absolute floor: `1`.

The concentration of fragility in Priority C is expected. Priority-A flagged names remain research candidates but require early rejection tests rather than automatic advancement.

## Controlled limitations

1. Replay uses the fixed current Universe cohort and is not point-in-time survivorship-free.
2. The six-session window tests operational stability, not long-horizon returns or alpha.
3. Historical ST and security-master identity may not be fully point-in-time.
4. Industry identity coverage is incomplete and is not used to impose hard quotas.
5. No future-return or realized false-positive test is performed.
6. Financial quality, valuation, capitalization, dividends and estimates remain FMDL-3.
7. No Longlist name is promoted into the live Investment OS candidate pool.
8. No simulation or real holding changed.

## Final FMDL-2 conclusion

FMDL-2 has completed its intended market-behaviour scope:

- accepted historical daily store;
- incremental refresh and repair architecture;
- 26-factor Current;
- investability routing;
- four screening sleeves;
- 100-name research-priority Longlist;
- deterministic replay;
- short-window operational stability and concentration controls;
- structural rejection-testing queue;
- no trade authority.

Main publication will create `outputs/stability/current/FMDL2_FINAL_RELEASE.json`, update the Screening Current stability pointer and authorize entry into FMDL-3 planning.

## Authorized next phase

`FMDL-3 — Financial & Valuation Data Hardening`

FMDL-3 must begin with an overall architecture and phased execution plan, followed by `FMDL-3A — Source Benchmark, Point-in-Time Contract & Coverage Map`.
