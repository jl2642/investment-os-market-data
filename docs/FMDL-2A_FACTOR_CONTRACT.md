# FMDL-2A — Market Factor Contract v1.0

## 1. Purpose

This contract defines the market-behaviour factors that may be calculated from the accepted FMDL-1 A-share universe and daily price/volume history. It deliberately excludes financial-statement, market-cap, valuation, dividend and analyst-estimate factors; those remain FMDL-3.

All outputs are **research-priority evidence only**. No factor, score, rank or sleeve creates BUY/ADD/SELL permission.

## 2. Input authority

Required current inputs:

- `outputs/investment_os/INVESTMENT_OS_MARKET_DATA_INTERFACE.json`;
- `outputs/current/A_SHARE_UNIVERSE.csv`;
- `outputs/current/DAILY_MARKET_SNAPSHOT.csv`;
- `outputs/current/MARKET_EVENT_FLAGS.csv`;
- a validated historical daily store produced from the source selected by the FMDL-2A benchmark.

A full-market factor run is blocked when the FMDL-1 interface is invalid, Current has a hard failure, hashes or row counts disagree, or the latest snapshot is stale under the interface policy.

## 3. Price basis

- Return, volatility, drawdown and distance-to-high factors use **forward-adjusted daily close (`qfq`)** when a source exposes a stable qfq series.
- Liquidity factors use unadjusted source-reported volume and turnover amount.
- Adjustment mode and provider must be recorded per series.
- Missing observations remain missing; they are never filled with zero.
- No value after the factor `as_of_date` may enter a calculation.

## 4. Investability and data-readiness fields

| Field | Definition | Hard/soft use |
|---|---|---|
| `history_observations` | valid daily close observations up to `as_of_date` | factor availability |
| `history_coverage_ratio_250` | valid observations divided by min(250, expected listed sessions) | quality gate |
| `latest_history_date` | last valid date in the historical series | freshness gate |
| `suspension_days_20/60` | days with suspension/no valid trade in the window | exclusion/review |
| `zero_turnover_days_20/60` | traded-labelled days with zero amount | review |
| `event_flag_count` | current market-event flags attached to the symbol | review |
| `factor_record_quality` | `VALID`, `PARTIAL`, `SUSPECT`, `BLOCKED` | downstream routing |

## 5. Price and momentum factors

| Factor ID | Formula/definition | Minimum valid observations |
|---|---|---:|
| `return_20d` | `close_t / close_(t-20) - 1` | 21 |
| `return_60d` | `close_t / close_(t-60) - 1` | 61 |
| `return_120d` | `close_t / close_(t-120) - 1` | 121 |
| `return_250d` | `close_t / close_(t-250) - 1` | 251 |
| `momentum_250_20d` | `close_(t-20) / close_(t-250) - 1` | 251 |
| `distance_52w_high` | `close_t / max(close over latest 250 sessions) - 1` | 120; partial until 250 |
| `trend_consistency_60d` | share of valid daily returns above zero over 60 sessions | 41 |
| `positive_month_ratio_12m` | positive 20-session blocks / available blocks, maximum 12 | 120 |

Cross-sectional relative-strength percentiles are derived only after the same-date factor table is complete; they are not source fields.

## 6. Risk factors

| Factor ID | Formula/definition | Minimum valid observations |
|---|---|---:|
| `volatility_20d` | standard deviation of daily returns × sqrt(252) | 16 |
| `volatility_60d` | standard deviation of daily returns × sqrt(252) | 41 |
| `downside_volatility_60d` | standard deviation of negative daily returns × sqrt(252) | partial when negative-return count is low |
| `max_drawdown_120d` | minimum of `close / running_max(close) - 1` | 81 |
| `max_drawdown_250d` | same over 250 sessions | 120; partial until 250 |
| `worst_day_120d` | minimum one-day adjusted return | 81 |
| `extreme_move_days_120d` | count of absolute daily returns above board-aware review threshold | 81 |

## 7. Liquidity and trading-stability factors

| Factor ID | Formula/definition | Minimum valid observations |
|---|---|---:|
| `avg_turnover_cny_20d` | mean daily turnover amount | 16 |
| `avg_turnover_cny_60d` | mean daily turnover amount | 41 |
| `median_turnover_cny_60d` | median daily turnover amount | 41 |
| `turnover_stability_60d` | median turnover / mean turnover, bounded `[0,1]` | 41 |
| `turnover_cv_60d` | standard deviation / mean turnover | 41 |
| `volume_ratio_20_60d` | mean volume over 20 / mean volume over 60 | 41 |
| `active_trade_ratio_60d` | sessions with positive close and turnover / expected sessions | 41 |

## 8. Cross-sectional derived fields

Calculated only across symbols that pass the factor's availability gate on the same `as_of_date`:

- factor percentile, ascending or descending as specified in the factor registry;
- board-neutral percentile;
- broad-market percentile;
- winsorized z-score for diagnostic use;
- missingness and confidence fields.

No missing factor may be assigned a neutral percentile. It remains missing and receives an explicit reason code.

## 9. Factors deferred to FMDL-3

The following are prohibited in FMDL-2 until an accepted financial/valuation source exists:

- market capitalization and free-float capitalization ranks;
- PE, PB, PS, EV/EBITDA and free-cash-flow yield;
- ROE, ROIC, gross margin, operating margin and cash-conversion quality;
- revenue, profit and cash-flow growth;
- leverage and balance-sheet resilience;
- dividend yield, payout stability and buyback factors;
- analyst forecasts or consensus revisions;
- bank, insurer and broker sector-specific fundamentals.

## 10. Quality and anti-leakage rules

1. Every row carries `as_of_date`, provider, adjustment mode, history start/end, observation count and a row hash.
2. Calculations slice data at or before `as_of_date` before any rolling operation.
3. Newly listed securities receive only factors supported by their available history.
4. Suspensions and missing days are not converted into zero returns.
5. Corporate-action discontinuities must be controlled by the selected adjusted series and anomaly checks.
6. A factor table is quarantined when row identity, dates, hashes or formula regression checks fail.
7. Factor ranks are research triage only and must re-enter Public Equity Investing and Investment OS through the accepted FMDL-1F interface.
