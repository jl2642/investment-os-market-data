# HKCU P3-0 Candidate Graduation Contract

## Objective

P3-0 freezes the graduation contract that will govern whether a P2B research-ready Hong Kong Stock Connect security may later be proposed for the formal HK Candidate Pool.

This is a **contract gate only**. It does not assess the 72 eligible securities, graduate any name, mutate Candidate state, open a simulation position, change the real account, create an order or grant trade authority.

## Entry lineage

The authoritative upstream is the accepted `HKCU-P2B-FINAL` contract as of 2026-08-07:

- 77 securities in the accepted P2B Final cross-sectional surface;
- 72 securities in `READY_FOR_P3_CONTRACT_EVALUATION_WITH_CONFIDENCE_CAP`;
- 5 securities in `HOLD_RETAINED_INVESTMENT_BLOCKER`;
- the five frozen blocker names are Yue Yuen (`00551`), Brilliance China (`01114`), Shenzhou International (`02313`), Topsports (`06110`) and JF SMARTINVEST (`09636`).

P3-0 preserves that lineage exactly. The five blocked names cannot be silently moved into the Phase-3 evaluation-eligible set.

## Graduation philosophy

Candidate graduation is intentionally different from P2A ranking and from portfolio allocation.

The contract therefore prohibits:

- a new weighted composite alpha score;
- neutral filling of missing evidence;
- automatic waivers;
- an arbitrary fixed top-N Candidate count;
- treating P2A rank as graduation authority;
- treating missing consensus as bearish;
- treating A/H discount as alpha or as a standalone graduation reason.

All applicable hard rules must pass. Confidence caps may route a security to Watch rather than automatically rejecting it, provided the cap is explicit, bounded and not a substantive investment blocker.

## The 12 graduation rules

### Hard rules

1. **Accepted P2B Final lineage** — the security must come from the accepted 77-name P2B Final surface without re-scoring.
2. **No retained investment blocker** — an unresolved substantive blocker is a hard hold.
3. **Current investability and buy eligibility** — publication eligibility, Stock Connect/buy eligibility and investability must remain valid.
4. **Decision-grade market and factor freshness** — stale decision inputs fail closed.
5. **Transaction/tax evidence complete** — execution frictions must remain explicitly evidenced; they are not alpha.
6. **Three company dimensions synthesized** — Governance/Value-Trap, Earnings-Expectation Revision and Catalyst must each have an accepted decision synthesis with no `RESEARCH_REQUIRED` residue.
7. **Governance/value-trap not substantively blocked** — unresolved material governance, related-party, auditor, control or value-trap risk prevents graduation.
8. **Earnings risk not substantively blocked** — a current material negative profit warning or equivalent unresolved earnings event prevents graduation.
9. **Liquidity and tradability accepted** — existing HKCU/P2A liquidity eligibility must remain valid; Phase 3 cannot lower the threshold merely to force a pass.

### Decision rules

10. **Valuation support explicit** — each assessment must state an interpretable security-specific valuation support state. A/H spread alone is insufficient, and missing valuation cannot be neutral-filled.
11. **Thesis, falsifier and monitor trigger explicit** — each assessment must have an investment thesis, principal downside/falsifier and at least one evidence-linked monitor trigger.
12. **Cross-listing and duplicate exposure review** — where A/H or an existing cross-market exposure exists, the assessment must explicitly address duplicate exposure and relative-value context.

## Assessment states for P3-1

P3-1 will be **assessment only** and may produce four proposed states:

- `PROPOSE_CORE_CANDIDATE` — all hard rules pass and no unresolved material confidence cap prevents core designation;
- `PROPOSE_WATCH_CANDIDATE` — all hard rules pass, but a bounded confidence cap, valuation uncertainty or event-timing condition warrants Watch status;
- `DEFER_RESEARCH_MONITOR` — no substantive blocker exists, but required decision fields are incomplete or not decision-grade;
- `HOLD_RETAINED_INVESTMENT_BLOCKER` — a substantive blocker remains.

No P3-1 state itself changes the formal Candidate Pool.

## Promotion boundary

Formal Candidate promotion is deliberately separated into `P3_2_CANDIDATE_POOL_PROMOTION`.

That later promotion must be an audited state transition. Promotion does not authorize simulation, real-account trading or orders and does not change `trade_authority=NONE`.

## Downgrade and reassessment

Any later Candidate must be reassessed when a material eligibility, freshness, evidence, governance, earnings, thesis or valuation condition changes. Removal must be logged rather than silently overwriting prior state.

## P3-0 acceptance

PASS requires:

- exact binding to the 77 / 72 / 5 P2B Final state;
- exact preservation of the five retained blockers;
- 12 explicit graduation rules;
- no score, neutral-fill, arbitrary top-N or automatic waiver mechanism;
- zero formal Candidate graduations;
- zero Candidate, Simulation, Real Account and order mutations;
- `trade_authority=NONE`.

PASS advances only to `P3_1_CANDIDATE_GRADUATION_ASSESSMENT`.
