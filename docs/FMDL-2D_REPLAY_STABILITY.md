# FMDL-2D — Replay, Stability & Final FMDL-2 Acceptance

## Objective

Validate that the accepted FMDL-2 market-behaviour factor and screening layer is deterministic, operationally stable and safe to hand off to the next data phase. FMDL-2D is not a factor-alpha backtest and does not create investment or trade authority.

## Replay design

FMDL-2D runs two complementary checks:

1. **Same-date deterministic replay** — rebuild the accepted Screening Current from the exact accepted Factor Current and require semantic equality for the screening universe, sleeve detail, Longlist and funnel.
2. **Six-session cohort replay** — rebuild factors and screens for the latest six market sessions from the accepted composite history, using the fixed current A-share Universe as a controlled cohort.

The cohort replay is intentionally labelled as operational stability evidence. It is not point-in-time survivorship-free because a historical security master, historical ST identity and complete historical industry classification are not yet available.

## Stability diagnostics

The engine produces:

- consecutive Longlist overlap and entrants/exits;
- Top-20 overlap;
- common-name rank Spearman correlation;
- median absolute rank movement;
- primary-sleeve and research-priority retention;
- sleeve-level Jaccard stability;
- board and available-industry concentration;
- current structural fragility flags;
- comparison with the accepted 2026-07-16 factor candidate as a historical anchor.

## Structural false-positive review

Without future returns, FMDL-2D cannot honestly calculate a realized false-positive rate. It therefore produces an ex-ante structural risk review using explicit flags such as single-sleeve dependence, bottom-quartile rank, near-floor liquidity, non-valid factor quality, current event flags, large drawdown and negative short-term return.

These flags prioritize research and rejection testing. They are not predictions of subsequent underperformance.

## Hard acceptance gates

Publication is blocked when:

- any same-date semantic artifact differs from Current;
- fewer than six sessions are replayed;
- a replay Longlist becomes materially thin;
- overlap, Top-20 retention, rank correlation or primary-sleeve retention breaches the hard floor;
- board concentration breaches the hard cap;
- Priority-A structural fragility breaches the hard cap;
- the historical factor anchor falls below 99% raw-factor cell agreement;
- independent artifact, hash, identity or authority validation fails.

Target ranges are reported separately. Missing a target may create a controlled warning without defeating acceptance when the hard operational floor remains intact.

## Canonical outputs

Candidate evidence:

- `outputs/stability/candidate/FMDL2D_ACCEPTANCE.json`
- `outputs/stability/candidate/DAILY_REPLAY_SUMMARY.csv`
- `outputs/stability/candidate/RANK_TRANSITIONS.csv`
- `outputs/stability/candidate/SLEEVE_TRANSITIONS.csv`
- `outputs/stability/candidate/RANK_MIGRATIONS.csv`
- `outputs/stability/candidate/FALSE_POSITIVE_RISK_REVIEW.csv`
- `outputs/stability/candidate/REPLAY_LONGLISTS.csv`
- `outputs/stability/candidate/FMDL2D_VALIDATION.json`
- `outputs/stability/candidate/FMDL2D_MANIFEST.json`

After validation and main publication:

- `outputs/stability/current/`
- `outputs/stability/current/FMDL2_FINAL_RELEASE.json`
- `outputs/status/FMDL2D_LAST_SUCCESS.json`

## Authority boundary

All FMDL-2D outputs remain `RESEARCH_PRIORITY_ONLY_NO_TRADE_AUTHORITY`. The phase cannot promote names into the live Investment OS candidate pool, change a simulation or real portfolio, or claim factor alpha.
