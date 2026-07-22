# FMDL-6X1-A — Existing Pilot Audit & Dual Activation Contract

## Objective

Open the next stage of US-equity development without fabricating a brokerage channel. This phase audits the accepted FMDL-6 pilot and the Investment OS Release-8 canonical base, preserves both as immutable upstream evidence, and replaces the prior all-or-nothing activation concept with two independent gates.

## Verified upstream baseline

- Investment OS package: `股票投资助手_CURRENT.zip`
- Release ID: `INVESTMENT_OS_R8_20260720_501345e84562`
- Release sequence: `8`
- Package SHA-256: `479d375da1586419a98bb2821342cf691b0d1358882b66bc1601fd717ab2a9aa`
- Manifest files checked: `61`
- Nested runtime packages checked: `4`
- Package and nested ZIP integrity: `PASS`
- FMDL-5-FINAL: accepted Hong Kong Stock Connect operating base
- FMDL-6-FINAL: accepted US interface and resume-ready pilot
- Trade authority: `NONE`

The Release-8 package remains the current Investment OS binary canonical base. FMDL-5 and FMDL-6 remain immutable GitHub overlays until a later controlled single-package refresh.

## Audit conclusion

The existing pilot is sufficient to preserve identity architecture, source-interface knowledge, failure taxonomy and restore logic. It is not sufficient for production research because it intentionally excludes a full universe, historical store, production financial normalization, factors, screening and research graduation.

The user currently has no US brokerage channel. That fact blocks only broker-specific eligibility and real-account integration; it does not economically or technically justify blocking construction of a research-only US-equity platform.

## Dual activation model

### Gate 1 — Research Production Gate

Status after FMDL-6X1-A: `OPEN_FOR_CONTROLLED_BUILD`

Authorizes:

- anticipated, channel-agnostic US research-universe design;
- official identity and listing master construction;
- full historical market/corporate-action/FX evidence build after later gates;
- SEC filing and financial-fact normalization after later gates;
- factor, screening and research production after later gates;
- research-only cross-market duplicate-exposure analysis.

Does not authorize:

- broker eligibility claims;
- candidate-pool admission;
- simulation admission;
- real-account admission;
- order generation.

### Gate 2 — Brokerage & Real-Account Gate

Status: `CLOSED_NO_CHANNEL`

Required before opening:

1. an actual US investment channel exists;
2. tradable venues and instrument types are documented;
3. base currency, FX, fees, tax, settlement and fractional-share constraints are documented;
4. any broker-specific symbol restrictions are reconciled;
5. the user explicitly approves account integration.

## No-channel operating rule

Until Gate 2 opens, every US security must carry both:

- a research status; and
- a separate channel status of `CHANNEL_ELIGIBILITY_PENDING`.

A security may be research-grade while remaining ineligible for candidate, simulation or real-account state transitions.

## Fixed FMDL-6X1 sequence

- 6X1-A — existing pilot audit and dual activation contract;
- 6X1-B — anticipated research universe and instrument boundary;
- 6X1-C — source, cost and execution-route revalidation;
- 6X1-D — full-build contract and 6X2 handoff;
- 6X1-FINAL — operational acceptance.

Maximum planned rounds: `5`.
Maximum targeted repair rounds: `2`.

## Acceptance gates

- exact Release-8 package identity is bound;
- accepted FMDL-5-FINAL and FMDL-6-FINAL are bound;
- prior pilot evidence is preserved without mutation;
- Research Production Gate is open only for controlled future phases;
- Brokerage & Real-Account Gate remains closed;
- candidate, simulation, real-account and order mutations equal zero;
- `trade_authority = NONE`;
- same-input validation is deterministic.

## Expected exit

`FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED`

Next gate:

`FMDL-6X1-B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY`
