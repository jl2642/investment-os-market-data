# FMDL-6-FINAL — Resume-Ready Operational Acceptance

## Purpose

FMDL-6-FINAL closes the bounded US Equity Interface and Resume-Ready Pilot. It does not convert the US pilot into a production investment system and does not authorize a full-universe build, research Longlist, candidate admission, portfolio integration or orders.

The accepted operating posture after this phase is:

- A-share capability: operational through the accepted Investment OS and FMDL stack;
- Hong Kong Stock Connect capability: operational through FMDL-5-FINAL;
- US equity capability: resume-ready technical pilot only;
- `trade_authority = NONE` for the US pilot.

## Bound release chain

| Phase | Release sequence | Accepted Release |
|---|---:|---|
| FMDL-6-0 | 19 | `FMDL6_0_20260722_b63e9fb88a33` |
| FMDL-6A | 20 | `FMDL6A_20260722_99a4726452b1` |
| FMDL-6B | 21 | `FMDL6B_20260722_de3d0a9b7703` |
| FMDL-6C | 22 | `FMDL6C_20260722_0e06fd37937c` |
| FMDL-6D | 23 | `FMDL6D_20260722_5e207a0a13a8` |
| FMDL-6E | 24 | `FMDL6E_20260722_44e038992a68` |

The cross-market operating base remains:

- FMDL-5-FINAL: `FMDL5FINAL_20260721_a43285d1ee25`;
- Investment OS canonical base: `INVESTMENT_OS_R8_20260720_501345e84562`.

## Acceptance work

FMDL-6-FINAL performs all of the following from accepted repository assets without live-source refresh:

1. validates every component Last-success pointer;
2. validates Current Release and Manifest identity;
3. validates every Manifest file hash and byte size;
4. validates Current, Archive and Immutable Manifest parity;
5. validates contiguous Release sequences 19–24;
6. validates the FMDL-5-FINAL and Investment OS Release-8 base;
7. validates that the US activation gate remains closed;
8. validates all four deferred future phases;
9. performs a minimal clean-room restore without chat memory;
10. injects pointer loss, Release mismatch, Manifest file loss, trade-authority escalation and activation-gate leakage failures;
11. proves the upstream Last Known Good assets are unchanged;
12. performs independent candidate validation and same-input replay;
13. publishes a machine-readable resume handoff, user operating guide and File Library retention instruction.

## Final restore order

1. `outputs/status/FMDL6_FINAL_LAST_SUCCESS.json`
2. `outputs/fmdl6_final/current/FMDL6FINAL_RESUME_HANDOFF.json`
3. `outputs/fmdl6_final/current/FMDL6FINAL_RELEASE_CHAIN.json`
4. `outputs/fmdl6_final/current/FMDL6FINAL_ACTIVATION_GATE.json`
5. `outputs/fmdl6_final/current/FMDL6FINAL_DEFERRED_BACKLOG.json`
6. `outputs/fmdl6_final/current/FMDL6FINAL_USER_OPERATING_GUIDE.md`
7. `outputs/fmdl6_final/current/FMDL6FINAL_RELEASE.json`
8. `outputs/fmdl6_final/current/FMDL6FINAL_MANIFEST.json`

This order is sufficient for a new conversation to identify the current state and continue development. Previous chat context is not a dependency.

## Future US activation

A future US full build remains closed until every condition is true:

- the user has a real US-market investment channel;
- the tradable security scope is documented;
- account currency, tax and execution constraints are documented;
- the pilot source interfaces are revalidated;
- the user explicitly approves the full build.

After activation, resume in this order:

1. `FMDL-6X1_CHANNEL_AND_INVESTABLE_UNIVERSE_REFRESH`
2. `FMDL-6X2_FULL_UNIVERSE_AND_HISTORICAL_BUILD`
3. `FMDL-6X3_FACTOR_SCREENING_AND_RESEARCH_PRODUCTION`
4. `FMDL-6X4_INVESTMENT_OS_AND_PORTFOLIO_INTEGRATION`

A dedicated US-equity development conversation is supported and is the preferred route for a long future build. Other project conversations may continue normal A-share, Hong Kong, real-holding, simulation and candidate-pool operations in parallel.

## File Library posture

The File Library remains the compact human-facing canonical recovery layer. Keep only:

1. the current Investment OS Release 8 canonical ZIP;
2. the matching Release 8 pointer / START_HERE asset.

FMDL source code, workflows, technical releases, Current, Archive, Immutable and Last-success assets remain authoritative in GitHub. Separate FMDL-5 or FMDL-6 candidate artifacts do not need to be uploaded to File Library.

## Exit status

`FMDL6_RESUME_READY_OPERATIONAL_ACCEPTANCE_ACCEPTED`

Next operating state:

`FMDL_PROGRAM_PHASE_COMPLETE_OPERATING_OBSERVATION`
