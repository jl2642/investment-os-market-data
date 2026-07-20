# FMDL-4C — Investment OS Re-entry & State Mutation Controls

## Purpose

FMDL-4C takes the six FMDL-4B research-graduated names back into Investment OS through a role-separated, versioned and rollbackable state layer.

It does not convert research graduation into candidate-pool admission, simulation entry, real-account action or an order.

## Entry gate

- `FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED`
- six research-graduated names;
- each name bound to one FMDL-4A Evidence Envelope and one FMDL-4B Research Object;
- `trade_authority = NONE`.

## Release 6 composition

The accepted state is composed rather than falsely repacking the unreadable external ZIP:

1. Release 4 external canonical base — immutable and SHA-pinned;
2. FMDL-4A Release 5 research/evidence adapter;
3. FMDL-4B research Release;
4. FMDL-4C Release 6 versioned state overlay.

Composition mode:

`IMMUTABLE_BASE_PLUS_VERSIONED_ADDITIVE_STATE_OVERLAYS`

The Release-4 ZIP bytes remain unavailable to GitHub CI. Therefore FMDL-4C does not claim to have inspected or overwritten existing candidate, simulation or real-account rows.

## Re-entry decisions

### Candidate-pool re-entry review queue

- `600900.SH` 长江电力
- `000938.SZ` 紫光股份
- `000333.SZ` 美的集团
- `600018.SH` 上港集团

These names have research cases suitable for candidate-pool reconciliation after entry valuation, portfolio fit and name-specific research gates are closed.

### Shadow-track re-entry review queue

- `300308.SZ` 中际旭创
- `002396.SZ` 星网锐捷

These names have real operating exposure but remain expectations- or quality-of-earnings-gated. They require scenario or earnings work before any candidate-pool admission review.

### No admissions

- simulation admissions: `0`
- real-account admissions: `0`
- orders: `0`

## State transition contract

Each of the six accepted transitions has a deterministic transition ID, evidence and research lineage, role-specific gate results, from/to hashes, rollback token, semantic hash and `trade_authority = NONE`.

Applied state domain: `FMDL4C_REENTRY_REVIEW_QUEUE`

Applied scope: `ADDITIVE_OVERLAY_REENTRY_QUEUE_ONLY`

## Role separation

The candidate router may place a research-graduated name into the re-entry review queue. It cannot alter existing candidate-pool membership until the external base content is reconciled.

The simulation router blocks all six names pending candidate observation, open research gates and an explicit experiment design.

The real-account router blocks all six names pending base-state reconciliation, research readiness, RCM, portfolio fit, ETF alternative review, capital migration review, pre-trade memo and user confirmation.

## Versioned diff and rollback

The overlay moves from an empty FMDL-4C queue to six keyed review records. The diff is additive, deterministic and reversible.

Rollback removes the FMDL-4C overlay while preserving Release 4, the FMDL-4A adapter and FMDL-4B research. A failed run cannot replace Current or Last-known-good.

## Outputs

- six state-transition objects;
- re-entry review queue;
- candidate, simulation and real-account router outputs;
- versioned state diff;
- rollback and LKG proof;
- Release 6 composition manifest;
- deterministic state-overlay ZIP;
- Decision, independent Validation, immutable Release, Current, Archive and Last-success.

## Controlled limitations

1. Release-4 ZIP bytes remain unreadable to GitHub CI; existing membership cannot be reconciled directly.
2. Re-entry queue acceptance is not candidate-pool admission.
3. Current price, portfolio fit, RCM, ETF alternative, capital migration and user confirmation remain open.

## Exit gate

`FMDL4C_INVESTMENT_OS_REENTRY_AND_STATE_CONTROLS_ACCEPTED`

## Next gate

`FMDL-4D_THESIS_ATTRIBUTION_AND_FEEDBACK_LOOP`

## Authority

`INVESTMENT_OS_REENTRY_GOVERNANCE_AND_VERSIONED_OVERLAY_STATE_ONLY`

`trade_authority = NONE`
