# FMDL-4D — Thesis Tracking, Attribution & Feedback Loop

## Purpose

FMDL-4D creates an append-only, falsifiable thesis and attribution baseline for the six FMDL-4C re-entry-review names. It preserves the original FMDL-4B research, links the accepted FMDL-4C transitions and separates:

1. company-thesis status;
2. security-thesis readiness;
3. position action;
4. investment-outcome attribution;
5. strategy feedback proposals.

FMDL-4D does not admit a security to the candidate pool, simulation or real account. It does not create orders or trade authority.

## Entry gate

- `FMDL4C_INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED`
- `FMDL-4D_THESIS_ATTRIBUTION_AND_FEEDBACK_LOOP`

## Baseline population

Six FMDL-4C re-entry-review records:

- candidate-pool re-entry review: 长江电力、紫光股份、美的集团、上港集团;
- Shadow Track review: 中际旭创、星网锐捷.

## Thesis record

Each symbol receives one `THESIS_AND_ATTRIBUTION_RECORD` with:

- append-only Thesis version;
- company-thesis status;
- security-thesis readiness;
- position action and portfolio role;
- inherited research thesis and variant perception;
- earnings drivers, risks and open gates;
- catalyst and Prove/Kill links;
- Evidence, Research and Transition IDs;
- return and decision attribution status;
- lessons, feedback links and next review gate;
- deterministic semantic hash.

## Status separation

The initial company-thesis statuses are:

- `INTACT_UNTESTED_BASELINE` for candidate-pool re-entry review;
- `WATCH_UNTESTED_EXPECTATIONS_OR_QUALITY_GATE` for Shadow Track review.

All six securities remain:

- `NOT_DECISION_GRADE_PENDING_CURRENT_PRICE_AND_SCENARIO`;
- `WAIT_FOR_PROOF`;
- `UNASSIGNED_NO_EXPOSURE`.

A sound company thesis is not a security recommendation, and a security recommendation is not a position authorization.

## Catalyst and Prove/Kill registries

Catalysts are inherited from the source-backed FMDL-4B Research Objects. They remain `UNTESTED_BASELINE` until a new official filing or operating disclosure is registered.

Each symbol has five Prove/Kill checks. Conditions are labelled:

- `DRAFT_THRESHOLD_FOR_PM_CONFIRMATION`;
- `NOT_APPROVED`.

A Prove/Kill result cannot automatically mutate candidate, simulation or real-account state.

## Attribution baseline

No accepted simulation or real-account exposure exists. Therefore:

- gross return: unavailable;
- benchmark return: unavailable;
- active return: unavailable;
- selection attribution: unavailable;
- position attribution: unavailable;
- timing attribution: unavailable;
- failure classification: `NO_OBSERVATION`.

FMDL-4D explicitly prohibits inventing returns or treating research graduation as realized alpha.

## Failure taxonomy

The system distinguishes:

- selection error;
- research error;
- valuation error;
- timing error;
- position-sizing error;
- data-quality error;
- execution error;
- exogenous shock;
- thesis drift;
- no observation.

Classification occurs only after observable evidence exists.

## Feedback firewall

Feedback proposals are auditable but not applied rule changes. The firewall blocks:

- single-stock rule changes;
- single-period rule changes;
- automatic screening or graduation changes;
- automatic sizing or trading changes.

A rule change requires multiple independent observations, explicit failure classification, regression testing and human approval.

## Release-7 composition

`Release 4 external base + FMDL-4A evidence adapter + FMDL-4B research + FMDL-4C re-entry state + FMDL-4D thesis/attribution overlay`

The overlay is deterministic, independently validated and published to Current, Archive and an immutable Release directory.

## Acceptance gates

- exactly six Thesis records;
- at least eighteen catalysts;
- exactly thirty Prove/Kill checks;
- exactly six attribution baselines;
- exactly five feedback proposals;
- zero fabricated observable returns;
- zero decision-grade security calls;
- zero position actions;
- append-only decision log;
- zero rule mutation;
- zero candidate, simulation or real-account mutation;
- zero order generation;
- zero trade authority;
- deterministic ZIP and same-input idempotence.

## Controlled limitations

1. There is no accepted simulation or real-account exposure, so investment attribution is not yet observable.
2. Current price and explicit valuation scenarios are not bound into the security thesis.
3. Feedback proposals do not modify system rules.

## Exit gate

`FMDL4D_THESIS_ATTRIBUTION_AND_FEEDBACK_ACCEPTED`

## Next gate

`FMDL-4-FINAL_UNIFIED_INTEGRATION_AND_OPERATIONAL_ACCEPTANCE`

## Authority

`THESIS_TRACKING_ATTRIBUTION_AND_FEEDBACK_PROPOSALS_ONLY`

`trade_authority = NONE`
