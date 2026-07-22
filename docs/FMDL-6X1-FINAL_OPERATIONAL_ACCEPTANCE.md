# FMDL-6X1-FINAL — Operational Acceptance

## Purpose

Close the five-round FMDL-6X1 program by independently validating the accepted A–D releases, replaying the same inputs, injecting controlled failures, restoring from a minimal clean-room asset set, and publishing an immutable final Release.

## Final authority decision

The final acceptance opens only the **Research Production Gate**:

`OPEN_FOR_FMDL6X2_DATA_PRODUCTION`

The **Brokerage & Real-Account Gate** remains:

`CLOSED_NO_CHANNEL`

Research eligibility, channel eligibility, portfolio admission and trade authority remain separate. No brokerage eligibility, real-account recommendation or order authority is inferred from research-production acceptance.

## Required validation

1. Verify the exact A → B → C → D release chain and Last-success pointers.
2. Verify Current and immutable Release byte parity for every bound phase asset.
3. Verify the fixed five-round FMDL-6X1 plan.
4. Verify the fixed six-stage FMDL-6X2 plan.
5. Verify official-primary-first source policy, SEC controlled official execution, Yahoo non-decision-grade fallback, disabled Stooq route and zero paid-subscription budget.
6. Run same-input byte-deterministic replay.
7. Inject nine material failure scenarios and prove every one is blocked.
8. Restore and revalidate from the minimal clean-room asset set.
9. Publish Current, immutable Release, Manifest and Last-success.
10. Generate the seven canonical FMDL-6X2 startup assets.

## Permanent boundaries

- `trade_authority = NONE`
- candidate pool mutations = 0
- simulation mutations = 0
- real-account mutations = 0
- orders = 0
- no live Security Master rows are created in this phase
- no historical or SEC fact-store rows are created in this phase

## Exit

Required status:

`FMDL6X1_FINAL_ACCEPTED`

Next gate:

`FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION`
