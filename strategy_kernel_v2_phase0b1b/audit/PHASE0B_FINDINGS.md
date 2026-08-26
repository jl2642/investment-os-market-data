# Phase 0B — Current Main Rule Audit Findings

Audit main: `5c5df9082688f65332c79fef3b9cbfa893a06908`  
Coverage: all 11 Core Static modules; 62 semantic rules mapped in the working audit package.

## Finding 1 — Do not treat Core Static as one strategy block

Current Core Static mixes durable investment principles, underwriting/valuation rules, portfolio-capital-allocation rules, evidence standards, state/accounting governance, workflow/publication rules and execution safety. The correct first move is separation of responsibility, not wholesale tightening or loosening.

## Finding 2 — Preserve the safety substrate

Canonical authority, PIT evidence, Real/Simulation separation, user confirmation, atomic writeback, lineage, publication rollback and `orders=0 / trade_authority=NONE` are not alpha rules. They protect economic truth and remain unchanged.

## Finding 3 — Economic judgment is distributed across 00/03/04/06

The system already contains business-quality, circle-of-competence, valuation-scenario, thesis/falsifier, Candidate and opportunity-cost concepts. What is missing is a single audit-ready object that represents their current economic state without converting workflow completion into investment merit.

## Finding 4 — Candidate has an unresolved dual role

Candidate currently routes research attention and also sits near decision promotion. Phase 0B does not declare this wrong. Phase 3 must test whether separating attention state from capital-comparability state reduces false negatives without increasing false positives.

## Finding 5 — Core 08 already demands the right learning tests

The legacy constitution already calls for process/outcome separation, false-positive/false-negative review, replay, current-portfolio impact testing and rule simplification. Strategy Kernel v2 should operationalize those requirements rather than add another layer of permanent gates.

## Current-state diagnostics

- A Candidate Current: `2026-07-24_CLOSE`; Core=2, Research Queue=33, Shadow=38, ready=0; continuous engine incomplete.
- Candidate Dynamic: `2026-08-07_CLOSE`; one completed weekly cycle; admission/mutation counts=0.
- D2: as-of 2026-08-18; 000719 and 002039 complete/no decision; 301215 evidence-gap hold; manual trigger=false.
- Real Canonical marks: `2026-08-14`; 7 holdings; broker_verified=false; 605090 weight about 43.89% of real total assets.
- Simulation Canonical marks: `2026-08-14`; 601138 = 600 shares, RMB66.19 mark, about 3.89% of simulation assets; accepted action remains HOLD/NO_ADD/NO_TRADE.
- HKEX:00669 accepted BUY REVIEW remains WATCH/NO_TRADE; price bands are research gates only.

Candidate freshness is therefore a diagnostic fact, not proof of missed alpha. Causality is deferred to point-in-time replay.

## Explicit non-conclusions

This audit does **not** conclude that current gates are too strict, that more trading is desirable, that Buffett/段永平 rules should be hard-coded, or that recent HOLD outcomes were wrong.
