# FMDL-3D-B — Full-Universe Acceptance

## 1. Acceptance decision

`FMDL3DB_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED`

Accepted candidate release:

`FMDL3DB_20260719T194329+0800`

Accepted workflow run:

`29685409327`

Candidate artifact:

`8441977430`

Artifact digest:

`sha256:dc4f250e103febb9e692126bde3dcd6bb25bf38073b2a8b48db1cda59d0c3dba`

## 2. Bound source release

- market release: `FMDL1BC_20260717T174015+0800`;
- source as-of date: `2026-07-17`;
- Universe version: `a_share_universe-2026-07-17-FMDL1BC_20260717T174015+0800`;
- snapshot version: `daily_market_snapshot-2026-07-17-FMDL1BC_20260717T174015+0800`;
- Universe and snapshot hashes matched the accepted Current release.

## 3. Measured full-Universe result

| Metric | Accepted result |
|---|---:|
| Universe symbols | 5,528 |
| Capitalization Current rows | 5,528 |
| Deterministic shards | 16 |
| Effective-share ledger rows | 87,113 |
| Retry ledger rows | 5,528 |
| Accepted price rows | 5,523 |
| Accepted price coverage | 99.9096% |
| Valid capitalization rows | 5,523 |
| Effective-share coverage | 99.9096% |
| Non-BSE coverage | 99.9231% |
| Controlled quarantine rows | 5 |
| Future source ledger rows preserved | 56 |
| Future rows selected for Current | 0 |
| Future-effective Current rows | 0 |
| Non-positive selected share rows | 0 |
| Duplicate Current keys | 0 |
| Duplicate ledger keys | 0 |
| Source attempts | 5,528 |
| Maximum attempts for one symbol | 1 |
| Automatic action authority | 0 |

## 4. Board coverage

| Board | Valid capitalization coverage | Frozen gate | Result |
|---|---:|---:|---|
| SH Main | 100.0000% | 97% | PASS |
| SZ Main | 99.8660% | 97% | PASS |
| STAR | 99.8361% | 95% | PASS |
| ChiNext | 99.9285% | 97% | PASS |
| BSE | 99.6951% | 70% | PASS |

One accepted Universe row remains classified as `UNKNOWN` board and received valid capitalization evidence. The board-quality issue remains owned by the security-master layer; it does not create a capitalization ambiguity.

## 5. Controlled quarantine

Five issuers lacked a positive accepted close in the bound daily snapshot:

- `002656.SZ` — `*ST摩登`;
- `002713.SZ` — `*ST东易`;
- `301234.SZ` — `五洲医疗`;
- `689009.SH` — `九号公司`;
- `920685.BJ` — `新芝生物`.

Each retained valid share-history evidence but was published as `PRICE_UNAVAILABLE`. No share row was marked selected for Current and no capitalization value was fabricated.

## 6. Point-in-time and lineage acceptance

The following gates passed:

- exact full-Universe membership;
- one unique Current key per symbol;
- unique effective-share ledger identity;
- one selected ledger row per valid Current row;
- selected effective date not later than price date;
- positive total and float A-share counts;
- float shares not greater than total shares;
- exact selected-share lineage from Current to ledger;
- total and float market capitalization deterministic replay;
- price, source timestamp and share-effective date preservation;
- future-effective provider rows preserved but never selected;
- invalid rows carry explicit reasons and null capitalization.

## 7. Defect closed during production acceptance

The first production run exposed one semantic defect: a symbol with an invalid price could still retain a PIT-eligible share row marked `selected_for_current`, even though no capitalization Current was published.

The engine was corrected so `selected_for_current` means selection into an accepted capitalization Current, not merely eligibility by share-effective date. For any invalid capitalization state, all ledger rows remain preserved but the Current-selection flag is cleared.

After correction:

- all 16 shard validations passed;
- selected ledger rows exactly matched valid Current rows;
- the aggregate decision and independent validation passed with zero hard failures.

## 8. Independent validation

`status = PASS`

`hard_failures = []`

- manifest errors: 0;
- schema errors: 0;
- replay differences: CNY 0.00 for total and float market capitalization;
- future-selected share rows: 0;
- future Current share rows: 0;
- trade authority: `NONE`.

## 9. Controlled limitations

- the effective-share route currently relies on one tested free standardized provider, with retries and explicit quarantine;
- capitalization uses the latest completed-session close, not intraday prices;
- this phase does not calculate PE, PB, PS, EV multiples or a valuation score;
- provider market-cap and provider valuation fields remain non-authoritative;
- dividend, buyback and dilution event Current remains FMDL-3D-D work;
- no target price, candidate-pool mutation, portfolio action or trade authority exists.

## 10. Phase transition

FMDL-3D-B is accepted for immutable publication after main-branch validation.

Next authorized gate:

`FMDL-3D-C_VALUATION_ENGINE_CURRENT`

Authority:

`DATA_AND_RESEARCH_EVIDENCE_ONLY`

`trade_authority = NONE`
