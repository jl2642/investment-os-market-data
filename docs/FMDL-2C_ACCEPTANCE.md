# FMDL-2C Acceptance — Screening Sleeves & Research-Priority Funnel

## Acceptance state

`ACCEPTED_WITH_RESEARCH_ONLY_LONGLIST_AND_FMDL2D_STABILITY_PENDING`

FMDL-2C has passed a real 5,528-security full-market build, deterministic regression tests, independent candidate validation and main-branch Screening Current publication on GitHub-hosted runners. FMDL-2C is formally complete.

The output is a research-priority queue only. It is not a factor-alpha claim, investment recommendation, live Investment OS candidate-pool promotion, portfolio instruction or trade permission.

## Canonical main-branch publication

- Merge commit: `2fb51b358c820706de795e09e8c1b66f46a25840`
- Screening Current: `FMDL2C_20260717T210036+0800`
- As-of date: `2026-07-17`
- Publication status: `PUBLISHED`
- Input factor Current: `FMDL2B4_FACTOR_20260717T174336+0800`
- Quality / independent validation: `PASS / PASS`
- Hard failures: `0`
- Stability status: `PENDING_FMDL2D_REPLAY_AND_ECONOMIC_STABILITY`
- Authority: `RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY`
- Trade authority: `NONE`

Canonical paths:

- `outputs/screens/current/`
- `outputs/screens/current/SCREENING_CURRENT_RELEASE.json`
- `outputs/status/FMDL2C_LAST_SUCCESS.json`

## Accepted real run

- Workflow run: `29581863050` — `SUCCESS`
- Candidate artifact: `8407344370`
- Artifact digest: `sha256:57bf203865150d6dc546385d8a1631c56ca06dfddad49d723b9be559449bf3f7`
- Acceptance screening run: `FMDL2C_20260717T205335+0800`
- As-of date: `2026-07-17`
- Input factor Current: `FMDL2B4_FACTOR_20260717T174336+0800`
- Screening contract: `1.0.0`
- Candidate quality: `PASS`
- Independent validation: `PASS`
- Hard failures: `0`

## Funnel result

| Stage | Count | Universe ratio |
|---|---:|---:|
| A-share Current Universe | 5,528 | 100.0000% |
| Factor-data ready | 5,524 | 99.9276% |
| Core investable | 5,001 | 90.4667% |
| Watch eligible | 16 | 0.2894% |
| Raw sleeve hits | 150 | 2.7135% |
| Distinct sleeve candidates | 134 | 2.4240% |
| Research Longlist | 100 | 1.8090% |

Additional routing:

- Review only: `139`
- Excluded: `372`
- Priority A — immediate research: `20`
- Priority B — watch or trigger: `40`
- Priority C — screen flag only: `40`

## Accepted sleeves

| Sleeve | Raw hits | Primary Longlist names | Longlist membership |
|---|---:|---:|---:|
| `DEFENSIVE_STABILITY` | 40 | 30 | 30 |
| `TREND_PERSISTENCE` | 40 | 29 | 30 |
| `LIQUID_BREAKOUT` | 40 | 22 | 33 |
| `RECOVERY_WATCH` | 30 | 19 | 22 |

All four archetypes have independent Longlist representation. The Priority-A group also contains all four primary sleeves:

- Defensive stability: `6`
- Trend persistence: `6`
- Liquid breakout: `5`
- Recovery watch: `3`

## Cross-sleeve comparability

Different sleeves have different factor mixes and raw-score distributions. Direct comparison of their raw weighted scores caused defensive candidates to crowd out standalone recovery candidates during the first acceptance run.

The accepted final ordering therefore uses:

`70% within-sleeve rank percentile + 30% raw sleeve score + capped cross-sleeve confirmation bonus`.

This preserves within-archetype strength while making different research pathways comparable without forcing artificial equal quotas.

## Investability and identity controls

The accepted Current contains:

- named security-master identity for all `5,528` screening rows;
- named identity for all `150` sleeve rows;
- named identity for all `100` Longlist rows;
- zero duplicate Longlist symbols;
- zero duplicate symbol-sleeve rows;
- zero `SUSPECT` or `BLOCKED` records in the Longlist;
- zero excluded, ST, suspended or unknown-board names in the Longlist;
- zero missing Longlist scores;
- contiguous ranks `1–100`.

The temporary `UNKNOWN`-board symbol `302132.SZ` is explicitly routed to `REVIEW_ONLY`. It cannot benefit from a meaningless one-security board-neutral percentile.

## Economic condition checks

All accepted trend-persistence names satisfy:

- non-negative 60-session return;
- non-negative 120-session return;
- non-negative 250-to-20-session momentum;
- distance from the 52-week high no worse than `-35%`.

All liquid-breakout names satisfy:

- non-negative 20- and 60-session returns;
- distance from the 52-week high no worse than `-20%`;
- 20/60-session volume ratio between `1.10` and `3.00`.

All recovery-watch names satisfy:

- 20-session return of at least `3%`;
- non-negative 60-session return;
- 20/60-session volume ratio between `1.05` and `3.00`;
- at least one weak longer-horizon percentile condition.

Missing factors remain missing and never receive a zero, neutral percentile or neutral screening score.

## Defects found and closed during real acceptance

1. **Singleton unknown-board distortion.** A lone `UNKNOWN`-board security received 100th-percentile board-neutral scores despite negative absolute returns. Unknown boards are now review-only and core momentum sleeves also require positive absolute trends.
2. **Cross-sleeve raw-score distortion.** Raw weighted scores were not directly comparable across archetypes and eliminated standalone recovery names. Final ranking now blends within-sleeve rank percentiles and raw scores.
3. **Human identity omission.** Initial machine outputs contained symbols but no security names. The final screen binds canonical security-master name, exchange, listing status and available industry identity and independently validates name completeness.

## Canonical outputs

- `outputs/screens/current/SCREENING_UNIVERSE.parquet`
- `outputs/screens/current/SCREENING_SLEEVE_DETAIL.parquet`
- `outputs/screens/current/SCREENING_LONGLIST.csv`
- `outputs/screens/current/SCREENING_FUNNEL.csv`
- `outputs/screens/current/SCREENING_QUALITY.json`
- `outputs/screens/current/SCREENING_VALIDATION.json`
- `outputs/screens/current/SCREENING_MANIFEST.json`
- `outputs/screens/current/SCREENING_CURRENT_RELEASE.json`

## Controlled limitations

1. FMDL-2C uses only the accepted market-behaviour factors from FMDL-2B.
2. Financial quality, valuation, market capitalization, dividends and analyst revisions remain FMDL-3.
3. Industry coverage is incomplete and therefore is displayed where available but is not used to force sector quotas.
4. A single-date screen does not prove economic alpha or rank persistence.
5. FMDL-2D must test same-date replay, date-to-date turnover, sleeve stability, board/industry concentration, rank migration and false-positive behavior.
6. No result enters the live Investment OS candidate pool until Public Equity Investing research and the later FMDL-4 re-entry contract are completed.
7. No simulation or real holding changed.

## Authorized next phase

`FMDL-2D — Replay, Stability & Final FMDL-2 Acceptance`
