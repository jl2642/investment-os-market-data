# FMDL-6 START HERE

## Current program purpose

FMDL-6 is a **US Equity Interface and Resume-Ready Pilot**, not a full US equity production system.

The user currently has no direct US equity investment channel. The system therefore builds only the interfaces, identity model, 24-security technical benchmark, minimal data chain, quality/cost benchmark and machine-readable recovery package required for a fast future restart.

## Current scope

- benchmark size: 24 securities;
- official-source-first identity and SEC filing interfaces;
- free or free-tier market-data interface benchmark;
- small-sample price, corporate-action, filing and financial-fact chain;
- point-in-time, revision, failure and Last Known Good controls;
- no full universe;
- no full historical backfill;
- no production factor or screening engine;
- no candidate-pool, simulation or real-account integration;
- no orders;
- `trade_authority = NONE`.

## Authoritative restore order

1. `outputs/status/FMDL6_0_LAST_SUCCESS.json`
2. `outputs/fmdl6_0/current/FMDL6_START_HERE.md`
3. `outputs/fmdl6_0/current/FMDL6_0_RELEASE.json`
4. `outputs/fmdl6_0/current/FMDL6_ACTIVATION_GATE.json`
5. `outputs/fmdl6_0/current/FMDL6_DEFERRED_BACKLOG.json`
6. `config/fmdl6_0_us_equity_resume_ready_pilot_architecture.json`
7. `docs/FMDL-6-0_US_EQUITY_INTERFACE_AND_RESUME_READY_PILOT_ARCHITECTURE.md`

## Program sequence

- FMDL-6-0 — architecture and scope freeze
- FMDL-6A — market contract and security identity
- FMDL-6B — source interface and access benchmark
- FMDL-6C — 24-security benchmark pool
- FMDL-6D — minimal end-to-end data chain
- FMDL-6E — quality, failure and cost benchmark
- FMDL-6-FINAL — resume-ready operational acceptance

## Deferred future build

The following phases are not authorized until the activation gate opens:

- FMDL-6X1 — channel and investable-universe refresh
- FMDL-6X2 — full universe and historical build
- FMDL-6X3 — factors, screening and research production
- FMDL-6X4 — Investment OS and portfolio integration

## Activation rule

A full build requires all of the following:

- the user has a real US investment channel;
- the tradable-security scope is documented;
- account currency, tax and execution constraints are documented;
- pilot source interfaces are revalidated;
- the user explicitly approves a full build.

Partial, implicit or inferred activation is forbidden.

## Current next gate

`FMDL-6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY`
