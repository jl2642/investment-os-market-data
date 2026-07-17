# FMDL-2C — Screening Sleeves & Funnel

## Phase objective

Turn the accepted FMDL-2B factor Current into a transparent, reproducible research-priority funnel. FMDL-2C is an idea-generation layer, not a trade engine and not a factor-alpha claim.

## Frozen sleeves

1. **TREND_PERSISTENCE** — medium-term trend breadth and persistence with minimum risk overlays.
2. **LIQUID_BREAKOUT** — short-term acceleration near the annual high, confirmed by volume and liquidity.
3. **DEFENSIVE_STABILITY** — low realized risk, shallow drawdown and stable trading behavior.
4. **RECOVERY_WATCH** — early recovery after weak long-horizon performance; watchlist-only routing.

Each sleeve has explicit required fields, weights, thresholds, maximum candidate count and route. Missing factor inputs are never neutralized.

## Investability routing

Every A-share Current symbol is classified into one of four states:

- `ELIGIBLE_CORE` — may enter core sleeves;
- `ELIGIBLE_WATCH` — may enter watch sleeves only;
- `REVIEW_ONLY` — visible in audit outputs but cannot enter the Longlist;
- `EXCLUDED` — blocked by data quality, suspension, minimum liquidity or trading-continuity rules.

ST names are review-only. `SUSPECT` and `BLOCKED` factor records, current suspensions and names below absolute liquidity floors cannot enter any sleeve.

## Funnel and Longlist

Per-sleeve scores are weighted averages of direction-aware board-neutral percentiles. All weighted inputs must be present. Sleeve-specific raw triggers and risk overlays are applied after scoring.

The final research Longlist:

- de-duplicates cross-sleeve names;
- adds a small, capped cross-sleeve confirmation bonus;
- is capped at 100 symbols;
- assigns `A_IMMEDIATE_RESEARCH`, `B_WATCH_OR_TRIGGER`, or `C_SCREEN_FLAG_ONLY`;
- routes every name to `PUBLIC_EQUITY_INVESTING_IDEA_GENERATION`;
- does not promote any name into the live Investment OS candidate pool.

## Canonical outputs

- `outputs/screens/candidate/SCREENING_UNIVERSE.parquet`
- `outputs/screens/candidate/SCREENING_SLEEVE_DETAIL.parquet`
- `outputs/screens/candidate/SCREENING_LONGLIST.csv`
- `outputs/screens/candidate/SCREENING_FUNNEL.csv`
- `outputs/screens/candidate/SCREENING_QUALITY.json`
- `outputs/screens/candidate/SCREENING_VALIDATION.json`
- `outputs/screens/candidate/SCREENING_MANIFEST.json`
- `outputs/screens/current/` after independent validation and publication

## Phase boundary

FMDL-2C establishes the screening architecture and first real full-market output. FMDL-2D owns replay, date-to-date rank stability, turnover, sleeve concentration, false-positive review and final FMDL-2 acceptance. Financial quality, valuation, market capitalization and analyst factors remain FMDL-3.
