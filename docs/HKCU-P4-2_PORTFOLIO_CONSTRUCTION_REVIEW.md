# HKCU P4-2 Portfolio Construction Review

## Purpose

P4-2 converts the accepted P4-1 Portfolio Fit reassessment into account-specific construction priorities, substitution-only reviews and bounded single-security analytical sizing envelopes.

It consumes the accepted P4-1R numeric portfolio-context surface rather than inferring construction from Candidate rank or a weighted score.

## Entry

A valid run requires:

- P4-1R runtime context = `PASS_P4_1R_PORTFOLIO_CONTEXT_COMPLETION`;
- P4-1 Portfolio Fit reassessment = `PASS_P4_1_PORTFOLIO_FIT_REASSESSMENT`;
- 70 active formal Hong Kong Candidates;
- 140 Account × Security fit/context rows;
- current REAL and SIMULATION position states;
- `trade_authority=NONE`.

## Construction states

Each Candidate is reviewed separately for REAL and SIMULATION and receives one of:

- `PRIMARY_BUILD_REVIEW`
- `SECONDARY_BUILD_REVIEW`
- `PROBE_BUILD_REVIEW`
- `SUBSTITUTION_REVIEW_ONLY`
- `WATCH_NO_SIZE`
- `NO_INCREMENTAL_ROLE`

These are construction-review states, not orders or portfolio mutations.

## No weighted score

P4-2 does not calculate an alpha score or use a fixed Top-N. Independent constraints each produce a sizing cap and the final analytical cap is the minimum of those caps.

The independent caps cover:

1. Candidate tier maximum;
2. volatility scaling versus the current account;
3. single-name historical-drawdown loss budget;
4. accepted marginal-risk state;
5. accepted Pareto opportunity-cost state;
6. evidence-confidence limits;
7. remaining direct-sector room;
8. remaining direct-style room;
9. liquidity / average-turnover capacity.

A favorable attribute cannot offset a binding risk constraint.

## Priority semantics

`PRIMARY_BUILD_REVIEW` requires low relative opportunity cost plus explicit diversification improvement, without simultaneous sector and style concentration pressure.

`SECONDARY_BUILD_REVIEW` requires low/moderate opportunity cost and bounded marginal risk without simultaneous sector and style concentration pressure.

`PROBE_BUILD_REVIEW` is reserved for positive Portfolio Fit with evidence or risk constraints that justify a small analytical envelope.

High relative opportunity cost does not receive new-size authorization at P4-2.

## Exact A/H overlap

An exact A/H same-issuer overlap is routed to `SUBSTITUTION_REVIEW_ONLY`. P4-2 may calculate a replacement-equivalent analytical cap, but net new weight is zero. Any later proposal must compare the H-share with the existing A-share or other exact same-issuer exposure explicitly.

## Sizing envelope semantics

The output may include suggested minimum/maximum weights and an analytical cap for one security in one account. These values are **non-additive**. They are not a portfolio allocation and must not be summed across securities.

P4-3 must assemble complete portfolio scenarios under aggregate HK sleeve, sector/style, funding and risk budgets before a portfolio proposal exists.

## Funding semantics

REAL broker cash remains execution balance only. Zero broker cash is not a security rejection and does not create a strategic cash target; positive REAL construction rows state that external liquidity or a separate capital decision may be required.

SIMULATION cash is funding context only and never alpha or automatic admission authority.

## Governance boundary

P4-2 does not:

- mutate Candidate membership;
- mutate REAL positions;
- mutate SIMULATION positions;
- create an aggregate portfolio allocation;
- create orders;
- create a Pre-trade Memo;
- record user trade approval;
- grant trade authority.

`trade_authority=NONE` throughout.

A clean PASS advances only to `P4_3_PORTFOLIO_CONSTRUCTION_SCENARIO_TEST`.
