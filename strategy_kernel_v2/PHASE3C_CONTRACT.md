# Strategy Kernel v2 — Phase 3C Decision / Capital Replay Contract

## Status
**VALIDATED COMPLETE_BOUNDED_REPLAY_TERMINAL_NONREPLAYABILITY_FINDING.** Phase 3C remains shadow-only. The bounded historical replay and full Canonical-tree replayability audit are complete. Phase 3D is **not authorized** by this closeout because neither candidate model produced a valid contemporaneous historical replay set.

## 3C-1 — Point-in-time structured feature extraction
- Source authority is exclusively the Phase 3A selected evidence set for each checkpoint.
- Every registered historical source is loaded from its exact registered `commit_sha:path` via `git show`.
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
- Explicit `NO_DECISION`, `NOT_DECISION_GRADE`, `WATCH`, or `NO_TRADE` semantics normalize to `NO_ACTION` before generic `HOLD` tokens are considered, preventing research holds from being misreported as portfolio retention.

## Bounded replay result
Across the seven Phase 3A checkpoints:
- registered historical sources read by exact commit/path: **29/29**;
- Legacy evaluable security×checkpoint instances: **29**;
- Phase-2 probabilistic/vector evaluable instances: **0**;
- simple non-probabilistic/Pareto evaluable instances: **0**;
- model-specific evidence fetches: **0**;
- subjective feature fills: **0**;
- retrospective probability backfills: **0**;
- retrospective scenario backfills: **0**.

This is a model replayability/input-burden finding, not a model-performance conclusion.

## Canonical-tree historical input recovery audit
The continuation gate was resolved by scanning the complete Canonical checkpoint trees under `investment_os_runtime`, `evidence`, and `outputs`, not only the 29 Phase 3A registered records.

Validated audit result:
- checkpoint count: **7**;
- keyword-candidate file occurrences inspected: **673**;
- exact-model-field file occurrences: **114**;
- proxy-like legacy-field file occurrences: **147**;
- complete Phase-2 probability/vector packet occurrences: **0**;
- complete simple-Pareto five-field packet occurrences: **0**;
- unregistered complete Phase-2 packet occurrences: **0**;
- unregistered complete simple-Pareto packet occurrences: **0**.

Conclusion: `NO_COMPLETE_CANDIDATE_MODEL_INPUT_PACKET_FOUND_IN_CANONICAL_CHECKPOINT_TREES`.

Therefore the blocker is **not a Phase 3A registration omission**. On the bounded historical corpus:
- `PHASE2_PROBABILISTIC_VECTOR = HISTORICALLY_NONREPLAYABLE_WITHOUT_RETROSPECTIVE_INPUT_CREATION`;
- `SIMPLE_NON_PROBABILISTIC_PARETO = HISTORICALLY_NONREPLAYABLE_WITHOUT_NEW_TRANSFORMATION_RULES`;
- `LEGACY_POLICY_BASELINE = BOUNDED_HISTORICAL_REPLAY_AVAILABLE`.

Legacy/proxy fields such as `evidence_score`, `quality_score`, `portfolio_fit_score`, `risk_penalty`, `race_confidence`, `current_weight`, `base_case_expected_return`, `return_vs_completed_close`, and unweighted `driver_based_scenarios` remain historical facts. They may not be relabelled as Phase 3B probability/confidence/concentration/execution or simple-Pareto dimensions merely to improve replayability.

## Completion and downstream gate
Phase 3C is complete as a **terminal negative replayability finding** for this bounded corpus. Completion does not imply successful multi-model historical comparison.

Phase 3D remains blocked. Before Phase 3D can start, governance must explicitly determine the subsequent evaluation path for candidate models that have no contemporaneous replay outputs. Phase 3C itself does not revise the fixed Phase 3B model forms or silently change the 3A→3F sequence.

## Non-output
Phase 3C does not calculate subsequent-return performance, regret, forecast calibration, model winner, target weights, investment recommendations, user decisions, Candidate/portfolio mutations, orders, or trades.

`orders=0`; `trade_authority=NONE`.
