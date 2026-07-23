# FMDL-6X3-D｜Sector, Industry, Peer & Benchmark Framework

## Objective

Create an auditable classification, peer and benchmark framework without converting incomplete evidence into formal industry-neutral rankings.

## Accepted first baseline

- SEC SIC is the only official issuer-classification anchor.
- Internal sector and industry labels are an explicit `INTERNAL_SEC_SIC_CROSSWALK_V1`; they are not claimed as GICS or ICB.
- Six SEC-linked issuers receive official SIC evidence and internal crosswalk labels.
- All other research securities remain in an official-classification evidence queue; security names alone cannot create a formal sector.
- Industry cohorts remain below the three-member formal peer minimum, so no formal peer ranks are emitted.
- QQQ is registered as the available Nasdaq-100 reference security, but its accepted market history remains `NON_DECISION_GRADE_FALLBACK`.
- Only benchmark-relative sandbox observations are allowed; no formal benchmark, sector-neutral or global factor score is emitted.

## Completion boundary

This stage accepts the production framework and explicit queues. It does not claim full sector coverage, GICS/ICB coverage, formal peer comparability, decision-grade benchmark data or candidate-pool authorization.
