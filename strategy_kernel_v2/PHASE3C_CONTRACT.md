# Strategy Kernel v2 — Phase 3C Decision / Capital Replay Contract

## Status
Implementation candidate. Phase 3C remains shadow-only and does not authorize Phase 3D, Phase 4, or any economic action until acceptance is complete.

## 3C-1 — Point-in-time structured feature extraction
- Source authority is exclusively the Phase 3A selected evidence set for each checkpoint.
- Every historical source is loaded from its exact registered `commit_sha:path` via `git show`.
- Extraction is model-neutral and occurs before any model execution.
- Every extracted field retains `provenance_evidence_ids` resolving inside the checkpoint.
- Unsupported source shapes remain unsupported rather than being heuristically filled.
- Unweighted scenarios remain unweighted; missing probabilities, confidence, concentration cost, execution friction, or simple-Pareto dimensions remain missing.
- Present-day `source_registry.py` is not a historical source.

## 3C-2 — Shared-packet replay
- The Phase 3B model forms remain fixed.
- Legacy, Phase-2 probabilistic/vector, and simple non-probabilistic/Pareto forms all consume the same immutable packet fingerprint.
- Models may not fetch evidence or adapt the evidence set themselves.
- Historical outcomes are normalized only as shadow replay states: `ADMITTED`, `BLOCKED`, `PRIORITIZED`, `RETAINED`, `REDUCED`, `NO_ACTION`, or `OBSERVED_UNMAPPED` when a Legacy disposition cannot be mapped without inference.

## Current expected bounded-seed behavior
The existing historical corpus contains explicit contemporaneous Legacy dispositions in several records, but it does not contain a complete explicit Phase-2 probability/vector packet or complete explicit five-field simple-Pareto packet. Therefore current acceptance expects:
- Legacy evaluable instances > 0;
- Phase-2 probabilistic evaluable instances = 0;
- simple-Pareto evaluable instances = 0;
- no retrospective fill to change those counts.

This expected result is a data/model-usability finding, not a model-performance conclusion.

## Non-output
Phase 3C does not calculate subsequent-return performance, regret, forecast calibration, model winner, target weights, investment recommendations, user decisions, Candidate/portfolio mutations, orders, or trades. Those remain outside Phase 3C; Phase 3D is not started merely because the replay harness executes.

`orders=0`; `trade_authority=NONE`.
