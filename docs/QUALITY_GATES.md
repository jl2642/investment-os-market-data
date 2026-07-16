# Quality Gates v1.0.0

## 1. Principle

Quality gates decide whether a candidate dataset may replace the last-known-good current release. They do not attempt to prove every market value is perfect; they prevent structurally incomplete, stale, duplicated or obviously corrupt data from entering Investment OS.

## 2. Severity

- `HARD`: failure blocks publication and quarantines the candidate.
- `SOFT`: failure permits only `DEGRADED` publication when the dataset-specific policy allows it; warning must appear in the manifest and QA report.
- `INFO`: diagnostic only.

## 3. Common hard gates

| Gate ID | Rule |
|---|---|
| `C001_SCHEMA_VALID` | Candidate file conforms to the registered JSON schema. |
| `C002_MANIFEST_PRESENT` | Candidate has a manifest with schema version, source, timestamps and hashes. |
| `C003_HASH_MATCH` | Published file SHA-256 matches the manifest. |
| `C004_ASOF_CONSISTENT` | Row as-of dates agree with the dataset manifest. |
| `C005_NO_INVALID_ROWS` | No row is marked `INVALID`. |
| `C006_SOURCE_TIME_PRESENT` | Source and retrieval timestamps are present. |
| `C007_DATE_NOT_FUTURE` | Business as-of date is not later than the China-market date at runtime. |
| `C008_UNIQUE_GRAIN` | Dataset natural key has no duplicates. |

## 4. A-share universe gates

### Hard

| Gate ID | Rule |
|---|---|
| `U001_MIN_ROWS` | Row count is at least the configured absolute floor. Initial floor: 4,000. |
| `U002_LKG_COVERAGE` | When an LKG universe exists, candidate row count is at least 97% of LKG unless an approved market-structure event is recorded. |
| `U003_SYMBOL_VALID` | 100% of symbols match supported `.SH`, `.SZ` or `.BJ` canonical patterns. |
| `U004_SYMBOL_UNIQUE` | One row per symbol. |
| `U005_REQUIRED_FILL` | Required identity/status fields meet configured fill rates. |
| `U006_EXCHANGE_BOARD_VALID` | Exchange and board combinations are from the controlled vocabulary. |

### Soft

| Gate ID | Rule |
|---|---|
| `U101_NAME_CHANGE_SPIKE` | Unusually large number of name changes versus LKG. |
| `U102_INDUSTRY_FILL` | Industry coverage below target; initial warning threshold 90%. |
| `U103_LISTING_DATE_FILL` | Listing-date coverage below target; initial warning threshold 95%. |
| `U104_STATUS_SHIFT` | Unusual jump in suspended, ST or non-active securities. |

## 5. Daily market snapshot gates

### Hard

| Gate ID | Rule |
|---|---|
| `M001_TRADING_DATE` | `as_of_date` is a confirmed trading date or the run is explicitly classified no-op. |
| `M002_UNIVERSE_COVERAGE` | Snapshot covers at least 95% of active universe symbols, excluding documented suspensions/data-unavailable rows. |
| `M003_SYMBOL_UNIQUE` | One row per symbol per date. |
| `M004_CLOSE_VALID` | Close is positive for rows marked traded; non-traded rows have an explicit status. |
| `M005_OHLC_RELATION` | Where OHLC exists: low ≤ open/close ≤ high. |
| `M006_NONNEGATIVE_FLOW` | Volume and turnover are non-negative. |
| `M007_RETURN_RECONCILIATION` | Where close and previous close exist, reported percentage change reconciles within configured tolerance. |
| `M008_DATE_FRESHNESS` | Source trading date equals expected latest completed trading date. |

### Soft

| Gate ID | Rule |
|---|---|
| `M101_VALUATION_FILL` | PE/PB fill below target; initial warning threshold 70%. |
| `M102_MARKET_CAP_FILL` | Market-cap fill below target; initial warning threshold 90%. |
| `M103_EXTREME_RETURNS` | Returns outside configured limits without known price-limit/status explanation. |
| `M104_ZERO_TURNOVER_SPIKE` | Zero-turnover share materially exceeds LKG/trailing norm. |
| `M105_FIELD_DRIFT` | Source columns or data types differ from approved mapping. |

## 6. Staleness

- A daily snapshot is current only for its stated trading date.
- On a non-trading day, the latest trading-day release remains usable and is not relabelled with the calendar date.
- A failed new run leaves the LKG release in place with its original date.
- Downstream consumers must compare `as_of_date` with the trading calendar and use-case tolerance.

## 7. Quarantine behavior

On hard failure:

1. Preserve raw capture and candidate output when safe.
2. Write a failed manifest and QA report.
3. Set candidate state to `QUARANTINED` or `FAILED`.
4. Do not alter `outputs/current/`.
5. Surface gate IDs and remediation hints.

## 8. Degraded publication

A dataset may be published as `DEGRADED` only when:

- all hard gates pass;
- the failed soft gates do not invalidate core identity/price semantics;
- the manifest lists warnings;
- Investment OS can identify the degraded fields and avoid unsupported decisions.

Universe identity failures and core closing-price failures are never soft.

## 9. QA outputs

Every run produces:

- machine-readable `DATA_QUALITY_REPORT.json`;
- human-readable `DATA_QUALITY_REPORT.md`;
- gate result list with observed value, threshold, severity, status and evidence;
- comparison against LKG where available.

## 10. Threshold governance

Thresholds live in `config/quality_gates.json`. Changing a threshold requires:

- reason and effective date;
- before/after values;
- evidence from observed runs;
- no retroactive silent change to archived QA results.
