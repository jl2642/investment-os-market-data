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

Gate v3 reads only `symbol`, `name` and `market_evidence.exchange`. The verified identity-only derivative is transported as six deterministic `gzip+base64` parts and is materialized at runtime to the exact legacy path expected by Gate v3.

- materialized size: `444,911` bytes
- materialized SHA-256: `c99f9bcca0c32a3992ef8f1b46679e854a958027fc48d89f3244c510985d304a`
- compressed size: `55,949` bytes
- compressed SHA-256: `01f7978dee6fa9e62922f23b7cf434dc3deffd958f619be5b6ebe3804824cbc3`
- records / unique symbols: `5,528 / 5,528`
- materializer: `automation/wp3_2a/materialize_identity_baseline.py`
- lineage manifest: `WP3_2_OLD_ACCEPTED_IDENTITY_BASELINE_20260717.manifest.json`

The materializer fails closed on missing parts, invalid Base64/Gzip, size mismatch, hash mismatch, record-count mismatch, duplicate symbols or schema mismatch.
