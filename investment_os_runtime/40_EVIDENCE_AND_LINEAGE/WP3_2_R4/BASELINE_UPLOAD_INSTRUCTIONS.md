# WP3-2A accepted identity baseline recovery

The historical accepted identity baseline has been recovered as a deterministic transport package on branch `automation/wp3-2a-baseline-recovery-20260725`.

No manual GitHub upload is required.

## Verified source

- source filename: `WP3_2_OLD_ACCEPTED_IDENTITY_EVIDENCE_20260717.jsonl`
- size: `14,949,468` bytes
- SHA-256: `b5fde4d2145f6d47a8120a3f96f91b74466fefd6793d5eeb37ab40a9a09b9b5d`
- records / unique symbols: `5,528 / 5,528`
- as-of: `2026-07-17`
- trade authority: `NONE`

## Gate-v3 derivative

Gate v3 reads only `symbol`, `name` and `market_evidence.exchange`. The verified identity-only derivative is transported as six `gzip+base64` parts and is materialized at runtime to the exact legacy path expected by Gate v3.

- materialized size: `592,941` bytes
- materialized SHA-256: `5f9ac4f3b0bf3d91dcee21fcae9825051ec8ed5c20778117de6700702415e11b`
- records / unique symbols: `5,528 / 5,528`
- materializer: `automation/wp3_2a/materialize_identity_baseline.py`
- lineage manifest: `WP3_2_OLD_ACCEPTED_IDENTITY_BASELINE_20260717.manifest.json`

The materializer fails closed on missing parts, invalid Base64/Gzip, size mismatch, hash mismatch, record-count mismatch, duplicate symbols or schema mismatch.
