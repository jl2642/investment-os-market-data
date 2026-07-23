# FMDL-6X4-C｜Candidate Graduation, Decision Interface & Guardrails

## Objective

Create a deterministic and auditable graduation interface that prevents research-priority status, workflow readiness, investment recommendations, Candidate Pool membership and trade authority from being conflated.

## Accepted first baseline

- Six issuer securities are assessed for graduation; QQQ remains a reference instrument and is not eligible for issuer-candidate graduation.
- Every applicable graduation rule must pass. There is no weighted score, neutral fill or partial-pass promotion.
- At least two registered and QC-passed workflow outputs are required before human review, including a source-backed issuer baseline and a decision-grade financial output or equivalent.
- Decision-grade market data, formal valuation, formal peer comparability, user-confirmed investment context, thesis/falsifiers and explicit human approval are mandatory.
- Current registered workflow output count is zero, valuation readiness is zero, formal peer count is zero and market data remains non-decision-grade.
- Therefore all six issuers remain blocked and QQQ remains not applicable. No graduation event, investment recommendation, Candidate Pool mutation, simulation action or trade authority is emitted.

## Decision interface separation

The interface maintains separate fields for research priority, company-thesis status, security-thesis readiness, candidate-graduation status, human approval, investment recommendation, Candidate Pool status, simulation status and trade authority.

## Downgrade and withdrawal

Any future approved candidate must be downgraded or withdrawn when registered outputs fail QC or are withdrawn, decision-grade data becomes stale, valuation or peer comparability is invalidated, material evidence conflicts remain unresolved, a thesis falsifier triggers, or human approval is withdrawn.

## Completion boundary

This stage accepts the rule registry, assessments, decision interface, approval state machine and guardrails. It does not approve a candidate, mutate the Candidate Pool, produce an investment recommendation, open simulation, connect brokerage or create an order.
