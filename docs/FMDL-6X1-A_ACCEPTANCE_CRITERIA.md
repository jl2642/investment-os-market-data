# FMDL-6X1-A Acceptance Criteria

The phase may be accepted only when all conditions below pass:

1. The uploaded Investment OS Release-8 package identity and SHA-256 are bound exactly.
2. The package outer ZIP, all Manifest file hashes and all four nested runtime ZIPs pass integrity checks.
3. Accepted FMDL-5-FINAL and FMDL-6-FINAL remain immutable upstream evidence.
4. The Research Production Gate is `OPEN_FOR_CONTROLLED_BUILD`.
5. The Brokerage & Real-Account Gate remains `CLOSED_NO_CHANNEL`.
6. Research eligibility and channel eligibility are represented as separate states.
7. The FMDL-6X1 sequence contains exactly five planned rounds and no more than two targeted repairs.
8. Candidate-pool, simulation, real-account and order mutations all equal zero.
9. `trade_authority = NONE`.
10. Deterministic validator, negative regression tests and GitHub Actions validation pass.

Required exit:

`FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED`

Next gate:

`FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY`
