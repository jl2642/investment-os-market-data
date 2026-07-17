# FMDL-2B-3 Acceptance — Basic Factor Engine

## Acceptance state

`ACCEPTED_WITH_CONTROLLED_PARTIAL_AND_FOUR_SYMBOL_QUARANTINE`

FMDL-2B-3 has built and independently validated the first full-market A-share basic-factor candidate from the accepted FMDL-2B-2 immutable history base. The release is approved as factor evidence for FMDL-2B-4 incremental-update engineering and later FMDL-2C screening-sleeve design.

It remains research-priority evidence only. It does not demonstrate factor alpha, create a Longlist, promote a live candidate, change simulation or real holdings, or grant trade authority.

## Release identity

- Factor run ID: `FMDL2B3_20260717T162732+0800`
- As-of date: `2026-07-16`
- Input history release: `FMDL2B2_29556547410_1`
- Factor contract version: `1.0.0`
- Factor count: `26`
- Full-market workflow: `FMDL 2B-3 Basic Factor Engine`
- Initial independent full-market workflow run: `29565867088` — `SUCCESS`
- Persisted candidate manifest: `outputs/factors/candidate/BASIC_FACTOR_MANIFEST.json`
- Trade authority: `NONE`

## Full-market result

| Metric | Result |
|---|---:|
| Accepted A-share Universe | 5,529 |
| Wide factor rows | 5,529 |
| Symbol-factor detail rows | 143,754 |
| Valid symbols | 5,361 |
| Partial symbols | 164 |
| Suspect symbols | 0 |
| Blocked symbols | 4 |
| Available factor values | 142,625 |
| Missing factor values | 1,129 |
| Overall factor-value availability | 99.2146% |
| Hard failures | 0 |

The wide table covers every accepted Universe symbol exactly once. The long table contains exactly one record for every `5,529 × 26` symbol-factor pair.

## Factor coverage

- 20-session return coverage: `5,514 / 5,529` (`99.7287%`);
- 60-session return coverage: `5,487 / 5,529` (`99.2404%`);
- 120-session return coverage: `5,448 / 5,529` (`98.5350%`);
- 250-session return and 250-to-20 momentum coverage: `5,383 / 5,529` (`97.3594%`);
- 60-session volatility, downside volatility, turnover and trading-activity coverage: generally `5,503 / 5,529` (`99.5298%`);
- inferred suspension and zero-turnover controls: `5,525 / 5,529` (`99.9277%`).

Longer-window coverage is lower by design because newly listed securities do not receive factors unsupported by available history.

## Missingness reconciliation

All 1,129 missing values have explicit reason codes:

| Reason | Missing values |
|---|---:|
| `INSUFFICIENT_HISTORY` | 882 |
| `HISTORY_QUARANTINED` | 104 |
| `MISSING_OR_INSUFFICIENT_TURNOVER` | 98 |
| `MISSING_OR_INSUFFICIENT_VOLUME` | 23 |
| `INSUFFICIENT_EXPECTED_SESSIONS` | 22 |

No missing factor was converted to zero, a neutral percentile or a neutral z-score.

## Quality-state interpretation

### `VALID` — 5,361 symbols

These symbols have current single-provider QFQ history, acceptable coverage, no missing factor and no current review condition under the FMDL-2B-3 policy.

### `PARTIAL` — 164 symbols

Partial does not mean the entire record failed. It means at least one controlled limitation remains, principally:

- insufficient listing history for one or more long-window factors;
- limited expected sessions for very new listings;
- current suspension, zero-turnover or other market-event review flags;
- lower-than-target calendar coverage;
- one restricted Tencent fallback series.

`002898.SZ` is the only accepted Tencent fallback history. Price and turnover-amount factors are available, while the unvalidated historical volume factor remains missing.

`920305.BJ` has all 26 factors but receives confidence grade `C` because its 250-session calendar coverage is `77.6%`; the engine did not silently upgrade it to full confidence.

### `BLOCKED` — 4 symbols

- `688089.SH`
- `688143.SH`
- `688173.SH`
- `689009.SH`

These are exactly the four controlled FMDL-2B-2 historical quarantines. Each has one factor-status row and 26 explicit missing factor records. None receives a raw factor, percentile or z-score.

## Formula and anti-leakage acceptance

The following gates passed:

- all history was sliced at or before `2026-07-16` before rolling calculations;
- only the 26 factors frozen in FMDL-2A were implemented;
- return and risk factors use QFQ close;
- liquidity factors use source-reported amount and volume without fabrication;
- factor minimum-observation rules were enforced;
- broad-market and board-neutral percentiles were calculated only for available same-date values and follow the registry direction;
- raw factor values in the wide table reconcile to the long detail table;
- bounded ratios, drawdowns, volatility, turnover and count factors passed range and sign checks;
- output hashes, row counts, Universe identity and as-of dates reconcile;
- no BUY/ADD/SELL, target-weight or trade-permission field exists.

## Controlled limitations and non-claims

1. Cross-sectional ranks are a research-ordering tool, not evidence of future excess return.
2. Current ST classification and current board identity are not point-in-time historical classification data.
3. The history base is not a survivorship-free point-in-time Universe backtest.
4. Free-source QFQ continuity still requires incremental overlap and corporate-action refresh controls in FMDL-2B-4.
5. Factor stability, turnover, replay and screening performance remain FMDL-2D work.
6. Financial, valuation, market-cap, dividend and analyst factors remain prohibited until FMDL-3.
7. No candidate pool, simulation account, real account or trading state changed.

## Operational hygiene correction

During the first PR run, the legacy daily production workflow was found to trigger on research-development pull requests. That run remained non-writing because its production commit step was skipped. The workflow has now been corrected so daily production no longer runs on pull requests; it remains available through the weekday schedule, manual dispatch and controlled main-branch production paths.

## Authorized next phase

`FMDL-2B-4 — Incremental Update, Refresh & Final Acceptance`

FMDL-2B-4 must implement controlled daily overlap updates, corporate-action/QFQ continuity checks, Last-known-good factor publication, stale-input blocking, quarantine recovery, deterministic refresh behavior and final FMDL-2B operating acceptance. FMDL-2C screening sleeves must not begin until B4 has made the factor layer maintainable rather than one-shot.
