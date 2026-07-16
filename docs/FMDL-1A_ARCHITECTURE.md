# FMDL-1A-R Production Architecture

## 1. Objective

Create the production architecture and contracts required to build a free, auditable A-share market-data MVP for Investment OS.

This phase freezes responsibilities, schemas, quality gates, versioning, publication state and downstream interfaces before ingestion code is written.

## 2. Scope

### Included in FMDL-1

- Shanghai, Shenzhen and Beijing listed A-share common stocks.
- Security master and investability metadata.
- Trading calendar.
- Daily market snapshot after the close.
- Selected market and valuation fields available from free sources.
- Data quality validation, lineage, last-known-good protection and stable output files.
- GitHub Actions automation.

### Excluded from FMDL-1

- Financial-statement hardening, TTM reconstruction and sector-specific accounting logic: FMDL-3.
- Factor ranking and candidate funnel: FMDL-2.
- Hong Kong Stock Connect: FMDL-5.
- Paid consensus, tick data, order books and broker connectivity.
- Automated orders or portfolio changes.

## 3. Authority boundary

The repository is authoritative only for market-data evidence and screening inputs.

- Data layer may publish `READY`, `DEGRADED`, `QUARANTINED` or `FAILED` data states.
- Public Equity Investing may research and prioritize candidates.
- Investment OS retains final authority over candidate status, gates, position sizing and portfolio actions.
- Real trades require explicit user confirmation and manual execution.

## 4. Logical pipeline

```text
Source Registry
      ↓
Source Adapter
      ↓
Raw Candidate Snapshot
      ↓
Canonical Normalization
      ↓
Schema Validation
      ↓
Quality Gates
      ↓
Manifest + Hash + Lineage
      ↓
Publish or Quarantine
      ↓
Stable Investment OS Outputs
```

## 5. Repository structure

```text
.
├── README.md
├── config/
│   ├── data_sources.json
│   ├── universe_rules.json
│   ├── quality_gates.json
│   └── schedules.json
├── schemas/
│   ├── a_share_universe.schema.json
│   ├── daily_market_snapshot.schema.json
│   └── dataset_manifest.schema.json
├── ingestion/
│   └── akshare/                 # FMDL-1B/C
├── pipeline/                    # FMDL-1B/C/D
├── datasets/
│   ├── raw/                     # dated source captures
│   ├── processed/               # normalized dated datasets
│   ├── manifests/               # dated manifests
│   ├── quality/                 # dated QA reports
│   └── lkg/                     # last-known-good pointers/data
├── outputs/
│   ├── current/                 # stable downstream paths
│   └── archive/                 # immutable dated releases
├── scripts/
│   └── validate_contracts.py
├── docs/
│   ├── DATA_CONTRACT.md
│   ├── SOURCE_REGISTRY.md
│   ├── QUALITY_GATES.md
│   ├── UPDATE_CADENCE.md
│   ├── INVESTMENT_OS_INTERFACE.md
│   └── FMDL-1A-R_ACCEPTANCE.md
└── .github/workflows/           # FMDL-1E
```

Empty runtime directories are created by pipeline code. Generated files are not considered canonical unless accompanied by a passing manifest.

## 6. Canonical datasets

### `a_share_universe`

One row per listed A-share security as of a date. Includes identity, exchange, board, listing status, ST/suspension flags, industry metadata and source lineage.

### `daily_market_snapshot`

One row per security per trading date. Includes OHLC, previous close, return, volume, turnover, market capitalization and available valuation fields.

### `trading_calendar`

Trading-date reference used to distinguish holidays, delayed data and actual failures. Implementation begins in FMDL-1B/C.

### `dataset_manifest`

One manifest for every candidate or published dataset. It records schema version, source times, row count, hashes, QA state and parent/last-known-good lineage.

### `data_quality_report`

Human-readable and machine-readable QA results generated for each run.

## 7. Dataset lifecycle

```text
COLLECTED
  → NORMALIZED
  → VALIDATED
  → READY | DEGRADED | QUARANTINED | FAILED
  → PUBLISHED only when allowed by policy
```

- `READY`: all hard gates pass; publish normally.
- `DEGRADED`: all hard gates pass but one or more soft gates fail; publish with explicit warnings only where the dataset contract permits.
- `QUARANTINED`: schema or hard quality gate fails; preserve evidence but do not update stable outputs.
- `FAILED`: no valid candidate dataset was generated.

## 8. Last-known-good rule

Stable files in `outputs/current/` are replaced only after:

1. Schema validation passes.
2. All hard quality gates pass.
3. Manifest and file hashes are generated.
4. Candidate release is written to the immutable archive.
5. Current pointers are updated atomically.

A failed or quarantined run must leave the previous current release unchanged.

## 9. Versioning

- Contract version: semantic version, beginning `1.0.0`.
- Dataset schema version: stored in every manifest.
- Dataset version: `<dataset_id>-<as_of_date>-<run_id>`.
- Run ID: UTC-safe unique ID while timestamps retain `Asia/Shanghai` business meaning.
- Material schema change requires a major version increase.
- Added nullable fields require a minor version increase.
- Documentation-only correction requires a patch increase.

## 10. Publication outputs

Stable paths planned for FMDL-1F:

```text
outputs/current/A_SHARE_UNIVERSE.csv
outputs/current/DAILY_MARKET_SNAPSHOT.csv
outputs/current/DATASET_MANIFEST.json
outputs/current/DATA_QUALITY_REPORT.json
outputs/current/DATA_QUALITY_REPORT.md
```

Dated copies are stored under `outputs/archive/YYYY/MM/DD/<run_id>/`.

## 11. Security and cost controls

- No paid API is required or authorized.
- No secrets are committed to the repository.
- Source adapters are read-only.
- GitHub Actions receives the minimum permissions required; publishing uses repository contents write permission only.
- External data is treated as untrusted input and validated before use.
- A free source failure is a data-quality event, not permission to fabricate or silently carry forward values as current.

## 12. Acceptance gate for FMDL-1A-R

FMDL-1A-R is accepted only when:

- All canonical documents exist.
- Machine-readable configuration files exist and cross-reference valid schema IDs.
- Three JSON schemas parse successfully.
- The contract validator reports PASS.
- Data source, cadence, QA, last-known-good and Investment OS boundaries are explicit.
- No ingestion or screening result is falsely represented as already operational.

FMDL-1 overall remains incomplete until real A-share datasets are produced and an automated workflow passes.
