# Round 3 — Hong Kong and US limited production

## Purpose

Round 3 converts the accepted FMDL-5 Hong Kong Stock Connect overlay and the accepted FMDL-6 US research stores into a bounded operating cadence. It does not claim that Hong Kong and US coverage is equal to the A-share production chain.

## Hong Kong boundary

- Canonical scope is the 644-security Southbound Stock Connect universe, not all HKEX listings.
- The universe is split into five deterministic weekday buckets. A completed weekly rotation requires all five buckets and at least 600 attempted securities with an 85% success floor.
- A bucket closes only when Yahoo's two independent chart routes agree on a positive close whose `trade_date` exactly equals the requested `as_of` date. A prior-session close is never relabelled as the current session. Holiday or incomplete-session weeks therefore remain observation weeks rather than accepted weekly cycles.
- Market prices remain unofficial free-vendor research evidence. Existing HKEX disclosure, financial, factor, Longlist, Research Object and A/H duplication controls remain authoritative inputs.
- Weekly research proposals can use `RESEARCH_PRIORITY`, `WATCH_FOR_ENTRY`, `DUPLICATION_REVIEW`, `DATA_GAP` or `REMOVE_FROM_RESEARCH_REVIEW`. They cannot change Candidate membership.

## United States boundary

- The accepted Security Master contains 8,785 securities, but Round 3 does not pretend to refresh the whole US market every week.
- Seven benchmark members are observed each operating day: AAPL, MSFT, NVDA, JPM, BRK.B, XOM and QQQ.
- A deterministic 64-security market-data batch and an eight-issuer official SEC retrieval queue rotate each weekday. Five days therefore cover a bounded research cohort, not all 8,785 securities.
- US market buckets use the same exact-session gate and require at least 300 weekly rotation attempts, an 80% rotation success ratio and at least five successful benchmark members before market rotation can close. Successful benchmark quotes alone cannot close a rotation bucket.
- The 7,419-issuer filing mother pool is reconstructed from the accepted filing evidence, issuer backfill queue and FMDL-6 identity lineage. Queue rows without a stored CIK use the truthful route `canonical_issuer_id → accepted representative ticker → official SEC company-ticker mapping → CIK → Submissions and CompanyFacts`.
- Yahoo dual-route market evidence remains `NON_DECISION_GRADE_FALLBACK`. GitHub Hosted Runner is not authorized to claim SEC retrieval success because the accepted FMDL-6 contract records repeatable 403 responses. The workflow therefore emits an eight-issuer queue for ChatGPT web-controlled retrieval from official SEC sources; official evidence remains research-only and does not authorize an investment conclusion.
- Formal cross-sectional ranking, US Candidate promotion, simulation admission and real-account admission remain disabled.

## Operating outputs

Each requested market date creates:

- `CROSS_MARKET_LIMITED_LEDGER_CURRENT.json` — operating cycles and accepted coverage;
- `CROSS_MARKET_LIMITED_RUN_CURRENT.json` — the current batch, capture status and truthful scope statement;
- `CROSS_MARKET_RESEARCH_PROPOSAL_CURRENT.json` — research-only proposals after a completed weekly rotation;
- `ROUND3_SEC_OFFICIAL_RETRIEVAL_QUEUE.json` — the eight-issuer official SEC web-retrieval queue and required resolution route;
- immutable run evidence and hashes under `40_EVIDENCE_AND_LINEAGE/CROSS_MARKET_LIMITED/<run_id>/`.

A date enters the no-op ledger only after completed sessions are captured for both markets. Partial or stale captures are labelled `PARTIAL_RETRYABLE_MISSING_COMPLETED_SESSION` and do not block a controlled retry.

The GitHub workflow publishes only to `automation/cross-market-limited-<run_id>-a<attempt>`. `main` remains the sole Canonical and requires a governed PR.

## Official SEC observer closure

The official web observer writes exactly one `ROUND3_SEC_OBSERVER_INBOX.json` into the matching governed result branch. The permanent workflow then:

1. validates that every success or failure belongs to the original eight-issuer queue;
2. requires a timezone-aware retrieval timestamp, a valid 10-digit CIK, the declared CIK-resolution route and official SEC URLs only;
3. rejects unqueued issuers, duplicate evidence, non-official sources, missing Submissions or CompanyFacts endpoints, any order field above zero and any authority other than `NONE`;
4. writes normalized `ROUND3_SEC_OFFICIAL_RETRIEVAL_RESULT.json` and `ROUND3_SEC_OBSERVER_MANIFEST.json` evidence;
5. updates the weekly ledger, current run and research proposal without touching Candidate, simulation, real-account or decision state.

The result branch still requires a governed Draft PR, full diff review and lineage review before it can update Canonical `main`. The workflow does not retrieve SEC data itself and does not convert official filing evidence into a buy or sell recommendation.

## Acceptance state

- `ROUND3_OPERATING_OBSERVATION`: engineering is installed or fewer than three completed weekly rotations have passed.
- `ROUND3_LIMITED_PRODUCTION_ACCEPTED`: at least three completed weekly rotations pass all completed-session, source-quality, coverage, official-SEC, scope and authority gates, including at least 30 unique official SEC issuer refreshes per accepted week through the ChatGPT web-controlled observer.

This acceptance means the bounded operating cadence works. It does not mean full Hong Kong or US market production, decision-grade Yahoo data, persistent alpha, automatic Candidate mutation or trading authority.

## Permanent firewall

Candidate Pool mutations, simulation mutations, real-account mutations, decision mutations and orders are all zero. `trade_authority=NONE`.
