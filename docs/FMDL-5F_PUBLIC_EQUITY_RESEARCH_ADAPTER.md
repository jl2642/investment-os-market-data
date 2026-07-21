# FMDL-5F｜Public Equity Research Adapter

## 1. Objective

FMDL-5F converts the formally accepted FMDL-5E-R1 Hong Kong research Longlist into traceable Public Equity Research objects and governed graduation decisions. It reuses the accepted FMDL-4 research-object architecture while adding Hong Kong-specific official-disclosure, A/H, dividend, WVR/internet and corporate-action routes.

The phase ends at research routing. It does not admit a security to the Investment OS candidate pool, simulation portfolio or real account, and it does not create a target price, position size or order.

## 2. Bound lineage

- FMDL-5C market store: `FMDL5C_20260721_52f17b755436`
- FMDL-5D disclosure and financial store: `FMDL5D_20260721_0aee5654502c`
- FMDL-5E-R1 factor and screening release: `FMDL5E_20260721_5fd74c13444b`
- FMDL-5E entry status: `FMDL5E_HONG_KONG_FACTOR_AND_SCREENING_ADAPTER_ACCEPTED`

Every formal object binds its accepted screening row, accepted factor row and accepted FMDL-5D financial Current row by deterministic hash.

## 3. Research cohort and stage model

The 100-name FMDL-5E Longlist becomes the complete research-priority registry. The current 20-name `A_IMMEDIATE_RESEARCH` cohort receives formal Research Objects. The remaining 80 names retain a traceable `SCREENED / DEFERRED` state and are not mechanically rejected.

Formal decisions are:

- `GRADUATED`: research case ready only;
- `SHADOW_TRACK`: material expectations, governance, geopolitical or event risk remains unresolved;
- `DEFERRED`: evidence is relevant but incomplete;
- `REJECTED`: the first research gate fails.

The accepted target is 15–20 formal Research Objects and 5–8 Graduated or Shadow Track cases.

## 4. Research object

Each Research Object records:

- business model and competitive position;
- owner/governance-quality hypothesis;
- earnings drivers, catalysts and risks;
- variant perception and Why Now;
- first rejection and investability conditions;
- at least four Prove/Kill checks;
- cross-sectional screening and valuation context;
- Hong Kong case types;
- official public sources and accepted internal evidence bindings;
- research decision and authority boundary.

Qualitative fields are deterministic research hypotheses for subsequent analyst verification. They are not represented as direct quotations from filings or as completed initiating coverage.

## 5. Source policy

Official public sources must use `www1.hkexnews.hk`, must have been available no later than the accepted market as-of date and must be financial-result or financial-statement material. ESG reports, meeting material, poll results and presentations are excluded from the source-selection route.

Each object requires at least one official public source and three total references including internal accepted evidence. A Graduated object requires at least two official sources. Future sources are prohibited.

## 6. Required Hong Kong case routes

Graduated or Shadow Track objects must collectively cover:

- `A_H`;
- `HIGH_DIVIDEND`;
- `WVR_OR_INTERNET`;
- `CORPORATE_ACTION`.

Case coverage is a research-routing control. It does not increase a score or force graduation.

## 7. Canonical outputs

- `FMDL5F_RESEARCH_PRIORITY_REGISTRY.csv`
- `FMDL5F_RESEARCH_OBJECTS.jsonl`
- `FMDL5F_RESEARCH_OBJECT_INDEX.csv`
- `FMDL5F_SOURCE_LEDGER.csv`
- `FMDL5F_GRADUATION_REGISTRY.csv`
- `FMDL5F_CASE_ROUTE_COVERAGE.csv`
- `FMDL5F_QUALITY_REPORT.json`
- `FMDL5F_DECISION.json`
- `FMDL5F_MANIFEST.json`

An accepted main run publishes Current, Immutable Release, Archive and `outputs/status/FMDL5F_LAST_SUCCESS.json`.

## 8. Acceptance gates

- exactly 100 registry rows and 20 formal objects for the current active cohort;
- formal-object count remains inside the master-plan range of 15–20;
- 5–8 Graduated or Shadow Track cases;
- all four required Hong Kong case routes represented;
- zero duplicate registry or object security IDs;
- zero missing active profiles or required evidence bindings;
- official-source and minimum-source requirements satisfied;
- zero future or non-HKEX official sources;
- zero raw-score-only decisions;
- deterministic object hashes, Manifest identity and same-input replay;
- zero candidate-pool, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## 9. Controlled limitations

- The 20 objects are a governed first-pass research baseline, not full initiating-coverage reports.
- The adapter does not build independent forecasts, DCF models, target prices or complete relative-valuation models.
- FMDL-5D official filing identity and structured financial evidence support the research route, but qualitative hypotheses still require analyst verification.
- Graduation is not candidate admission and creates no portfolio or trade authority.

## 10. Exit

Expected accepted status:

`FMDL5F_PUBLIC_EQUITY_RESEARCH_ADAPTER_ACCEPTED`

Next gate:

`FMDL-5G_INVESTMENT_OS_INTEGRATION`
