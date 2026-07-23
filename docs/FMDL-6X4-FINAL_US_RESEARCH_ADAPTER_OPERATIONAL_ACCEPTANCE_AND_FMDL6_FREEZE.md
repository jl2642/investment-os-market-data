# FMDL-6X4-FINAL — US Research Adapter Operational Acceptance & FMDL-6 Freeze

## Objective

Reconcile the accepted FMDL-6X1, FMDL-6X2, FMDL-6X3 and FMDL-6X4 operating states into one recoverable US research-adapter baseline, freeze the completed FMDL-6 architecture and open only the FMDL-7 cross-market/full-system final acceptance gate.

## Authoritative component chain

The accepted component chain is:

`FMDL-6X1-FINAL Release 29`
→ `FMDL-6X2-FINAL Release 35`
→ `FMDL-6X3-FINAL Release 41`
→ `FMDL-6X4-A Release 42`
→ `FMDL-6X4-B Release 43`
→ `FMDL-6X4-C Release 44`
→ `FMDL-6X4-D Release 45`
→ `FMDL-6X4-E Release 46`
→ `FMDL-6X4-FINAL Release 47`.

Every accepted component remains immutable. FINAL reconciles and freezes the chain; it does not rewrite upstream releases.

## Accepted operational capabilities

1. Source, cost, execution-route and full-build contracts.
2. US Security Master, identity, listing-history, market-reference and SEC stores with explicit coverage boundaries.
3. Research readiness, financial normalization, factor/risk, sector/peer/benchmark, screening and Research Card production.
4. Public Equity Investing workflow-contract mapping.
5. Evidence registration and append-only Security Evidence Ledgers.
6. Candidate-graduation rules, Decision Interface, human-approval states and guardrails.
7. Zero-exposure simulation controls, shadow-only attribution and failure recovery.
8. A-share, Hong Kong Stock Connect and US dimension-level comparability plus the operating runbook.

Operational acceptance proves architecture, lineage, controls, publication and recoverability. It does not prove persistent alpha or authorize an investment action.

## Frozen boundaries

FMDL-6X4-FINAL freezes the following boundaries:

- no ticker-only identity matching;
- no unsupported accounting conversion;
- no forced common cross-market factor score;
- no cross-market global security rank;
- no neutral fill or silent source substitution;
- no automatic Candidate Pool promotion;
- no formal US simulation position;
- no real-account or brokerage channel;
- no automatic order generation;
- `HUMAN_USER` remains the only graduation and simulation authority;
- `trade_authority = NONE`.

The US shadow attribution lane remains research-sandbox evidence only. It is not formal portfolio performance and is not an investment recommendation.

## Operating posture after acceptance

After acceptance:

- FMDL-6 is `COMPLETE_AND_FROZEN`;
- the US research adapter is `OPERATIONALLY_ACCEPTED_AND_FROZEN`;
- Daily, Weekly, Monthly, Quarterly and Event-driven operating controls remain active as frozen runbook definitions;
- data backfills or workflow executions require a separately governed operating run and may not alter the frozen contract silently;
- any failed new output must fail closed and restore from the accepted immutable Release or Last Known Good pointer;
- the only open development gate is FMDL-7.

## Completion boundary

This stage does not:

- execute the fourteen Public Equity Investing workflows;
- create a completed workflow artifact;
- promote a US security into the Investment OS Candidate Pool;
- create a formal simulation position;
- issue an investment recommendation;
- connect a broker or create an order;
- claim complete historical, valuation, peer or decision-grade market coverage;
- claim future or persistent excess return.

## Required exit

`FMDL6X4_FINAL_US_RESEARCH_ADAPTER_OPERATIONAL_ACCEPTANCE_AND_FMDL6_FREEZE_ACCEPTED`

## Next gate

`FMDL-7_CROSS_MARKET_AND_FULL_SYSTEM_FINAL_OPERATIONAL_ACCEPTANCE`
