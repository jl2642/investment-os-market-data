# HKCU P5A｜Phase 5 Contract & Entry Freeze

## Purpose

P5A is the first and only planning-freeze gate for the HK Stock Connect Phase 5 migration layer. Its job is to freeze the complete P5A-P5E business sequence and preserve the accepted P4-4 portfolio proposals as immutable Phase 5 entry evidence before any Pre-trade Memo, user decision, manual execution support, reconciliation or Current writeback.

P5A is not an investment-selection rerun and is not a trading gate.

## Authoritative entry

Phase 5 may enter only from accepted P4-4:

- P4-4 status: `PASS_P4_4_PORTFOLIO_PROPOSAL_REVIEW`;
- Phase 4 status: `PHASE_4_CLOSED`;
- no additional P4 business subphase is allowed;
- REAL preferred proposal: `REAL_CONSERVATIVE`, 5% HK sleeve, 4 securities;
- SIMULATION preferred observation proposal: `SIM_BALANCED`, 15% HK sleeve, 9 securities;
- preferred proposal count: 2;
- allocation count: 13;
- `trade_authority=NONE`.

P5A freezes the P4-4 Decision, Preferred Proposals and Proposal Allocations together with hashes of the REAL and SIMULATION Current state files. Later Phase 5 work must either use this entry surface or explicitly fail the gate and repair the evidence; it may not silently replace the entry proposal.

## Frozen Phase 5 roadmap

The Phase 5 business sequence is exactly five gates.

### P5A｜Phase 5 Contract & Entry Freeze

Freeze the roadmap, P4-4 entry proposal, Current hashes, permissions and stop conditions. P5A may produce only entry-freeze, gate-register and lineage-manifest evidence.

### P5B｜REAL Pre-trade Memo

Prepare the REAL-account Pre-trade Memo for the frozen 5% four-security proposal. The memo must cover Evidence, Thesis, valuation, portfolio fit, funding source, maximum loss, alternatives, triggers, exit and review date. It may conclude APPROACH_NOT_READY, DEFER, MODIFY or recommend proceeding to user decision. It cannot authorize execution.

P5B begins at `RESEARCH_ONLY` and can exit only to `USER_DECISION_REQUIRED` when the memo is complete.

### P5C｜User Decision Gate

Record the user's explicit REAL decision as APPROVE, REJECT, MODIFY or DEFER. Separately record whether the SIMULATION observation proposal may be activated. A technical PASS, memo recommendation or earlier BUY_PROPOSAL must never substitute for user approval.

Even after explicit approval, the permission label is `USER_APPROVED_MANUAL_EXECUTION`; system `trade_authority` remains `NONE`.

### P5D｜Manual Staged Execution Support

Only after explicit user approval, prepare a manual staged-execution checklist such as capital amount, board-lot rounding, batch sequence and execution order. The system does not connect to a broker, create broker orders, submit trades or infer fills.

### P5E｜Reconciliation, Atomic Writeback & Observation

For REAL, only user-supplied actual execution facts may enter reconciliation and governed atomic writeback. For SIMULATION, writeback requires an explicit activation record. Failed validation preserves LKG. A proposal, memo, approval or checklist is never evidence that a trade occurred.

A passing P5E closes the HKCU special development line into `HKCU_SPECIAL_DEVELOPMENT_COMPLETE_OPERATING_OBSERVATION`.

## Planning governance correction

The Phase 4 subgate sequence was not fully frozen at Phase 4 inception, which allowed P4-2, P4-3 and P4-4 numbering to emerge incrementally even though the underlying portfolio work remained directionally valid.

P5A prevents that planning defect from recurring:

- frozen business gates are exactly `P5A`, `P5B`, `P5C`, `P5D`, `P5E`;
- no P5F or later Phase 5 business gate is authorized;
- no HKCU Phase 6 is authorized;
- `P5X-R` repair subgates are allowed only for implementation or evidence defects inside the already-frozen objective;
- a repair gate may not create a new business objective, bypass a prior gate, expand authority or silently change the Phase 5 entry proposal.

## Portfolio and cash rules

Phase 5 continues CORE_STATIC governance:

- ranking or weighted score cannot authorize real capital;
- simulation results cannot authorize real capital;
- REAL-account cash is an execution balance, not a fixed strategic cash bucket;
- funding source, maximum loss, correlations, Look-through, alternatives and exit/review conditions must remain explicit;
- P4-4's 5% REAL proposal is an entry proposal, not an obligation to buy. P5B may reject, defer or modify it based on current valuation/evidence.

## P5A boundary

P5A does not:

- produce a Pre-trade Memo;
- record user approval or rejection;
- prepare a manual execution checklist;
- write target positions;
- mutate Candidate membership;
- mutate REAL Current;
- mutate SIMULATION Current;
- create orders;
- connect to a broker;
- infer execution;
- grant trade authority.

`trade_authority=NONE` throughout.

## Acceptance

P5A passes only if all of the following are independently validated:

- accepted P4-4 and closed Phase 4 are the entry state;
- P5A-P5E is the exact five-gate business sequence;
- P5F+ and Phase 6 remain unauthorized;
- entry proposal count = 2;
- entry allocation count = 13;
- REAL entry = 5% / 4 securities;
- SIMULATION entry = 15% / 9 securities;
- frozen proposal/allocation rows match the rebuilt P4-4 surface;
- Current and entry-input hashes are recorded;
- no Current/Candidate mutation, no target writeback, no Pre-trade Memo, no user confirmation, no manual checklist and no orders occur;
- `trade_authority=NONE`.

On PASS, the only next business gate is `P5B_REAL_PRETRADE_MEMO`.
