# HKCU P3-1 Candidate Graduation Assessment

## Objective

P3-1 applies the accepted `P3-0 Candidate Graduation Contract` to the full accepted P2B Final surface. It is an **assessment-only** gate. It may propose Candidate states, but it may not mutate the formal Candidate Pool, simulation, real account, orders or trade authority.

## Entry state

The accepted entry surface is fixed at:

- 77 P2B Final securities;
- 72 securities eligible for graduation assessment;
- 5 retained investment blockers: Yue Yuen (`00551`), Brilliance China (`01114`), Shenzhou International (`02313`), Topsports (`06110`) and JF SMARTINVEST (`09636`);
- 12 graduation rules from P3-0.

The workflow rebuilds and independently validates P2B Final before applying P3-1. If P2B Final no longer reproduces its accepted 77/72/5 state, P3-1 fails closed.

## Assessment architecture

P3-1 materializes one security assessment and twelve rule assessments per security.

Hard rules cover accepted lineage, blocker status, current investability/buy eligibility, decision-grade freshness, transaction/tax evidence, the three company dimensions, governance risk, earnings risk and accepted liquidity/tradability.

Decision rules cover:

1. explicit valuation support;
2. an investment thesis, principal falsifier and monitor trigger tied to accepted evidence;
3. A/H cross-listing and duplicate-exposure review where applicable.

No weighted composite score is created. Missing consensus remains an information limitation rather than a bearish signal. A/H relative value is context only and cannot satisfy the valuation rule by itself.

## Freshness semantics

P3R04 reuses the accepted HKCU / FMDL-5E freshness contract instead of inventing a stricter Phase-3 rule. The accepted FMDL-5E maximum price age is seven calendar days. P3-1 therefore requires:

- HKCU `freshness_status=CURRENT`;
- eligibility as-of equal to the frozen assessment date;
- accepted market and factor observations to be non-future and within the seven-calendar-day freshness window.

An accepted factor observation from the immediately preceding session may therefore remain decision-grade. P3-1 does **not** silently require the factor timestamp to equal the assessment date when the upstream freshness contract did not require that.

## Valuation semantics

P3-1 uses only accepted earnings-yield, P/E and dividend-yield context from the canonical HKCU surface.

- `SUPPORTIVE`: positive earnings-yield or dividend-yield support exists;
- `LIMITED`: a positive P/E observation exists but direct yield support is absent;
- `MISSING`: no accepted valuation observation is available;
- `ADVERSE_OR_UNUSABLE`: valuation fields exist but do not provide positive support.

Missing or adverse valuation cannot be neutral-filled into a pass. A/H discount is never used as a substitute for missing valuation support.

## Confidence-cap semantics

P3-1 preserves the evidence semantics accepted in P2B instead of reclassifying every uncertainty as a blocker.

- `TARGETED_DEEPENING_REQUIRED` is a material unresolved evidence gap and therefore defers Candidate proposal until the targeted gap is resolved.
- `LIMITED_CONFIDENCE` is a non-blocking P2B evidence limitation. It becomes a bounded Watch confidence cap, not an automatic Defer.
- `CONFIDENCE_CAP_MONITOR` is also a bounded Watch cap.

This distinction is necessary because P3-0 explicitly states that a confidence cap is not automatic rejection and that Watch status may carry bounded uncertainty.

## Proposal routing

The only P3-1 proposal states are:

- `PROPOSE_CORE_CANDIDATE`
- `PROPOSE_WATCH_CANDIDATE`
- `DEFER_RESEARCH_MONITOR`
- `HOLD_RETAINED_INVESTMENT_BLOCKER`

Routing is deterministic and has no fixed target count.

A Core proposal requires all applicable rules to pass, supportive valuation, at least one positive company dimension, no negative company dimension, zero targeted-deepening requirements and zero bounded confidence caps.

A Watch proposal requires all applicable hard and decision rules to pass but permits bounded `LIMITED_CONFIDENCE` / `CONFIDENCE_CAP_MONITOR` uncertainty, mixed/neutral evidence, event timing or limited valuation support.

A Defer state is used where no retained blocker exists but a hard/decision rule fails or a `TARGETED_DEEPENING_REQUIRED` gap remains.

A retained P2B Final blocker is preserved exactly and cannot be waived by Phase 3.

## Acceptance boundary

P3-1 must assess all 77 securities and materialize 924 Security × Rule rows. The five retained blocker securities must remain blocked. Proposal-state counts are an output of the evidence and rule application; they are not hard-coded beforehand.

Even a `PROPOSE_CORE_CANDIDATE` or `PROPOSE_WATCH_CANDIDATE` is not formal Candidate Pool membership. Formal promotion requires the separate `P3_2_CANDIDATE_POOL_PROMOTION` gate.

P3-1 therefore requires:

- formal Candidate graduations = 0;
- Candidate Pool mutations = 0;
- Simulation mutations = 0;
- Real Account mutations = 0;
- Orders = 0;
- `trade_authority=NONE`.
