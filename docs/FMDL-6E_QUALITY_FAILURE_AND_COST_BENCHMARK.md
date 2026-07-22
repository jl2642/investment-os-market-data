# FMDL-6E｜Quality, Failure & Cost Benchmark

## 1. Objective

FMDL-6E consumes the accepted FMDL-6D Current release and performs a deterministic, offline quality benchmark. It does not refresh live sources, expand the US universe, produce factors, create a research Longlist, or mutate any Investment OS state.

The phase must prove four things:

1. the accepted FMDL-6D data chain is internally coherent and fully lineage-bound;
2. material data, identity, point-in-time, manifest and authority defects are rejected;
3. injected failures do not mutate the accepted upstream LKG;
4. the current free-route pilot has a transparent request, storage and scaling-cost profile.

## 2. Accepted input

- FMDL-6D release: `FMDL6D_20260722_5e207a0a13a8`
- status: `FMDL6D_MINIMAL_END_TO_END_DATA_CHAIN_ACCEPTED`
- input: `outputs/fmdl6d/current`
- authority: bounded technical benchmark only
- trade authority: `NONE`

The benchmark reads the published FMDL-6D Market Store, FX Store, selected SEC financial facts, Chain Records, Availability policy, Source Registry, Decision, Validation, Release and Manifest.

## 3. Quality dimensions

The baseline audit covers nine dimensions:

1. Release and Manifest integrity;
2. market completeness, uniqueness and numeric-domain validity;
3. corporate-action completeness and availability lineage;
4. FX completeness, uniqueness and numeric-domain validity;
5. financial-fact identity, filing lineage and availability;
6. cross-store referential integrity;
7. source hashes and no-silent-replacement controls;
8. point-in-time and no-lookahead posture;
9. candidate, simulation, real-account, order and trade-authority firewalls.

Any baseline error is a hard failure. A weighted quality score is deliberately not used to hide a failed critical control: each dimension is reported by explicit pass and error counts.

## 4. Failure-injection matrix

The deterministic suite injects at least sixteen defects into deep copies of the accepted input:

- missing security;
- duplicate market date;
- null close;
- negative volume;
- security-key mismatch;
- payload-hash corruption;
- negative FX rate;
- duplicate FX date;
- missing SEC accession;
- duplicate financial fact key;
- broken chain link;
- unauthorized lookahead claim;
- manifest hash mismatch;
- trade-authority escalation;
- candidate-pool mutation attempt;
- source-registry row loss.

Every declared defect must trigger its expected rejection code. False negatives are forbidden.

## 5. LKG and replay proof

Failure injections operate on in-memory deep copies only. The FMDL-6D Last-success pointer and Current Manifest are hashed before and after the suite; both must remain unchanged.

The candidate is built twice from the same accepted input without a live refresh. The two canonical document sets and their SHA-256 identities must match. Independent candidate validation performs an additional deterministic rebuild and compares the complete Manifest.

The publisher validates before replacing Current. A rejected candidate therefore cannot overwrite the existing FMDL-6E LKG.

## 6. Cost model

The benchmark records:

- current market, FX, financial-fact, event and source counts;
- known response bytes retained in the Source Registry;
- published output bytes from the FMDL-6D Manifest;
- per-security market-store bytes;
- per-sample-issuer financial-store bytes;
- a bounded 24-security low/high request and storage projection.

The current provider cash-cost assumption is USD 0 because the pilot uses free Yahoo routes, ECB official series and an approved external SEC snapshot route. This is not a total-cost claim: human review, maintenance, hosted compute, source breakage, future paid-provider fees and compliance work are excluded.

No reliable wall-clock benchmark was persisted by FMDL-6D, so FMDL-6E does not invent one. Full-universe numeric projection remains closed and deferred.

## 7. Acceptance gates

FMDL-6E is accepted only when:

- the baseline error count is zero;
- all nine quality dimensions are evaluated;
- all declared injections are executed;
- false-negative count is zero;
- upstream LKG hashes are unchanged;
- same-input replay passes;
- candidate Manifest and canonical identity pass independent validation;
- all candidate, simulation, real-account and order mutation counts remain zero;
- `trade_authority = NONE`.

## 8. Exit and next gate

Expected exit:

`FMDL6E_QUALITY_FAILURE_AND_COST_BENCHMARK_ACCEPTED`

Next gate:

`FMDL-6-FINAL_RESUME_READY_OPERATIONAL_ACCEPTANCE`

FMDL-6E does not authorize a full US build or any investment decision route.
