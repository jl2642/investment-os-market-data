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

## Constraint-driven sizing

P4-2 does not calculate an alpha score or use a fixed Top-N. Independent constraints each produce a sizing cap and the final analytical cap is the minimum of those caps.

The caps cover Candidate tier, volatility, historical-drawdown loss budget, marginal risk, Pareto opportunity cost, evidence confidence, direct-sector room, direct-equity-style room and liquidity. A favorable attribute cannot offset a binding risk constraint.

`PRIMARY_BUILD_REVIEW` requires low relative opportunity cost plus explicit diversification improvement. `SECONDARY_BUILD_REVIEW` requires low/moderate opportunity cost and bounded marginal risk. `PROBE_BUILD_REVIEW` is used when positive Portfolio Fit remains subject to evidence or risk constraints. High relative opportunity cost receives no new-size envelope.

## Direct-equity style scope

P4-1R preserves useful cross-asset style context. P4-2 uses a narrower direct-equity style-room definition for single-stock concentration control. Fixed-income holdings and generic pooled vehicles are therefore excluded from direct-equity style room rather than being treated as existing single-stock style exposure.

The P4-2 evidence surface retains both the original P4-1R style weight and the construction-specific direct-equity style weight for auditability.

## Exact A/H overlap

An exact A/H same-issuer overlap is `SUBSTITUTION_REVIEW_ONLY`. Net new weight is zero. The replacement-equivalent analytical cap cannot exceed the existing overlap weight and remains subject to applicable single-name risk, volatility, confidence, opportunity-cost and liquidity limits.

Because an equal-value same-issuer substitution does not itself add sector or style exposure, it does not consume net-new sector/style room. If one account has a new-build review while the other has a same-issuer substitution review, the combined route is `ADVANCE_MIXED_NEW_AND_SUBSTITUTION_SCENARIO_TEST` so both account semantics remain visible.

## Sizing envelope semantics

Suggested minimum/maximum weights and analytical caps are single-security analytical envelopes. They are **non-additive** and are not an aggregate portfolio allocation.

P4-3 must assemble complete portfolio scenarios under aggregate HK sleeve, sector/style, funding and risk budgets before any portfolio proposal exists.

## Funding semantics

REAL broker cash remains execution balance only. Zero broker cash is not a security rejection and does not create a strategic cash target. SIMULATION cash is funding context only and never alpha or automatic admission authority.

## Accepted real-run result

Accepted Canonical-input run as of 2026-08-07:

- 140 Account × Security reviews; 70 combined security routes.
- REAL: 1 `PRIMARY_BUILD_REVIEW`, 8 `SECONDARY_BUILD_REVIEW`, 40 `PROBE_BUILD_REVIEW`, 20 `WATCH_NO_SIZE`, 1 `NO_INCREMENTAL_ROLE`.
- SIMULATION: 4 `SECONDARY_BUILD_REVIEW`, 41 `PROBE_BUILD_REVIEW`, 2 `SUBSTITUTION_REVIEW_ONLY`, 20 `WATCH_NO_SIZE`, 3 `NO_INCREMENTAL_ROLE`.
- Combined: 45 `ADVANCE_DUAL_SCENARIO_TEST`, 2 `ADVANCE_MIXED_NEW_AND_SUBSTITUTION_SCENARIO_TEST`, 2 `ADVANCE_REAL_SCENARIO_TEST`, 21 `HOLD_PORTFOLIO_WATCH`.
- Huishang Bank 03698 is the single REAL `PRIMARY_BUILD_REVIEW`, with a single-security analytical envelope of approximately 1.52%–3.03%.
- Midea Group H 00300 / SIMULATION is substitution-only against 000333.SZ: existing overlap approximately 6.52%, replacement-equivalent cap approximately 1.88%, net new weight 0.
- CM Bank H 03968 / SIMULATION is substitution-only against 600036.SH: existing overlap approximately 6.06%, replacement-equivalent cap approximately 2.17%, net new weight 0.
- REAL defensive-style raw context of approximately 39.52% is reduced to direct-equity style exposure of 0% where that raw weight came from fixed-income holdings; China Mobile, CLP Holdings and PCCW therefore no longer lose construction capacity because of bond-fund exposure.
- High-relative-opportunity-cost rows receive zero new-size authorization.
- P4-1 `NO_INCREMENTAL_ROLE` rows remain zero-size.
- Independent validator: `PASS`, `errors=[]`.
- Candidate, REAL, SIMULATION and portfolio mutations = 0; orders = 0; `trade_authority=NONE`.

## Governance boundary

P4-2 does not mutate Candidate membership, REAL positions or SIMULATION positions; does not create an aggregate portfolio allocation, Pre-trade Memo, user trade confirmation or order; and does not grant trade authority.

A clean PASS advances only to `P4_3_PORTFOLIO_CONSTRUCTION_SCENARIO_TEST`.
