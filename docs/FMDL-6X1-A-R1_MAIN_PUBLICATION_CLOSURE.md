# FMDL-6X1-A-R1 — Main Publication Closure

## Repair trigger

PR #61 merged the validated FMDL-6X1-A architecture and contract, but the merged configuration remained `CONTRACT_CANDIDATE` and no canonical `Current`, immutable Release or `Last-success` pointer was published. Therefore FMDL-6X1-A could not yet be treated as formally accepted.

## Repair scope

This targeted repair:

- promotes the contract status to `ACCEPTED`;
- binds PR #61 and merge commit `2ebe0bab0de891eadf4b547f1d77df5ba13b80b4`;
- publishes `outputs/fmdl6x1a/current`;
- publishes an immutable `datasets/fmdl6x1a/releases/<release_id>` copy;
- publishes `outputs/status/FMDL6X1A_LAST_SUCCESS.json`;
- validates complete parity and hashes;
- preserves zero candidate, simulation, real-account and order mutation;
- retains `trade_authority = NONE`.

## Exit

`FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED`

Next gate:

`FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY`
