# FMDL-4 — Public Equity Investing & Investment OS Integration Architecture

## Purpose

FMDL-4 turns the accepted FMDL-1 through FMDL-3E evidence stack into an operating public-equity research and Investment OS loop. It does not rebuild A-share market or financial data. It connects trusted evidence to investor research, then routes accepted research conclusions into candidate-pool, simulation-lab and real-account review states under explicit authority controls.

## Entry gate

`FMDL3E_UNIFIED_OPERATIONAL_ACCEPTANCE_AND_CANONICAL_CLOSURE_ACCEPTED`

The architecture binds:

- FMDL-1 market-data interface;
- FMDL-2 final screening and stability layer;
- FMDL-3C-D financial-score Investment OS interface;
- FMDL-3E Final unified operational Current;
- File Library canonical Investment OS package Release 4 metadata.

## Three-layer model

### Evidence layer — FMDL

Owns point-in-time market, factor, financial, valuation and shareholder-return evidence. Every decision-grade field retains release identity, source lineage, quality state, as-of time and controlled limitations. Evidence cannot mutate Investment OS state.

### Research judgment layer — Public Equity Investing

Owns investor interpretation: business model, competitive position, owner quality, earnings drivers, variant perception, valuation scenarios, catalysts, risks, prove/kill checks and research conclusions. A research object must cite accepted evidence IDs and cannot directly mutate portfolio state.

### Investment state layer — Investment OS

Owns candidate-pool, simulation-lab and real-account review state. State changes require role-specific gates, a versioned diff, reason codes, evidence IDs, research version, validation and rollback identity.

## Canonical objects

1. `FMDL_EVIDENCE_ENVELOPE` — one symbol and accepted as-of state.
2. `PUBLIC_EQUITY_RESEARCH_OBJECT` — one symbol and research version.
3. `INVESTMENT_OS_STATE_TRANSITION` — one proposed or accepted state change.
4. `THESIS_AND_ATTRIBUTION_RECORD` — one thesis version or attribution period.

These objects prevent raw FMDL rows, narrative research and portfolio state from being mixed into one opaque score.

## Public Equity Investing routing

- idea-generation owns screen triage and next-diligence priority;
- company-tearsheet owns issuer identity and investor fact packs;
- initiating-coverage owns complete thesis and valuation framing;
- earnings-preview/deep-dive own expectation and result updates;
- scenario-sensitivity owns downside/base/upside and breakpoints;
- thesis-tracker owns catalysts, prove/kill checks and review cadence;
- portfolio-risk-management owns portfolio-fit and action proposals, never execution;
- memo-builder owns research, thesis-update and pre-trade memos;
- meeting-prep owns management questions and diligence gaps;
- deck-report-qc owns source tie-out and circulation readiness.

## Role separation

### Candidate pool

Candidate state expresses research priority and observation status. FMDL scores may change research priority but may not automatically promote or delete a name. Graduation, defer and reject decisions require a research object and reason codes.

### Simulation lab

Simulation is an experiment and failure-mode environment, not a queue for the real account. Admission requires an experiment contract. Simulation performance does not automatically authorize real-capital migration.

### Real account

Real-account review requires the complete chain:

`RESEARCH_CASE_READY -> RCM_GATE -> PORTFOLIO_FIT -> ETF_ALTERNATIVE -> CAPITAL_MIGRATION -> PRE_TRADE_MEMO -> USER_CONFIRMATION`

No FMDL-4 phase creates order execution or trade authority.

## Investment OS package architecture

The existing three logical packages remain but are upgraded rather than replaced:

- `CORE_STATIC`: decision rules, research/graduation contracts, RCM, capital migration, authority and rollback rules;
- `EVIDENCE`: immutable FMDL pointers, evidence envelopes, research objects, sources and limitation registers;
- `STATE_CURRENT`: candidate research stages, simulation experiments, real-account reviews, thesis versions, accepted transition diffs and active FMDL bindings.

File Library remains the canonical package store. GitHub stores immutable data and integration Releases. Project Sources are not required.

## Authority firewall

The following are hard failures:

- raw score converted directly to portfolio action;
- candidate, simulation and real-account states crossing without their gates;
- state mutation without a versioned diff;
- research conclusion without evidence lineage;
- stale or quarantined evidence used as Current;
- failed package replacing Current;
- automatic real-account action;
- order generation or execution;
- any non-`NONE` trade authority.

## Controlled limitations

1. GitHub can bind the File Library pointer metadata and package SHA, but cannot inspect the external ZIP content until FMDL-4A imports and validates it.
2. FMDL-2 proves deterministic screening and short-window stability, not long-horizon realized alpha.
3. FMDL-3E live post-Baseline market advancement remains pending until a later completed session is accepted.

## Architecture exit

`FMDL4_ARCHITECTURE_ACCEPTED`

## Next gate

`FMDL-4A_RESEARCH_HANDOFF_AND_CANONICAL_STATE_PACKAGE_ADAPTER`
