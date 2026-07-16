# FMDL-1A-R Acceptance Record

## Release identity

- Phase: `FMDL-1A-R — Production Architecture & Contract Completion`
- Contract version: `1.0.0`
- Repository: `jl2642/investment-os-market-data`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`
- Acceptance state: `ACCEPTED`
- Validation result: `FMDL-1A-R CONTRACT VALIDATION: PASS`
- Validation scope: 17 required assets and 7 machine-readable JSON contracts

## Assets accepted

### Governance documents

- `README.md`
- `docs/FMDL-1A_ARCHITECTURE.md`
- `docs/DATA_CONTRACT.md`
- `docs/SOURCE_REGISTRY.md`
- `docs/QUALITY_GATES.md`
- `docs/UPDATE_CADENCE.md`
- `docs/INVESTMENT_OS_INTERFACE.md`
- `docs/FMDL-1A-R_ACCEPTANCE.md`

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

| Check | Required result | Result |
|---|---|---|
| Required architecture assets exist | PASS | PASS |
| Seven JSON contracts parse | PASS | PASS |
| Schema IDs and config references agree | PASS | PASS |
| Required Universe and Snapshot fields are defined | PASS | PASS |
| Free-only source policy is machine-readable | PASS | PASS |
| AKShare is registered only for MVP testing | PASS | PASS |
| Last-known-good protection is configured | PASS | PASS |
| Universe floor is at least 4,000 records | PASS | PASS |
| Snapshot coverage gate is at least 95% | PASS | PASS |
| Daily schedule matches 17:30 Asia/Shanghai | PASS | PASS |
| Trading-calendar and manual-dispatch controls exist | PASS | PASS |
| Manifest includes required publication states | PASS | PASS |
| Investment OS authority boundary is explicit | PASS | PASS |
| No ingestion result is falsely claimed operational | PASS | PASS |

## Validation evidence

The deterministic validation logic in `scripts/validate_contracts.py` was executed against the committed contract payloads and returned:

```text
FMDL-1A-R CONTRACT VALIDATION: PASS
```

The GitHub workflow is also installed to repeat this validation on relevant pushes, pull requests and manual dispatches. The connected GitHub tool does not expose ordinary push-triggered workflow runs in this session, so the repository-local deterministic result is the acceptance evidence for this release; future workflow results remain an additional operating control.

## Phase boundary

Acceptance of FMDL-1A-R means the production architecture and contracts are frozen sufficiently to begin the combined FMDL-1B/C implementation.

It does **not** mean that:

- AKShare production functions have been selected;
- a real A-share universe has been generated;
- daily market data is operational;
- scheduled ingestion has passed;
- Investment OS is already consuming this repository.

Those remain FMDL-1B through FMDL-1F deliverables.

## Next authorized batch

`FMDL-1B/C — A-share Universe Builder + Daily Market Snapshot`
