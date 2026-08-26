# Strategy Kernel v2 — Plan Changelog

## 2026-08-26 — Phase 1C plan synchronization
Phase 1C was formalized between Decision Object normalization and capital comparison so underwriting completeness, comparison readiness and decision readiness are not conflated. No effective policy or authority changed.

## 2026-08-26 — Phase 1C validation closeout
Persisted deterministic bundle, tests and validation record; synchronized implementation status to validated shadow-only. No phase-order or authority change.

## 2026-08-26 — Phase 2 execution refinement
**Reason:** deep-research findings and Phase 1C evidence gaps show that immediately creating a single ranked score would embed unvalidated utility weights and risk confusing measurement with policy.

**Changed:**
- retained top-level Phase 2 but split execution into 2A Comparator Contract/Engine, 2B Governed Refresh Adapters, and 2C Current Shadow Comparison Pack;
- Phase 2A uses transparent return/downside/confidence/concentration/execution vectors and a weight-free Pareto frontier;
- explicitly prohibits a scalar policy score in 2A;
- requires every `READY_AFTER_REFRESH` item to satisfy all recorded refresh requirements through a governed overlay;
- requires an explicit rate/provenance for any cash/reference baseline;
- Phase 2C requires at least two meaningful non-reference eligible capital uses or emits `NO_COMPARISON`.

**Not changed:** no Core Static rule, Candidate membership, economic state, target weight, user decision, order authority or trade authority changes; `orders=0`, `trade_authority=NONE`.

## 2026-08-26 — Phase 2B governed refresh contract
**Reason:** Phase 2A correctly returned 0 eligible / 8 blocked from the current Phase 1C objects. A safe mechanism is needed to admit genuinely refreshed evidence without relaxing the evidence standard merely to generate a ranking.

**Changed:**
- added a governed refresh packet schema with explicit provenance, evidence classes, requirement coverage, material-gap resolution, scenarios and comparison inputs;
- `READY_AFTER_REFRESH` requires exact coverage of all recorded refresh requirements;
- clarified that `NOT_READY` can become comparison-ready only after a governed `FUNDAMENTAL_REUNDERWRITE` resolves all original refresh requirements and material evidence gaps;
- price/valuation-only refresh cannot override a material fundamental evidence gap;
- a refreshed shadow copy may change comparison readiness only; source decision readiness and Canonical authority are preserved.

**Validation:** 13/13 unit tests pass; no user decision, Candidate mutation, economic mutation, order or trade is generated.

## 2026-08-26 — Phase 2C real-evidence closeout
**Reason:** Phase 2C was required to test the comparison architecture against actual stored governed evidence, not to manufacture a ranking.

**Observed evidence outcome:**
- latest governed A-share market/portfolio marks are materially fresher than main research state and reach 2026-08-25;
- freshness alone does not supply probability-weighted scenarios, explicit confidence, concentration cost, execution friction or missing fundamental underwriting;
- WP4B completion flags do not expose the underlying scenario payload needed by the comparator;
- 601138 has legacy unweighted scenarios and fresh price but not the full current fundamental/probability packet;
- 605090 and 301215 remain material-evidence-gap cases;
- no object can form a complete Phase 2B packet without adding new assumptions.

**Changed:**
- persisted a source-by-source current evidence inventory for all eight objects;
- added a generic Phase 2C pack builder that accepts only real Phase 2B refresh packets and emits `NO_COMPARISON` when fewer than two non-reference uses are eligible;
- persisted the current pack as `NO_COMPARISON`: 0 eligible / 8 blocked / 0 real refresh packets applied;
- advanced the development state to the boundary before historical replay.

**Not changed:** no effective Core Static rule, Candidate state, real/simulation state, target weight, user decision or trade permission changed.

## 2026-08-26 — ROADMAP_DRIFT_CORRECTION / Program Governance Hardening
**Detected drift:** during Phase 2 plan synchronization, the macro roadmap accidentally omitted the originally required Phase 4 Forward Parallel Shadow Validation and made the documentation appear to allow Phase 3 to lead directly toward effective migration.

**Impact assessment:**
- implementation through Phase 2C remained shadow-only;
- no Core Static policy, Candidate state, real/simulation economic state, target weight, user decision, order authority or trade authority changed;
- therefore this was a program-control/documentation drift, not an effective-policy migration.

**Correction:**
- restored the explicit macro lifecycle `Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5`;
- established `MASTER_PROGRAM_CHARTER.md` as the human-readable master charter and `PROGRAM_CONTRACT.json` as its machine-readable lifecycle contract;
- added `PROGRAM_STATE.json` with Phase 2 complete-shadow state, Phase 3 next, Phase 4 mandatory, and Phase 5 migration forbidden;
- expanded Phase 3 into 3A–3F and restored Phase 4 forward parallel shadow validation plus Phase 5 governed migration sequence;
- added machine-checkable program consistency validation so future macro-phase omission or illegal Phase 3→5 promotion fails validation.

**Not changed:** Phase 0–2 implementation semantics and all authority boundaries remain unchanged; `orders=0`, `trade_authority=NONE`.

**Promotion consequence:** Phase 3 implementation may start only after this correction is governed and the program-consistency check passes. Phase 3 can promote only to Phase 4; Phase 5 requires separate Phase 3 + Phase 4 evidence.

## 2026-08-26 — Program consistency validator acceptance hardening
**Reason:** final governance acceptance review found that the first validator checked the Charter, Roadmap and Execution Plan but did not actually read `PLAN_CHANGELOG.md`, despite the Charter listing it as a controlled artifact. It also hard-coded the temporary Phase 2 → 3 state and checked only part of the machine-readable promotion contract.

**Changed:**
- `PLAN_CHANGELOG.md` is now read by the validator and must contain the roadmap-drift correction record while that correction flag is active;
- all mandatory promotion gates in `PROGRAM_CONTRACT.json` must be true;
- current macro phase must follow the contract-declared promotion edge dynamically rather than a Phase-2-specific hard code;
- Phase 3/4/5 completion and entry dependencies are machine-checked;
- `PROGRAM_STATE.json` and `CURRENT_PHASE_STATUS.json` must remain in lockstep on promotion, phase-start and authority fields;
- zero-mutation and `orders=0` / `trade_authority=NONE` invariants are checked across the controlled state surfaces;
- governance regression coverage is expanded accordingly.

**Not changed:** no macro lifecycle, investment model, Core Static rule, Candidate state, portfolio state, target weight, user decision, order authority or trade authority changed.

**Promotion consequence:** Phase 3A remains blocked until this hardened validator passes on the governed correction head.

## 2026-08-26 — Phase 3A Point-in-time Evidence Ledger / bounded acceptance
**Reason:** historical replay cannot be valid if a file's embedded `as_of` date is confused with the date the information actually became Canonical. The same problem applies to later research revisions, market marks, Candidate state and portfolio context.

**Implemented:**
- added a pure point-in-time ledger engine with offset-aware `available_at`, immutable source commit identity, explicit authority domain and stable evidence-stream keys;
- default replay authority is `CANONICAL_MAIN` only;
- later versions are excluded until their availability timestamp and remain visible only as future evidence;
- checkpoint-bound Candidate, Real Account and market/portfolio marks preserve the exact Canonical state at that checkpoint, including stale embedded watermarks;
- added a real registry of 29 Canonical evidence records and seven Canonical replay checkpoints spanning 2026-07-26 through 2026-08-18 across the eight current Strategy Kernel v2 objects;
- bound decision-relevant streams including WP4/WP4B, 601138 WP5 P0, HKCU P5C valuation, HKCU 00669 BUY REVIEW and D2 R1/R2;
- added deterministic materialization from registry + checkpoint inputs rather than treating a copied derived ledger as authority.

**Implementation correction during review:** an initially hand-materialized derived ledger accidentally listed out-of-scope 00669/601138 future evidence in the first Core2-only checkpoint. The source registry and builder were correct; the hand-derived file was deleted immediately. Real-registry tests now verify that unrelated future assets are not surfaced and the ledger is rebuilt from authority inputs. No economic or policy state was affected.

**Validation:**
- 16 generic no-hindsight/authority/validation tests pass;
- 8 real-registry acceptance tests pass;
- total local Phase 3A suite = 24/24;
- all seven declared checkpoint requirement sets are reproducible in the bounded registry;
- at the 2026-08-13 checkpoint, 000719/301215 R1 is selected while R2 remains future evidence;
- R2 becomes selectable only at the 2026-08-18 Canonical merge;
- retrospective probability backfills=0; retrospective scenario backfills=0; generated model/recommendation/user decision=0; `orders=0`; `trade_authority=NONE`.

**Scope judgment:** Phase 3A is accepted as `VALIDATED_COMPLETE_SCOPE_BOUNDED`, sufficient to start Phase 3B model-form plumbing. It is not accepted as statistically sufficient historical coverage. `phase3_historical_validation_complete=false` and `phase3f_promotion_eligible=false`; broader date/regime coverage and Phase 3B–3E remain mandatory before Phase 3F can pass.

**Not changed:** no effective Strategy/Core rule, Candidate state, Real/Simulation state, target portfolio, user investment decision, order authority or trade authority changed.