# Investment OS Interface v1.0.0

## 1. Purpose

Define the stable handoff from the market-data repository to 股票投资助手 / Investment OS.

FMDL publishes evidence and screening inputs. It does not modify holdings, candidate status or trade permissions directly.

## 2. Stable output paths

Planned production paths:

```text
outputs/current/A_SHARE_UNIVERSE.csv
outputs/current/DAILY_MARKET_SNAPSHOT.csv
outputs/current/DATASET_MANIFEST.json
outputs/current/DATA_QUALITY_REPORT.json
outputs/current/DATA_QUALITY_REPORT.md
```

Consumers must read the manifest before reading the datasets.

## 3. Consumer preflight

Investment OS must verify:

1. Manifest exists and parses.
2. Dataset ID and major schema version are supported.
3. Publication status is `PUBLISHED`.
4. File hash matches the manifest.
5. QA status is `READY` or an explicitly accepted `DEGRADED` state.
6. `as_of_date` is suitable for the requested decision context.
7. No requested field is used when its quality state is unsupported.

Failure of preflight means `DATA_NOT_READY`, not permission to infer or fabricate data.

## 4. Dataset roles

### A-share universe

Used to:

- define the scan universe;
- resolve symbol, exchange, board and listing status;
- attach ST, suspension and listing-age flags;
- support FMDL-2 investability filters.

It does not rank or recommend securities.

### Daily market snapshot

Used to:

- update market price and liquidity observations;
- calculate downstream factors in FMDL-2;
- compare holdings and candidates at a consistent date;
- establish valuation inputs where fields are available and validated.

It is not a trade instruction.

## 5. Public Equity Investing handoff

FMDL-2/FMDL-4 may pass a prioritized candidate set to Public Equity Investing.

Required handoff posture:

- screen results are `research candidates`, not recommendations;
- data date, fields and QA status travel with each candidate;
- missing evidence is explicit;
- Public Equity outputs return research priority, thesis, catalyst, risks and next diligence;
- Investment OS reruns its own Gate and portfolio-fit rules before any simulated or real action.

## 6. State separation

The following remain outside this repository:

- real-account positions and transactions;
- simulated portfolio positions and transactions;
- user liquidity outside the securities account;
- candidate pool canonical statuses;
- position sizing and capital migration decisions;
- performance attribution and strategy calibration;
- user trade confirmation.

They remain in the 股票投资助手 CURRENT asset.

## 7. Update behavior

A new FMDL release may trigger a review but must not silently rewrite Investment OS CURRENT.

Expected FMDL-4 behavior:

1. Read accepted market-data release.
2. Generate screening/research outputs.
3. Compare with existing holdings and candidate pool.
4. Produce proposed state changes with evidence.
5. Apply changes to Investment OS only through its canonical state-refresh process.

## 8. Error posture

- `READY`: normal use.
- `DEGRADED`: use only unaffected fields and display warnings.
- `QUARANTINED` or `FAILED`: do not consume candidate release; retain prior accepted release.
- Stale LKG: may support historical/context work but cannot be presented as current.

## 9. Cross-market extension

The interface is market-neutral at the manifest level. FMDL-5 and FMDL-6 add market adapters and schemas without changing Investment OS authority boundaries.
