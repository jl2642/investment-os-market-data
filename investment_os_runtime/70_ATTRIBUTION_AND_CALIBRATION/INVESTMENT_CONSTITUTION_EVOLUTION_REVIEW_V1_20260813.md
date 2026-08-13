# Investment Constitution & Evolution Review v1

- Review date: 2026-08-13
- Status: DRAFT_REVIEW_NOT_POLICY
- Scope: Core Static, variable policy, operating cadence, conversation writeback, attribution/calibration, external philosophy benchmark
- Trade authority: NONE
- Rule mutation: NONE

> This document is an audit and proposal artifact. It does not modify Core Static, portfolio holdings, Candidate membership, action permissions, schedules, or trading authority.

## 1. Executive conclusion

The current Investment OS has a sound governance skeleton but is still heavier on process/governance than on a small set of memorable investment principles. The next stage should not add many rules. It should converge the existing rules into a small constitution, move numerical/operational choices into versioned policy, add an explicit conversation-to-writeback triage layer, and run a disciplined review cadence.

Recommended operating principle:

**High-frequency information, low-frequency action; continuous evidence accumulation, slow rule mutation.**

## 2. What should remain constitutional

The following principles are strong enough to remain or be promoted as constitutional candidates:

1. Stocks represent ownership in businesses; research must focus on business economics rather than price patterns alone.
2. Distinguish good company, good investment, and portfolio/account fit.
3. Stay inside a demonstrable circle of competence; uncertainty must reduce position confidence rather than be hidden by scoring precision.
4. Intrinsic value is a range based on future distributable cash flows and key assumptions, not a precise target price.
5. Price/cost basis is not value. Break-even is not a buy/sell reason.
6. Every BUY/ADD must pass an opportunity-cost test against cash, broad ETF exposure, and the best existing holding.
7. Position sizing depends on downside, correlation, liquidity, evidence confidence, and portfolio role—not on ranking alone.
8. No averaging down merely because a position is below cost; additions require refreshed thesis, valuation, cash-flow and portfolio-fit evidence.
9. Market volatility alone does not create an action. NO ACTION is a valid and often preferred daily conclusion.
10. Concentration is earned by understanding and evidence; it is not copied from famous investors.
11. Process quality and outcome must be reviewed separately; lucky profits do not validate a bad process, and sound decisions can have bad outcomes.
12. Rule changes require multiple observations, counter-evidence, replay/regression and explicit user approval.
13. ETF is the default alternative when single-company understanding or edge is insufficient.
14. Cash is an option and risk budget, not automatically idle capital; but cash targets are variable policy, not permanent doctrine.
15. The user remains final authority for real and simulation portfolio state changes and all trading decisions.

## 3. External benchmark assessment

### Buffett / Berkshire benchmark

The current system aligns well with the owner mindset, long-horizon orientation, intrinsic-value framework, and aversion to short-term trading. The major gap is not philosophy but operational emphasis: the system should more explicitly require a circle-of-competence statement, avoid pseudo-precision in valuation, and use opportunity cost as a formal decision gate.

### Duan Yongping benchmark

The strongest transferable principles are: buying a stock means owning a company; understanding the business is difficult and must precede conviction; future cash flow is the economic anchor; market noise should not dominate decisions; opportunity cost matters; and investors should avoid businesses they do not understand. The system should copy these filters, not copy concentrated position sizes or specific holdings.

## 4. Rule architecture recommendation

Use five layers:

### A. Core Static / Constitution
Stable principles and safety boundaries. Never changed automatically. Amend only by explicit user-approved governance change, normally after annual review or a major life/account objective change.

### B. Variable Policy
Position bands, cash bands, ETF roles, margin-of-safety conventions, Candidate thresholds, review windows and provider choices. These may generate automatic proposals, but cannot become effective automatically.

### C. Current State
Holdings, quantities, cash, costs, valuations, thesis status, simulation state, market/evidence watermarks. Update automatically when authoritative data is available or user-confirmed facts are provided.

### D. Observation / Decision-preparation layer
Evidence-backed but not-yet-actionable findings: e.g. potential re-add after earnings validation, NO-ADD until a report, valuation watch zones, event follow-ups. These should be written automatically with evidence, confidence, trigger, expiry/review date, and status.

### E. Conversation / Ephemeral
Hypotheses, market chat, exploratory scenarios, emotional reactions, and unverified opinions. Do not persist unless promoted by the writeback triage.

## 5. Conversation writeback triage

Every substantive investment conversation should be classified automatically into one of:

- NO_WRITEBACK
- OBSERVATION_WRITEBACK
- STATE_UPDATE_PROPOSAL
- POLICY_PROPOSAL
- CORE_PROPOSAL

Rules:

- Explicit user-confirmed transaction/position fact -> STATE_UPDATE_PROPOSAL (or governed current-state writeback if existing contract allows).
- Evidence-backed follow-up condition with decision relevance -> OBSERVATION_WRITEBACK.
- Repeated multi-case pattern suggesting a tunable rule -> POLICY_PROPOSAL.
- Long-lived objective/philosophy/safety-boundary change -> CORE_PROPOSAL.
- Market opinion, one-off hypothesis, or casual discussion -> NO_WRITEBACK.

No portfolio/Candidate/rule mutation may be inferred from silence or casual wording.

## 6. Review cadence

### Daily
Purpose: information and exception detection, not decision production.

Review: market/position abnormal moves, major company news, thesis triggers, stale data, required follow-up. Default acceptable conclusion: NO ACTION.

### Weekly
Purpose: clean the observation queue.

Review: which observations matured, expired, strengthened, weakened, or require research; unresolved position reviews; Candidate and thesis state changes.

### Monthly — Investment Discipline Review
Review behavior and process: trade count, chasing/averaging-down behavior, cost-basis anchoring, unnecessary turnover, position/conviction mismatch, cash deployment pressure, concentration drift, and process-vs-outcome classification.

Output: discipline scorecard + no more than three policy-calibration proposals.

### Quarterly — Strategy & Research Calibration
Refresh thesis, financials, valuation, ETF alternatives, opportunity cost, portfolio roles, exposure/correlation, Candidate false positives/false negatives, and evidence quality.

Output: policy proposal queue; no Core change unless a fundamental contradiction is found.

### Annual — Constitution Audit
Reassess investment objective, risk capacity, philosophy, major behavioral errors, realized opportunity cost, benchmark-relative outcomes, rule effectiveness, and whether any constitutional principle should be amended, merged, or retired.

## 7. Current gaps and proposed actions

### P1 — Add explicit Circle of Competence gate
Before a single-stock position can be high-confidence or enlarged, require a concise statement of: how the business makes money, the key durable advantage, the two or three economic variables that determine long-term cash flow, and what would prove the thesis wrong.

### P2 — Add formal Opportunity Cost gate
Every BUY/ADD/REPLACE proposal must compare expected risk-adjusted attractiveness against: do nothing/cash, a broad ETF alternative, and the best existing portfolio use of capital.

### P3 — Separate cost basis from investment decision
Cost basis remains for accounting and attribution. Decision outputs must not use “return to breakeven” as a thesis or action criterion.

### P4 — Add automatic Observation writeback
Create a governed observation register supporting: security, account, thesis, finding, evidence, confidence, trigger, expiry/review date, next research action, and promotion route.

### P5 — Add Monthly Discipline Review product
Existing Monthly review should explicitly include behavioral/discipline diagnostics, not only attribution and risk.

### P6 — Keep medium-term Candidate windows as diagnostics, not philosophy
20/60/120-day outcome windows are useful for entry-quality and process measurement, but cannot by themselves validate or invalidate long-term business quality. Add quarterly and annual thesis-validation horizons.

### P7 — Adopt simplification as a design objective
New rules should preferably replace/merge existing rules. Annual audit should track rule count, obsolete rules, conflicts, and whether complexity improved decisions.

## 8. What should NOT change now

- Do not alter trade_authority=NONE.
- Do not change any real/simulation holdings from this review.
- Do not alter Candidate membership.
- Do not hard-code a permanent cash percentage or single-stock limit into Core Static.
- Do not imitate Buffett/Duan concentration mechanically.
- Do not promote any proposal above to active policy without explicit user approval and implementation review.

## 9. Proposed acceptance decision

If accepted by the user, the next implementation should be a minimal governance patch that:

1. adds a Conversation Writeback / Observation contract;
2. adds Monthly Discipline Review semantics to Operating Products;
3. adds Circle of Competence + Opportunity Cost + Cost-Basis-Is-Not-Value principles to the appropriate Core Static modules as explicit clarifications (not a wholesale rewrite);
4. preserves current policy maturity states and rule-calibration approval gates;
5. does not change any portfolio state or trading permission.

