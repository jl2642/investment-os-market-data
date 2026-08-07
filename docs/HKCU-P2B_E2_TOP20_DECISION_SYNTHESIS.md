# HKCU P2B-E2 Top20 Decision Synthesis (S1)

## Purpose

S1 is the decision-synthesis closeout for P2A ranks 1-20 after accepted D1-D4 Company Evidence Deepening. It converts the 60 company-specific research dimensions into one auditable security-level research-readiness state.

S1 is **not** Candidate graduation and does not create an alpha score.

## Authoritative lineage

The pipeline rebuilds accepted D4. D4 recursively rebuilds D3, D2 and D1, so the synthesis consumes one canonical lineage rather than copied intermediate spreadsheets.

The Top20 surface contains exactly three dimensions per security:

- Governance / Value Trap
- Earnings Expectation Revision
- Catalyst

D3 and D4 resolutions override earlier D2 blocker semantics where deeper primary evidence changed the conclusion. Explicit negative signals in upstream `EVIDENCE_COMPLETE` rows are independently fail-closed so a completed row cannot hide adverse evidence merely because it was not part of D2's Partial-only queue.

## Decision states

- `ADVANCE_TO_P2B_CROSS_SECTIONAL_SYNTHESIS_WITH_CONFIDENCE_CAP`: research can proceed to the cross-sectional P2B comparison layer, but evidence limitations remain visible.
- `HOLD_RETAINED_INVESTMENT_BLOCKER`: a substantive adverse issuer signal remains unresolved and prevents any later Candidate graduation until its trigger is reviewed.

The existing P2A rank is preserved for lineage and is **not** re-scored in S1.

## Accepted expected state

- 20 securities / 60 company-specific dimensions;
- 18 advance with confidence caps;
- Yue Yuen (`00551`) and Brilliance China (`01114`) remain held on current negative earnings blockers;
- no alpha score;
- no formal HK Candidate graduation;
- no A-share Candidate, Simulation, Real Portfolio or order mutation;
- `trade_authority=NONE`.

## Next gate

`P2B_E2_RANKS21_40_PARTIAL_SYNTHESIS`

This reuses the accepted Top20 method on the next tranche rather than opening another Top20 evidence-chasing loop.
