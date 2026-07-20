# FMDL-4A — Research Handoff Contract & Canonical State-Package Adapter

## Purpose

FMDL-4A converts accepted FMDL-2 screening and FMDL-3E market, financial, valuation and shareholder-return evidence into a canonical research handoff for Public Equity Investing and Investment OS.

It does **not** create company research conclusions, candidate graduation decisions, simulation trades, real-account recommendations, orders or trade authority.

## Entry gate

- `FMDL4_ARCHITECTURE_ACCEPTED`
- Next gate from architecture: `FMDL-4A_RESEARCH_HANDOFF_AND_CANONICAL_STATE_PACKAGE_ADAPTER`

## Canonical base and adapter posture

The external canonical Investment OS base remains:

- package: `股票投资助手_CURRENT.zip`
- status: `ACTIVE_CANONICAL`
- release sequence: `4`
- run ID: `FMDL_1F_INVESTMENT_OS_INTERFACE_20260717_001`
- SHA-256: `cfc25d81c900e11cab594067a8a6220fc7654b9bf2540783d02121da3abda511`

GitHub CI cannot directly read the File Library ZIP bytes. FMDL-4A therefore uses a **SHA-pinned read-only additive overlay** rather than pretending to repack or rewrite the external base.

The Release-5 candidate means:

`Release 4 canonical base + FMDL4A_ADAPTER overlay`

It does not mean that the Release-4 ZIP was modified inside GitHub.

## Evidence Envelope

FMDL-4A creates one `FMDL_EVIDENCE_ENVELOPE` per accepted A-share symbol. Each envelope binds:

- FMDL-2 screening and research priority;
- FMDL-3C-D financial score and confidence;
- FMDL-3E market, capitalization, valuation and shareholder-return evidence;
- source Release IDs;
- quality state and controlled limitations;
- a deterministic semantic hash and evidence ID;
- `trade_authority = NONE`.

Expected universe: 5,528 symbols.

## Public Equity Investing routing

The 100-name FMDL-2 Longlist is converted into a research-priority registry. Routing is research-only:

- immediate research: `idea-generation` then `company-tearsheet`;
- other research priorities: `idea-generation` with later specialist routing as evidence requires;
- company research objects and graduation decisions belong to FMDL-4B;
- Investment OS state transitions belong to FMDL-4C.

Research priority is not candidate-pool admission and is not trade permission.

## Three-package overlay mapping

### CORE_STATIC

- research handoff contract;
- Public Equity routing contract;
- authority firewall.

### EVIDENCE

- full-universe Evidence Envelope Parquet and JSONL;
- 100-name research-priority registry;
- immutable source Release registry;
- limitation register.

### STATE_CURRENT

- read-only FMDL binding state only.

Existing real-account, simulation, candidate-pool, trade-register and position-thesis files are not replaced or modified.

## Acceptance gates

- exactly 5,528 unique Evidence Envelopes;
- exactly 100 unique Longlist handoffs;
- zero unknown Longlist symbols;
- zero missing financial evidence rows;
- zero invalid Evidence Envelope hashes;
- overlay Manifest and ZIP exact match;
- same-input ZIP idempotence;
- Release-4 base identity remains SHA-pinned;
- zero existing-path replacement;
- zero candidate, simulation or real-account mutation;
- zero trade authority.

## Outputs

- `FMDL4A_RELEASE5_ADAPTER_OVERLAY.zip`
- `FMDL4A_RELEASE5_OVERLAY_MANIFEST.json`
- `FMDL4A_ADAPTER/CORE_STATIC/*`
- `FMDL4A_ADAPTER/EVIDENCE/*`
- `FMDL4A_ADAPTER/STATE_CURRENT/FMDL4A_BINDING_STATE.json`
- Decision, independent Validation, immutable Release, Current, Archive and Last-success.

## Controlled limitations

1. The external Release-4 ZIP bytes are not directly readable by GitHub CI. The base remains externally canonical and SHA-pinned.
2. FMDL-4A creates evidence and routing contracts, not company research objects. Research begins in FMDL-4B.
3. No investment state mutation is authorized in FMDL-4A.

## Exit gate

`FMDL4A_RESEARCH_HANDOFF_AND_CANONICAL_ADAPTER_ACCEPTED`

## Next gate

`FMDL-4B_CANDIDATE_RESEARCH_AND_GRADUATION`

## Authority

`RESEARCH_HANDOFF_AND_READ_ONLY_PACKAGE_ADAPTER_ONLY`

`trade_authority = NONE`
