# FMDL-4B — Candidate Research & Graduation

## Purpose

FMDL-4B converts the 100-name FMDL-2 research queue into a fully traceable research-stage registry and applies source-backed Public Equity Investing judgment to the 20 `A_IMMEDIATE_RESEARCH` names.

The phase creates research conclusions only. It does not alter the Investment OS candidate pool, simulation portfolio, real account, trade register or position thesis.

## Scope

Every Longlist name receives an Evidence Envelope binding, research stage, graduation decision, reason code, next workflow and explicit zero state-mutation and zero trade-authority fields. The 80 names outside the current A-priority cohort are deferred rather than mechanically rejected.

Each A-priority name receives a deterministic `PUBLIC_EQUITY_RESEARCH_OBJECT` containing business model, competitive position, owner/governance baseline, earnings drivers, FMDL valuation context, catalysts, risks, variant perception, Why Now, first rejection, investability conditions, Prove/Kill checks, sources, Evidence IDs and next workflow.

## Graduation semantics

`GRADUATED` means `RESEARCH_CASE_READY_ONLY_NOT_CANDIDATE_POOL_ADMISSION_NOT_TRADE_READY`.

It does not mean an attractive entry price, candidate-pool promotion, simulation admission, real-account admission, buy recommendation or trade authority.

`DEFERRED` means a material research, valuation, data, event or capacity gate remains open. `REJECTED` means the current screen signal does not justify further active research; it does not remove the security from the full-market data system.

## Expected decision distribution

For the 20 formal objects: 6 Graduated, 9 Deferred and 5 Rejected. Across all 100 names: 6 Graduated, 89 Deferred and 5 Rejected.

## Hard gates

- exactly 100 stage and decision rows;
- exactly 20 formal Research Objects;
- at least two current public sources per formal object;
- zero unknown or missing Evidence bindings;
- zero raw-score-only decisions;
- zero mechanical rejection of the 80 non-active names;
- deterministic semantic hashes;
- zero Investment OS state mutation;
- zero order generation and zero trade authority.

## Outputs

- `FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.jsonl`
- `FMDL4B_PUBLIC_EQUITY_RESEARCH_OBJECTS.csv`
- `FMDL4B_RESEARCH_STAGE_REGISTRY.csv`
- `FMDL4B_GRADUATION_DECISIONS.csv`
- `FMDL4B_SOURCE_LEDGER.json`
- `FMDL4B_NO_RAW_SCORE_PROMOTION_PROOF.json`
- `FMDL4B_ZERO_STATE_MUTATION_PROOF.json`
- Decision, independent Validation, Release, Current, Archive and Last-success.

## Controlled limitations

1. Formal objects are limited to the current 20-name A-priority cohort.
2. They are public-disclosure baselines, not full initiating-coverage reports or forecast models.
3. Graduation remains a research-only status.

## Exit and next gate

Exit: `FMDL4B_CANDIDATE_RESEARCH_AND_GRADUATION_ACCEPTED`

Next: `FMDL-4C_INVESTMENT_OS_REENTRY_AND_STATE_MUTATION_CONTROLS`

Authority: `PUBLIC_EQUITY_RESEARCH_AND_GRADUATION_ONLY`; `trade_authority = NONE`.
