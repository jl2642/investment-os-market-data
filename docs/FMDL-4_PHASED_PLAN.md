# FMDL-4 — Phased Execution Plan

## Overall sequence

`FMDL-4A -> FMDL-4B -> FMDL-4C -> FMDL-4D -> FMDL-4-FINAL`

No phase may be skipped. A later phase must bind the accepted Last-success pointer and Release identity of the prior phase.

## FMDL-4A — Research Handoff Contract and Canonical State-Package Adapter

### Objective

Create the stable machine-readable bridge from FMDL evidence to Public Equity Investing research and the existing Investment OS package.

### Required work

- import and independently validate the File Library canonical Investment OS Release 4 package;
- map existing `CORE_STATIC`, `EVIDENCE` and `STATE_CURRENT` assets without deleting historical state;
- create the `FMDL_EVIDENCE_ENVELOPE` schema and full-Universe Current;
- bind FMDL-2 research Longlist and FMDL-3E unified evidence;
- create Public Equity Investing workflow routing and evidence-reliance rules;
- create a Release-5 package candidate with manifests, diff, Current/Archive/LKG and rollback tests;
- prove no candidate, simulation or real-account state changed during adapter construction.

### Exit

`FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_ACCEPTED`

## FMDL-4B — Candidate Research and Graduation

### Objective

Turn the research Longlist into a governed research funnel rather than a score-ranked list.

### Research states

`OBSERVE -> SCREENED -> DEEP_DIVE -> INVESTMENT_CASE_READY -> GRADUATED / DEFERRED / REJECTED`

### Required work

- create a research-stage registry for the full Longlist;
- choose a bounded priority cohort based on evidence quality, score diversity and structural-fragility testing;
- create investor fact packs and research objects;
- assess business model, competitive position, governance/owner quality, earnings drivers, valuation scenarios, catalysts, risks and variant perception;
- record prove/kill checks and missing evidence;
- issue explicit graduation, defer or reject decisions with reason codes;
- prove that no raw market or financial score caused automatic graduation.

### Exit

`FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED`

## FMDL-4C — Investment OS Re-entry and State Mutation Controls

### Objective

Route accepted research conclusions into the correct Investment OS domain without state crossover.

### Required work

- create separate candidate-pool, simulation-lab and real-account routers;
- create the `INVESTMENT_OS_STATE_TRANSITION` schema;
- produce proposed and accepted state diffs with evidence and research-version bindings;
- update `STATE_CURRENT` only through validated transitions;
- retain simulation experiment independence from real-account review;
- require RCM, portfolio fit, ETF alternative, capital migration, pre-trade memo and user confirmation for real-account action;
- publish the updated canonical Investment OS package with Current/Archive/LKG and rollback evidence.

### Exit

`FMDL4C_INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED`

## FMDL-4D — Thesis Tracking, Attribution and Feedback Loop

### Objective

Build the operating learning loop from research thesis to observed outcome without fitting rules to isolated wins or losses.

### Required work

- create versioned thesis, catalyst and prove/kill trackers;
- connect candidate, simulation and real-account outcomes to the research version that authorized them;
- separate market beta, selection, position size, timing and execution contributions;
- classify failures as data, research, portfolio construction, timing, execution or regime errors;
- create feedback proposals with evidence, confidence and required review;
- prohibit automatic factor-weight or policy changes from one observation.

### Exit

`FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_ACCEPTED`

## FMDL-4-FINAL — Unified Integration and Operational Acceptance

### Objective

Prove that the complete research-to-state loop is deterministic, role-separated, recoverable and operational.

### Required work

- bind all FMDL-4 component Releases;
- run end-to-end replay from accepted FMDL evidence through research and state routing;
- prove same-input idempotence;
- inject stale evidence, missing research lineage, cross-domain state mutation and unauthorized action failures;
- prove failed candidates preserve Current and Last-success;
- publish unified Current, immutable Release, Archive and canonical Last-success;
- set the next gate to FMDL-5.

### Exit

`FMDL4_PUBLIC_EQUITY_INVESTING_AND_INVESTMENT_OS_INTEGRATION_ACCEPTED`

## Program boundaries

FMDL-4 may improve research priority, candidate graduation, simulation design and real-account review recommendations. It may not execute trades, connect to a broker, create automatic real-account admission or claim that FMDL-2/3 scores alone prove alpha.
