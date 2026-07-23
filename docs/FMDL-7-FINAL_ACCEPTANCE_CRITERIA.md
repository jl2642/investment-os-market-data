# FMDL-7-FINAL Acceptance Criteria

## Required entry

- FMDL-7E Release 53 accepted;
- Canonical Release 9 identity and package hash match;
- FMDL-7-0 through 7E form strict Release sequence 48–53;
- A-share FMDL-1 through 4, Hong Kong Stock Connect FMDL-5 and US Research Adapter FMDL-6 remain accepted with `trade_authority = NONE`.

## Required acceptance

1. Three markets appear in one capability registry without forcing symmetric capabilities.
2. A-share is accepted as the primary full research/decision/state path, subject to freshness and human authority.
3. Hong Kong Stock Connect is accepted as an immutable governed research overlay, with no automatic admission.
4. US equities are accepted as a research adapter only; formal Candidate, simulation, brokerage, real-account and order gates remain closed.
5. Release 9 ZIP is present in GitHub, byte-identical to its identity record and openable.
6. File Library evidence is represented honestly: Pointer and Start Here are discoverable, user has attested cleanup, and binary search visibility is not overclaimed.
7. The 2026-07-20 state remains LKG and is not promoted to Current.
8. No common cross-market score, global rank, ticker-only identity, neutral fill or silent substitution is permitted.
9. Candidate, simulation and real-account state domains remain separate, with the human user as the sole investment authority.
10. Scheduled operations, staleness controls, deterministic replay, LKG recovery and clean-room restore remain accepted.
11. A current handoff document supports independent new-chat audit and targeted iteration.
12. All thirty final gates pass, all fourteen failure injections are rejected, all 640 logical shards are deterministic, and all mutation/order counts remain zero.

## Required exit

`FMDL7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE_ACCEPTED`

## Post-exit mode

`POST_FMDL7_OPERATING_OBSERVATION_AND_TARGETED_ITERATION`

No new numbered development phase is opened automatically. A real defect, operating observation or accepted new requirement is required.
