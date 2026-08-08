# HKCU P3-2 Candidate Pool Promotion

## Objective

P3-2 closes HKCU Phase 3 by converting the **exact accepted P3-1 proposal surface** into the first formal Hong Kong Candidate Current. This is a governed membership transition only. It is not portfolio allocation, simulation admission, real-account admission, order creation or trade authority.

## Frozen P3-1 entry

The accepted P3-1 run is pinned by implementation head, merge SHA, workflow run, artifact digest and exact output hashes. P3-2 must reproduce those accepted hashes before any promotion is valid.

Accepted P3-1 proposal surface:

- `PROPOSE_CORE_CANDIDATE`: 2
- `PROPOSE_WATCH_CANDIDATE`: 68
- `DEFER_RESEARCH_MONITOR`: 2
- `HOLD_RETAINED_INVESTMENT_BLOCKER`: 5
- Total: 77

P3-2 does not rescore, rerank or reinterpret those 77 securities.

## Deterministic promotion mapping

| P3-1 state | P3-2 state | Formal Candidate member |
|---|---|---|
| `PROPOSE_CORE_CANDIDATE` | `HK_CANDIDATE_CORE` | Yes |
| `PROPOSE_WATCH_CANDIDATE` | `HK_CANDIDATE_WATCH` | Yes |
| `DEFER_RESEARCH_MONITOR` | `RESEARCH_MONITOR` | No |
| `HOLD_RETAINED_INVESTMENT_BLOCKER` | `BLOCKER_MONITOR` | No |

No discretionary override, fixed Top-N, weighted rescoring, neutral fill or Core/Watch relabel is permitted in P3-2.

## Formal Current

The first formal HK Candidate Current contains 70 members:

- Core: 2
- Watch: 68

The remaining seven securities are preserved outside formal Candidate membership:

- Research Monitor: 2
- Blocker Monitor: 5

All 77 entry securities are represented in the append-only first-promotion ledger, so no security can disappear between P3-1 and P3-2.

## Governance boundary

P3-2 is the first gate in the HKCU program authorized to mutate **Hong Kong Candidate membership**. That authority is narrowly constrained to the exact accepted P3-1 mapping.

P3-2 explicitly does **not** authorize:

- A-share Candidate mutation;
- simulation-book admission or sizing;
- real-account admission or sizing;
- portfolio allocation;
- order generation;
- brokerage execution;
- trade authority.

`trade_authority=NONE` remains unchanged.

## Publication surface

Canonical Current is published under:

`outputs/hk_candidate/current/`

with:

- `HK_CANDIDATE_CURRENT.csv` — 70 formal members and their Core/Watch tier;
- `HK_CANDIDATE_NONMEMBER_MONITORS.csv` — 2 Defer + 5 Blocker names outside Candidate membership;
- `HK_CANDIDATE_PROMOTION_LEDGER.csv` — all 77 first-promotion transitions;
- `HK_CANDIDATE_DECISION.json` — gate decision and counts;
- `HK_CANDIDATE_QUALITY_REPORT.json` — independent quality assertions;
- `HK_CANDIDATE_MANIFEST.json` — deterministic file hashes.

The Current files are generated from the pinned P3-1 evidence and are independently rebuilt and byte-tied during PR acceptance; they are not hand-edited membership lists.

## Acceptance

P3-2 passes only if:

1. accepted P3-1 exact hashes reproduce;
2. all 77 entry securities are accounted for exactly once;
3. exactly 70 formal Candidate members are produced from the two admissible P3-1 proposal states;
4. Core/Watch states are preserved without relabeling;
5. Defer and Blocker states remain outside Candidate membership;
6. committed Current is byte-identical to the independently rebuilt P3-2 output;
7. A-share Candidate, simulation, real account and orders remain untouched;
8. `trade_authority=NONE`.

Successful P3-2 closes Phase 3 and advances only to `P4_0_PORTFOLIO_FIT_CONTRACT`.
