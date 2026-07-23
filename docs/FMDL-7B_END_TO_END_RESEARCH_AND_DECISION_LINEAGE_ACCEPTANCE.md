# FMDL-7B｜End-to-End Research & Decision Lineage Acceptance

## Objective

FMDL-7B proves that the accepted A-share, Hong Kong Stock Connect and US research-adapter systems preserve explicit evidence, research, decision and governed-routing identities across market-specific workflows.

It is a lineage acceptance stage. It does not refresh prices, execute new research, alter Candidate Pool membership, admit a simulation position, modify a real account, change investment rules, repack the File Library Canonical ZIP or create an order.

## Bound market lineages

### A-share

Six accepted lineages are replayed through:

`Evidence ID → Research ID → Graduation Decision → State Transition ID → Thesis Record ID`

Four cases remain Candidate Pool re-entry reviews and two remain Shadow Track re-entry reviews. Research graduation remains distinct from Candidate Pool admission.

### Hong Kong Stock Connect

Six accepted lineages are replayed through:

`FMDL-5E Screen → FMDL-5F Research Object and Decision → FMDL-5G Governed Route`

Four cases remain Candidate re-entry reviews and two remain Shadow Track reviews. Midea Group and Wuxi AppTec retain mandatory A/H duplication review before any market or exposure choice.

### US equity

Seven accepted research-benchmark lineages are replayed through:

`Evidence Registration → Security Evidence Ledger → Workflow Integration State → Decision Interface → Human Approval State`

Six issuer securities remain blocked because Decision-grade market data, registered workflow output, valuation, formal peer, investment context, thesis/falsifier and human approval prerequisites are incomplete. QQQ remains a reference instrument rather than an issuer candidate. No US candidate promotion is emitted.

## Required controls

- no orphan evidence, research, decision or route identity;
- no duplicate lineage identity;
- no ticker-only cross-market matching;
- no silent filling of missing lineage links;
- no forced common market score;
- no automatic Candidate Pool promotion;
- no investment recommendation generated from research priority or graduation status;
- no Candidate Pool, simulation, real-account, rule or order mutation;
- `trade_authority = NONE`.

## Failure injection

The acceptance run must reject seven fixtures covering missing lineage identities, state-domain crossover, research-object or route mismatch, A/H duplication bypass, US evidence or Decision Interface loss, fabricated approval or automatic promotion, and trade-authority escalation. Rejected fixtures cannot replace Current or Last-known-good.

## Exit

`FMDL7B_END_TO_END_RESEARCH_AND_DECISION_LINEAGE_ACCEPTED`

## Next gate

`FMDL-7C_PORTFOLIO_SIMULATION_ATTRIBUTION_AND_RULE_CALIBRATION_ACCEPTANCE`
