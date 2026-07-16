# FMDL-1A-R Acceptance Record

## Release identity

- Phase: `FMDL-1A-R — Production Architecture & Contract Completion`
- Contract version: `1.0.0`
- Repository: `jl2642/investment-os-market-data`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`
- Acceptance state: `PENDING_AUTOMATED_VALIDATION`

## Assets under acceptance

### Governance documents

- `README.md`
- `docs/FMDL-1A_ARCHITECTURE.md`
- `docs/DATA_CONTRACT.md`
- `docs/SOURCE_REGISTRY.md`
- `docs/QUALITY_GATES.md`
- `docs/UPDATE_CADENCE.md`
- `docs/INVESTMENT_OS_INTERFACE.md`

### Machine-readable configuration

- `config/data_sources.json`
- `config/universe_rules.json`
- `config/quality_gates.json`
- `config/schedules.json`

### Schemas

- `schemas/a_share_universe.schema.json`
- `schemas/daily_market_snapshot.schema.json`
- `schemas/dataset_manifest.schema.json`

### Validation controls

- `scripts/validate_contracts.py`
- `.github/workflows/contract-validation.yml`

## Acceptance checks

| Check | Required result | Current result |
|---|---|---|
| Required architecture assets exist | PASS | PASS |
| JSON contracts parse | PASS | PENDING CI |
| Schema IDs and config references agree | PASS | PENDING CI |
| Free-only source policy is machine-readable | PASS | PENDING CI |
| Last-known-good protection is configured | PASS | PENDING CI |
| Daily schedule matches 17:30 Asia/Shanghai | PASS | PENDING CI |
| Investment OS authority boundary is explicit | PASS | PASS |
| No ingestion result falsely claimed operational | PASS | PASS |

## Phase boundary

Acceptance of FMDL-1A-R means the production architecture and contracts are frozen sufficiently to begin FMDL-1B/C implementation.

It does **not** mean that:

- AKShare production functions have been selected;
- a real A-share universe has been generated;
- daily market data is operational;
- scheduled ingestion has passed;
- Investment OS is already consuming this repository.

Those are FMDL-1B through FMDL-1F deliverables.

## Promotion rule

Change `Acceptance state` to `ACCEPTED` only after the deterministic validator reports:

```text
FMDL-1A-R CONTRACT VALIDATION: PASS
```

Any failed check keeps the phase at `REMEDIATION_REQUIRED`.
