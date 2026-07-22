# FMDL-6X1-A PR Summary

## What changes

- verifies and binds the readable Investment OS Release-8 package;
- freezes a five-round FMDL-6X1 plan;
- replaces the old single activation gate with separate Research Production and Brokerage/Real-Account gates;
- opens only controlled research-production development;
- adds machine-readable contract, schema, deterministic validator, negative regression tests and CI workflow.

## Why

The user wants the US research capability completed but currently has no US brokerage channel. Treating the missing broker as a blocker for all research development would be unnecessarily restrictive; treating it as present would be false. The dual-gate model preserves both truth and execution progress.

## Safety and state impact

- Investment OS Release 8 unchanged;
- FMDL-0 through FMDL-6 accepted releases unchanged;
- candidate, simulation and real-account mutations: zero;
- orders: zero;
- `trade_authority = NONE`.
