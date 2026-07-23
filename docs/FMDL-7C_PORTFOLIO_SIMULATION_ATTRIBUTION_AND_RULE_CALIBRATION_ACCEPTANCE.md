# FMDL-7C｜Portfolio, Simulation, Attribution & Rule Calibration Acceptance

## Objective

FMDL-7C proves that the accepted Investment OS state can be converted into a transparent portfolio diagnostic, simulation PnL bridge, Candidate Pool observation and governed rule-calibration proposal set without confusing an accepted historical snapshot with current live state.

The accepted operating snapshot is `2026-07-20_CLOSE`. No post-as-of account change is fabricated, no new market data is fetched in this phase and no live trade recommendation is issued.

## Authoritative inputs

The phase binds:

- FMDL-7B Release 50;
- the Release-4 real-account, simulation and Candidate Core state binding;
- the POST-FMDL-4 Action Review;
- thirty accepted A-share and ETF 2026-07-20 closes;
- three accepted latest bond-fund NAVs;
- five FMDL-4D feedback proposals;
- six FMDL-4D no-position attribution baselines.

## Real-account attribution

The seven real-account positions are recalculated from the accepted close or NAV snapshot. The account reconciles to:

- total assets: RMB 448,831.42;
- stock and ETF value: RMB 134,732.00;
- bond-fund value: RMB 313,978.93;
- execution cash: RMB 120.49;
- mark-to-recorded-cost estimate: RMB -3,672.05;
- stock and ETF contribution estimate: RMB -7,036.60;
- bond-fund contribution estimate: RMB +3,364.55.

This is an unrealized mark-to-recorded-cost estimate, not a verified total-return calculation. It does not infer distributions, historical cash flows, fees or tax where those records are not present.

The accepted judgment remains `HOLD_AND_MONITOR_LKG_ONLY`. The two S&P 500 ETFs remain a controlled review case. Consolidation requires fresh cost, tracking, liquidity, tax and execution evidence and cannot occur automatically.

## Simulation attribution

The sixteen simulation positions reconcile to:

- market value: RMB 782,180.60;
- available cash: RMB 219,533.98;
- total assets: RMB 1,001,714.58;
- account total PnL: RMB +1,714.58;
- open-position unrealized PnL: RMB +10,165.00;
- closed-position, fee and other account residual: RMB -8,450.42.

The residual is explicit because open-position contribution cannot be forced to equal total account PnL. FMDL-7C does not fabricate a more granular decomposition without a complete closed-trade and fee ledger.

Ten open positions contribute positively and six contribute negatively. Four names retain no-add controls and two names retain hard-review controls. Positive simulation outcomes are observations, not proof of persistent alpha and not authorization for real-capital migration.

## Candidate Pool review

Candidate Core remains at twenty names. Six Active Memo thresholds are evaluated against the accepted 2026-07-20 snapshot and none are met. Thirteen Candidate Core names have simulation exposure; seven do not.

A Candidate Core name without an approved entry baseline, benchmark, observation window and exposure state does not receive a fabricated return or selection-attribution result. A met price threshold would route to memo review only and would not automatically change Candidate Pool, simulation or real-account state.

## Decision-layer separation

The phase stores facts, judgments, controlled-process recommendations and rule proposals separately.

Facts describe the accepted snapshot and calculations. Judgments describe hold, monitor and observe postures. Controlled-process recommendations describe review steps such as duplicate ETF comparison and the current-state refresh gate. Rule proposals remain versioned proposals and are not applied.

No security-level live investment recommendation or immediate trade proposal is emitted because current post-2026-07-20 state has not been confirmed.

## Rule calibration

Eight proposals are registered:

1. current-state and market-freshness gate before live action;
2. mandatory simulation PnL bridge;
3. controlled duplicate benchmark-exposure review;
4. binding no-add and hard-review controls;
5. multi-observation requirements before real-capital migration;
6. validated-current-price Candidate trigger evaluation;
7. approved entry baselines before candidate outcome attribution;
8. a firewall against single-period rule mutation.

Every proposal is `PROPOSED_NOT_APPLIED`, requires regression and human approval, and creates no rule mutation.

## Failure injection

The phase must reject:

- a historical LKG snapshot presented as Current;
- stale prices used for a live trade recommendation;
- automatic consolidation of the two S&P 500 ETFs;
- a broken simulation PnL bridge;
- bypass of no-add or hard-review controls;
- a single-period rule mutation;
- a fabricated Candidate price trigger;
- any trade-authority escalation.

Rejected fixtures cannot replace Current or Last-known-good.

## Completion boundary

FMDL-7C accepts the attribution calculations, action-review separation, controlled operating judgments and rule-calibration proposal mechanism. It does not refresh the latest market session, confirm post-as-of account activity, change Candidate Pool or portfolio state, repack the File Library Canonical package, connect brokerage or create an order.

## Exit

`FMDL7C_PORTFOLIO_SIMULATION_ATTRIBUTION_AND_RULE_CALIBRATION_ACCEPTED`

## Next gate

`FMDL-7D_SCHEDULED_OPERATIONS_MONITORING_STALENESS_AND_COST_CONTROLS`

Authority remains decision support only; `trade_authority = NONE`.
