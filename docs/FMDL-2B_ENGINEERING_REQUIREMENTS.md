# FMDL-2B — Historical Store & Basic Factor Engine Requirements

## 1. Authorized scope

FMDL-2B may now build the initial A-share historical store and calculate the factor registry frozen in FMDL-2A. It must not introduce valuation, financial-statement, market-cap, dividend or analyst-estimate factors; those remain FMDL-3.

## 2. Initial backfill design

- Input universe: accepted `outputs/current/A_SHARE_UNIVERSE.csv`.
- Target history: at least 251 valid sessions where listing history permits; use a wider retrieval window to tolerate suspensions and holidays.
- Primary route: `sina_daily / stock_zh_a_daily`, QFQ.
- Restricted fallback: `tencent_hist / stock_zh_a_hist_tx`, price-and-amount only, SH/SZ Main only.
- Shard size: configurable, initially 100–250 symbols per shard.
- Each shard must be independently resumable and idempotent.
- One failed symbol must not abort completed symbols or the entire shard.

## 3. Per-symbol state

Every symbol must carry:

- canonical symbol and board;
- provider and AKShare function;
- adjustment mode;
- requested and returned date range;
- first and latest valid dates;
- observation count;
- volume and amount capability flags;
- retry count and final state;
- source hash and normalized-series hash;
- quarantine reason where applicable.

Allowed states:

`PENDING -> FETCHED -> NORMALIZED -> VALIDATED -> READY`

or

`PENDING/FETCHED -> RETRY -> QUARANTINED`.

## 4. Historical data contract

Canonical columns should include:

- `date`, `symbol`, `open`, `high`, `low`, `close`;
- `volume_shares`, `turnover_cny` where the selected source supports them;
- `provider_id`, `source_function`, `adjustment_mode`;
- `retrieved_at`, `record_quality`, `row_hash`.

Rules:

- dates strictly ascending and unique;
- no date after the requested as-of date;
- valid OHLC values positive and internally consistent;
- missing values remain null;
- suspensions are represented explicitly, not converted into zero returns;
- provider series cannot be silently stitched across a symbol.

## 5. Cache and incremental update

Initial backfill writes immutable per-symbol history plus a manifest. Subsequent daily runs:

1. read the last validated date;
2. request only the overlap/incremental window;
3. validate overlap values and adjustment continuity;
4. append or replace the controlled overlap;
5. publish only after hash and date gates pass.

Full-history redownloads are reserved for repair, provider migration or corporate-action rebase.

## 6. Factor engine

The engine must implement only factors in `config/fmdl2_factor_registry.json` and must:

- slice all history at or before `as_of_date` before rolling calculations;
- use QFQ close for return/risk factors;
- use source-reported unadjusted volume and amount for liquidity factors;
- enforce minimum observations per factor;
- preserve missing factors and write explicit reason codes;
- calculate board-neutral and broad-market cross-sectional fields only after the same-date table is complete;
- carry factor availability, confidence and quality states;
- never map a missing factor to a neutral score.

## 7. Quality gates

Hard gates:

- valid Current interface and no FMDL-1 hard failure;
- identity uniqueness;
- future-data count zero;
- duplicate-date count zero after controlled normalization;
- impossible-OHLC count zero for promoted rows;
- series and output hashes valid;
- formula regression tests pass;
- factor date exactly matches the requested as-of date.

Controlled warnings:

- partial/new-listing history;
- quarantined symbols below the market-level blocking threshold;
- missing volume when restricted Tencent fallback is used;
- stale or suspended symbols;
- corporate-action continuity requiring review.

## 8. Publication model

FMDL-2B outputs remain candidate research evidence until FMDL-2C defines screening sleeves and FMDL-2D completes replay/stability acceptance.

No FMDL-2B output may:

- enter a live candidate pool as BUY-ready;
- change simulation or real holdings;
- bypass Public Equity Investing research triage;
- create automatic trading authority.

## 9. FMDL-2B acceptance evidence

FMDL-2B is not complete until it demonstrates:

- real multi-shard backfill over the full accepted universe;
- resumability after an interrupted shard;
- controlled retry and quarantine;
- a validated historical store with manifests and hashes;
- factor calculations for all eligible symbols;
- formula and anti-leakage regression tests;
- incremental append behavior;
- cost and GitHub Actions runtime within the free-tier operating design.
