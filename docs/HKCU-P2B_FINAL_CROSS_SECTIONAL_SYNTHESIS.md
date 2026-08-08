# HKCU P2B Final Cross-sectional Synthesis

## Objective

This gate converts the four accepted P2B-E2 security-level decision windows into one governed 77-security cross-sectional research surface. It is the closing gate of P2B research synthesis, not a Candidate graduation gate.

## Accepted lineage

The workflow rebuilds and independently validates P2A, P2B-E1 and P2B-E2 S1-S4. The resulting surface must contain exactly 77 securities and 231 company-specific dimensions. P2A rank and its screening score are preserved as upstream screening context; no new composite alpha score is created.

P2A currently publishes the English display name as `official_security_name_en`. P2B Final normalizes that canonical field to the downstream `security_name` display field and records its source column. The build fails closed if no non-empty accepted P2A name field is available.

## Cross-sectional decision semantics

A security is either:

- `READY_FOR_P3_CONTRACT_EVALUATION_WITH_CONFIDENCE_CAP`; or
- `HOLD_RETAINED_INVESTMENT_BLOCKER`.

The five accepted retained-blocker securities are Yue Yuen (`00551`), Brilliance China (`01114`), JF SMARTINVEST (`09636`), Shenzhou International (`02313`) and Topsports (`06110`). The other 72 securities are research-ready for the Phase-3 graduation contract, not formal Candidates.

Evidence-balance labels are descriptive only. Missing analyst consensus remains an evidence-confidence limit rather than a bearish inference. Cross-dimension event deduplication remains in force.

## Common execution evidence

All 77 securities retain the accepted P2B-E1 transaction/tax evidence. This is execution context and is not alpha.

## A/H relative value

P2B-E1 confirmed 13 same-issuer A/H pairs. P2B Final completes the previously deferred numeric comparison only when A price, H price and FX are synchronized to 2026-08-07.

- A close: canonical `outputs/current/DAILY_MARKET_SNAPSHOT.csv` as of 2026-08-07. P2B Final explicitly maps registry exchange identifiers `SSE/SZSE` to the snapshot suffixes `.SH/.SZ` and fails on any unsupported exchange.
- H close: exact 2026-08-07 unadjusted daily close. Retrieval uses a governed AkShare provider failover across Sina `stock_hk_daily`, Tencent A/H `stock_zh_ah_daily`, and Eastmoney `stock_hk_hist`. The actual successful provider is recorded per row.
- FX: SAFE RMB central parity for HKD on 2026-08-07 retrieved through AkShare, converted from RMB per 100 HKD to CNY per HKD.
- Formula: `A_close_CNY / (H_close_HKD * CNY_per_HKD) - 1`.

Provider failover does not relax the data contract. A provider is acceptable only if it returns exactly the required 2026-08-07 observation. Failure of one or all providers never permits substitution of another date.

A positive value means the H share trades at a discount to the A share on the synchronized conversion basis; a negative value means an H-share premium. This is relative-value context only, not an alpha score and not a graduation rule in P2B.

The independent validator freezes the same 13 A/H pairs accepted in the 2026-08-07 E1 registry, checks exact synchronized dates and numeric formula tie-out, and rejects any unrecognized H-price provider.

## Acceptance boundary

PASS requires exact 77/231 coverage, 72/5 decision states, 77 transaction/tax completions, 13/13 synchronized A/H observations, zero alpha scores and zero protected-state mutations. Formal HK Candidate graduation remains prohibited.

PASS advances to `P3_0_CANDIDATE_GRADUATION_CONTRACT`.

`trade_authority=NONE`.
