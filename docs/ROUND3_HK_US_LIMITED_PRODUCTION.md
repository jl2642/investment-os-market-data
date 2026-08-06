# Round 3 — Hong Kong and US limited production

## Purpose

Round 3 converts the accepted FMDL-5 Hong Kong Stock Connect overlay and the accepted FMDL-6 US research stores into a bounded operating cadence. It does not claim that Hong Kong and US coverage is equal to the A-share production chain.

## Hong Kong boundary

- Canonical scope is the 644-security Southbound Stock Connect universe, not all HKEX listings.
- The universe is split into five deterministic weekday buckets. A completed weekly rotation requires all five buckets and at least 600 attempted securities with an 85% success floor.
- Market prices remain unofficial free-vendor research evidence. Existing HKEX disclosure, financial, factor, Longlist, Research Object and A/H duplication controls remain authoritative inputs.
- Weekly research proposals can use `RESEARCH_PRIORITY`, `WATCH_FOR_ENTRY`, `DUPLICATION_REVIEW`, `DATA_GAP` or `REMOVE_FROM_RESEARCH_REVIEW`. They cannot change Candidate membership.

## United States boundary

- The accepted Security Master contains 8,785 securities, but Round 3 does not pretend to refresh the whole US market every week.
- Seven benchmark members are observed each operating day: AAPL, MSFT, NVDA, JPM, BRK.B, XOM and QQQ.
- A deterministic 64-security market-data batch and an eight-issuer official SEC batch rotate each weekday. Five days therefore cover a bounded research cohort, not all 8,785 securities.
- Yahoo dual-route market evidence remains `NON_DECISION_GRADE_FALLBACK`. SEC submissions and company facts are official research evidence, but neither source alone authorizes an investment conclusion.
- Formal cross-sectional ranking, US Candidate promotion, simulation admission and real-account admission remain disabled.

## Operating outputs

Each valid market date creates:

- `CROSS_MARKET_LIMITED_LEDGER_CURRENT.json` — append-only operating cycles and coverage;
- `CROSS_MARKET_LIMITED_RUN_CURRENT.json` — the current batch and truthful scope statement;
- `CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json` — research-only proposals after a completed weekly rotation;
- immutable run evidence and hashes under `40_EVIDENCE_AND_LINEAGE/CROSS_MARKET_LIMITED/<run_id>/`.

The GitHub workflow publishes only to `automation/cross-market-limited-<run_id>-a<attempt>`. `main` remains the sole Canonical and requires a governed PR.

## Acceptance state

- `ROUND3_OPERATING_OBSERVATION`: engineering is installed or fewer than three completed weekly rotations have passed.
- `ROUND3_LIMITED_PRODUCTION_ACCEPTED`: at least three completed weekly rotations pass all source, scope and authority gates.

This acceptance means the bounded operating cadence works. It does not mean full Hong Kong or US market production, decision-grade Yahoo data, persistent alpha, automatic Candidate mutation or trading authority.

## Permanent firewall

Candidate Pool mutations, simulation mutations, real-account mutations, decision mutations and orders are all zero. `trade_authority=NONE`.
