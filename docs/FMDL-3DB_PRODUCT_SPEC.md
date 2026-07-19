# FMDL-3D-B — Effective Share Count & Capitalization Engine

## 1. Purpose

FMDL-3D-B converts the accepted FMDL-3D-A point-in-time contract into a full-Universe effective-share-count ledger and capitalization Current.

This phase owns effective share counts and daily market capitalization. It does not calculate a valuation score, target price, shareholder yield, portfolio action or trade instruction.

## 2. Entry gate

`FMDL3DA_VALUATION_AND_SHAREHOLDER_RETURN_CONTRACT_ACCEPTED`

The engine also binds to one accepted FMDL-1 Current release and verifies the exact hashes of:

- `A_SHARE_UNIVERSE.csv`;
- `DAILY_MARKET_SNAPSHOT.csv`.

## 3. Full-Universe execution

The accepted Universe is assigned exactly once to 16 deterministic SHA-256 shards. Each shard:

1. loads the accepted latest-completed-session market snapshot;
2. retrieves the issuer share-capital change history from the frozen free provider route;
3. normalizes positive total and float A-share rows;
4. preserves future-effective rows as evidence;
5. selects the latest positive row effective no later than the price date;
6. computes total and float A-share market capitalization;
7. publishes one explicit Current state for every Universe member;
8. preserves retry, source-error and quarantine evidence.

## 4. Point-in-time rules

### Price

The numerator is the accepted FMDL-1 completed-session close. The engine preserves:

- price as-of date;
- source timestamp;
- source row hash;
- data status and record quality.

### Effective shares

For price date `T`, the selected share-count row is:

`latest positive source row with effective_date <= T`

Future-effective rows remain in the immutable ledger but cannot be selected for Current.

### Capitalization

`total_market_cap_cny = close × total_shares`

`float_market_cap_cny = close × float_a_shares`

Provider market-cap fields and provider PE/PB/PS are not authoritative.

## 5. Share-count ledger

The ledger preserves:

- issuer identity and board;
- source effective date;
- total, float A-share and optional limited A-share counts;
- change reason where available;
- PIT eligibility state;
- Current-selection flag;
- raw source fields;
- retrieval timestamp;
- source row hash;
- authority boundary.

## 6. Capitalization Current states

- `VALID`
- `VALID_WITH_WARNING`
- `PRICE_UNAVAILABLE`
- `SHARE_SOURCE_UNAVAILABLE`
- `NO_EFFECTIVE_SHARE_ROW`
- `FUTURE_ONLY_SHARE_ROWS`
- `INVALID_SHARE_VALUES`
- `UNIVERSE_OR_SNAPSHOT_CONFLICT`
- `CONTROLLED_QUARANTINE`

Only `VALID` and `VALID_WITH_WARNING` rows publish capitalization values. All other states retain null capitalization and an explicit reason.

## 7. Frozen coverage gates

- accepted price coverage: at least 98%;
- effective-share coverage overall: at least 95%;
- effective-share coverage outside BSE: at least 97%;
- board gates: SH Main 97%, SZ Main 97%, STAR 95%, ChiNext 97%, BSE 70%;
- zero future-selected share rows;
- zero future-effective Current rows;
- zero non-positive selected shares;
- zero duplicate Current keys;
- zero missing Universe members;
- zero untraceable selected share rows;
- all shard validations PASS;
- trade authority NONE.

## 8. Outputs

Candidate and published interfaces contain:

- `FMDL3DB_CAPITALIZATION_CURRENT.parquet`;
- `FMDL3DB_EFFECTIVE_SHARE_LEDGER.parquet`;
- `FMDL3DB_RETRY_LEDGER.csv`;
- `FMDL3DB_COVERAGE.csv`;
- `FMDL3DB_QUARANTINE.csv`;
- source release snapshots;
- shard decisions and validations;
- aggregate decision, independent validation and manifest;
- immutable Release, Current, Archive and Last-success pointer.

## 9. Failure and recovery

A failed shard or aggregate candidate cannot replace Current. Source errors remain explicit and retryable. Manual corrections require a source-identified immutable repair record; silent edits are prohibited.

FMDL-3E later adds scheduled incremental refresh, same-input replay, provider-change detection and Last-known-good failure simulation.

## 10. Authority boundary

The engine supplies data and research evidence only. It cannot:

- create an attractive-valuation conclusion;
- create a target price;
- alter a candidate pool;
- modify simulation or real holdings;
- generate an order;
- acquire trade authority.

`trade_authority = NONE`

## 11. Exit and next gate

Exit:

`FMDL3DB_EFFECTIVE_SHARE_COUNT_AND_CAPITALIZATION_ENGINE_ACCEPTED`

Next:

`FMDL-3D-C — Valuation Engine Current`
