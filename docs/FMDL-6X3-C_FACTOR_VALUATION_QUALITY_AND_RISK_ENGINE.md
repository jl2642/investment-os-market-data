# FMDL-6X3-C — Factor, Valuation, Quality & Risk Engine

This stage converts accepted FMDL-6X3-A/B and FMDL-6X2-D inputs into an auditable factor-domain baseline without overstating data readiness.

## Production boundaries

- Quarterly SEC-derived quality observations are allowed only for securities opened by FMDL-6X3-A and normalized by FMDL-6X3-B.
- A quarterly quality composite may be produced only as a three-security, non-sector-neutral sandbox. It is not a formal ranking or candidate signal.
- Yahoo-derived momentum, liquidity and risk observations remain `NON_DECISION_GRADE_FALLBACK` and sandbox-only.
- Valuation observations remain empty while TTM and annual inputs are unavailable. Quarterly annualization is forbidden.
- A global multi-factor score remains empty until FMDL-6X3-D provides sector, industry, peer and benchmark context.
- Missing observations are blocked or queued; no neutral factor value is inserted.

## Output domains

1. Security Factor Status
2. Quality Factor
3. Market Factor
4. Risk Factor
5. Valuation Factor

The five domains are deterministically partitioned into 64 buckets each. Review queues preserve market-history gaps, decision-grade market-data upgrades, quality comparability gaps, insufficient windows and valuation input gaps.

## Authority

This stage has no authority to modify the Investment OS Candidate Pool, simulation portfolio, real account or orders. `trade_authority = NONE`.
