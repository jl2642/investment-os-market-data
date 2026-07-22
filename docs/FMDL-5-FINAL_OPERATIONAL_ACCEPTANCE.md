# FMDL-5-FINAL — Hong Kong Stock Connect Operational Acceptance

## Objective

Close FMDL-5 through a single end-to-end replay of the accepted Hong Kong Stock Connect chain while preserving the accepted Investment OS Release-8 base and all state/action firewalls.

## Bound lineage

The acceptance binds the immutable releases for:

- FMDL-5-0 cross-market architecture;
- FMDL-5A Southbound universe boundary;
- FMDL-5B-1 security identity;
- FMDL-5B-2 issuer and cross-market semantics;
- FMDL-5C price, volume, corporate actions and FX;
- FMDL-5D HKEX disclosures and normalized financials;
- FMDL-5E-R1 factors and formal-sleeve-only screening;
- FMDL-5F Public Equity Research objects and graduation;
- FMDL-5G read-only Investment OS routing.

The accepted Investment OS Release-8 base remains immutable. FMDL-5-FINAL validates a cross-market overlay and does not falsely claim that the File Library binary package has already been repacked.

## Operational acceptance gates

- exact 644-security Southbound universe and 613 common equities;
- accepted 644-security market snapshot;
- at least 600 Decision-grade financial inputs;
- exact 28-factor architecture;
- exact 100-name formal-sleeve-only Longlist and zero fallback rows;
- exact 20 formal Research Objects;
- exact four Graduated and two Shadow Track decisions;
- exact six governed state transitions;
- exact four candidate re-entry reviews and two A/H duplication reviews;
- complete `security -> screen -> research -> transition` lineage for all six transitions;
- zero candidate-pool, simulation, real-account or order mutation;
- rollback/LKG preservation, failure injection and same-input replay;
- `trade_authority = NONE`.

## Capability conclusion

After formal acceptance, the system is operational for **A-share and Hong Kong Stock Connect research and governed investment decision support**. This includes market-data acquisition, point-in-time evidence, factor screening, formal company research, research graduation, cross-market duplication control, state routing and portfolio-review inputs.

This conclusion does not mean:

- persistent alpha has been proven;
- Research Graduation automatically admits a security to the candidate pool;
- candidate review automatically admits a security to the simulation portfolio;
- simulation review automatically admits a security to the real account;
- a broker connection or automatic order authority exists.

## Canonical package posture

FMDL-5-FINAL publishes Current, immutable Release, Archive and `FMDL5_FINAL_LAST_SUCCESS.json` in GitHub. The File Library Release-8 package remains the binary base until a separate single-package refresh imports its readable bytes and composes the accepted FMDL-5 overlay. No File Library deletion is authorized by this phase.

## FMDL-6 bounded scope

FMDL-6 is re-scoped as **US Equity Interface and Benchmark Pilot**, not a full-US-universe build.

The frozen scope is:

1. define US security identity, SEC disclosure and market-data interfaces;
2. select a representative 24-security benchmark spanning large-cap sectors, ADR/foreign issuer, REIT, financial, loss-making growth and corporate-action cases;
3. run small-sample price, SEC submissions/company-facts and corporate-action smoke tests;
4. measure free-source coverage, latency, revision identity, point-in-time controls, cost and failure modes;
5. produce a future full-build decision gate.

Explicitly excluded without a later user decision:

- full-US-universe history backfill;
- full-market factor and screening production;
- candidate-pool, simulation or real-account integration;
- automatic trade authority.

A full build may only be reconsidered after the user has a real US-market investment channel and explicitly approves the resource commitment.

## Exit

Required status:

`FMDL5_HONG_KONG_STOCK_CONNECT_OPERATIONAL_ACCEPTANCE_ACCEPTED`

Next gate:

`FMDL-6_0_US_EQUITY_INTERFACE_AND_BENCHMARK_PLAN`
