# FMDL-3C Roadmap

## FMDL-3C-A — Factor Architecture & Contract Design

Freeze the product boundary, factor dictionary, temporal construction, denominator rules, sector routing, quality states, validation gates and publication contract.

**Exit:** `FMDL3CA_FACTOR_ARCHITECTURE_AND_CONTRACT_ACCEPTED`

## FMDL-3C-B — Financial Factor Engine MVP

Build the PIT derived-input layer, calculate the contracted factor set over the full supported universe, store factor history, retain full lineage and publish a candidate factor dataset. No composite score is produced.

Key implementation work:

- sector-profile resolver;
- TTM and average-balance constructors;
- formula DSL evaluator;
- factor-version intervals;
- shard execution and aggregation;
- row-level quality states;
- immutable candidate artifacts.

**Exit:** `FMDL3CB_FULL_UNIVERSE_FACTOR_MVP_ACCEPTED`

## FMDL-3C-C — Validation, Sector Routing & Hardening

Run full-market economic sanity checks, resolve industry/sector applicability, validate tails and coverage, test replay and restatements, and harden controlled exclusions. Add specialized financial-sector factors only through separate accepted contracts.

**Exit:** `FMDL3CC_FACTOR_VALIDATION_AND_HARDENING_ACCEPTED`

## FMDL-3C-D — Score & Investment OS Interface

Design score eligibility, transformations and research packets after factor validity is established. Any composite score must expose factor values, quality states, weights, transformations and missingness. FMDL-3C-D may provide research-priority evidence but cannot create trade authority.

**Exit:** `FINANCIAL_FACTOR_CURRENT_ACCEPTED`

## Handoff

After FMDL-3C-D, the next program stage is FMDL-3D valuation, capitalization, dividend and shareholder-return evidence. FMDL-4 later combines accepted market, financial and valuation evidence for issuer-level research and decision gates.
