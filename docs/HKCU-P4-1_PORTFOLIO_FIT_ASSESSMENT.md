# HKCU P4-1 Portfolio Fit Assessment

## Purpose

P4-1 executes the frozen P4-0 Portfolio Fit Contract for all 70 formal Hong Kong Candidates against the current Real Account and Simulation portfolios separately. It is an assessment gate only. It does not admit a security to either portfolio, set a target weight, move cash, create an order or change trade authority.

## Assessment surface

- 70 formal Active HK Candidates: 2 Core + 68 Watch.
- 2 portfolio contexts: REAL and SIMULATION.
- 15 frozen P4 rules.
- 140 Account × Security assessments.
- 2,100 Account × Security × Rule rows.
- One combined routing state per Candidate derived from the two explicit account states.

## Canonical evidence binding

P4-1 binds directly to P4-0, HK Candidate Current, HKCU Current, the FMDL-5B2 issuer/cross-market semantics, and the current Real/Simulation position states. Fuzzy name matching is prohibited. Direct overlap is evaluated from current holdings; confirmed issuer/cross-market relationships are used when available.

## Fail-closed context audit

The repository audit performed before implementation found four decision-critical context surfaces that are not present in the accepted P4-1 inputs:

1. **Sector / industry classification.** HKCU `category` and `sub_category` describe listing/security taxonomy, not economic industry. P2A sleeve labels are factor/research context and may not masquerade as industry classification. Therefore P4R10 must DEFER until a Canonical classification and account exposure surface is added.
2. **Portfolio factor/style/theme look-through.** Candidate `primary_sleeve` exists, but current portfolio holdings are not mapped into the same accepted taxonomy. P4R11 therefore cannot assert that a Candidate increases or offsets portfolio concentration.
3. **Marginal diversification/downside-risk evidence.** No accepted account-level covariance, downside co-movement or equivalent marginal-risk surface is currently bound to P4-1. P4R12 cannot infer diversification from ticker count.
4. **Expected-return/opportunity-cost comparison.** Candidate valuation support exists, but there is no accepted risk/return comparison surface tying Candidates to relevant existing exposures and alternatives. A/H discount remains context, not alpha. P4R13 therefore defers.

These are evidence gaps, not bearish judgments on the 70 companies. The engine must materialize them as `DEFER` rather than neutral-fill them.

## Fit semantics

Account states remain exactly those frozen by P4-0: `FIT`, `FIT_WITH_CONSTRAINTS`, `NO_INCREMENTAL_ROLE`, `DEFER_PORTFOLIO_CONTEXT`, and `BLOCK_PORTFOLIO_FIT`. Missing decision-critical context routes to `DEFER_PORTFOLIO_CONTEXT`; a substantive hard investment/portfolio blocker is required for `BLOCK_PORTFOLIO_FIT`.

Direct existing holdings or confirmed same-issuer exposure are not automatic rejection. They must be recorded as overlap and later judged as add/substitute/duplicate risk. Real Account execution cash of zero is likewise not an automatic portfolio-fit blocker: the Real Account cash policy remains broker execution balance only, with external liquidity excluded. If a security later advances, funding requires a separate capital decision.

P4R14 may state an analytical no-size or construction-review envelope, but that is not position sizing authority. While required portfolio context is missing, the only permitted envelope is `NO_SIZE_PENDING_PORTFOLIO_CONTEXT`.

## Current engineering outcome

The P4-1 engine is intentionally capable of producing a structurally complete 2,100-row assessment while returning `BLOCKED_P4_1_PORTFOLIO_CONTEXT`. That status means the assessment infrastructure passed but positive portfolio-fit conclusions are not yet evidentially supportable. The next gate is `P4_1R_PORTFOLIO_CONTEXT_COMPLETION`, not P4-2.

## Governance boundary

P4-1 changes none of the following:

- HK Candidate membership;
- Simulation positions;
- Real Account positions;
- portfolio allocations;
- orders;
- trade authority.

`trade_authority=NONE` throughout.
