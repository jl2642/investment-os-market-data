# FMDL-3B — Financial Statement Store & Normalization

## Current execution scope

FMDL-3B is implemented as four engineering gates. This commit executes the first gate rather than declaring the entire phase complete:

1. **FMDL-3B-1 — Field Registry & Normalization Pilot** — real cross-sector pilot, PIT/revision storage, raw facts, normalized long-form facts, source index, conflict/QA/comparability outputs and publication controls.
2. **FMDL-3B-2 — Full-Universe Initial Statement Build** — deterministic sharded extraction over the accepted A-share Universe, including CNINFO official-document extraction for the BSE.
3. **FMDL-3B-3 — Comparability & Restatement Hardening** — changed-label detection, provider backfill detection, known-revision replay and conflict recovery.
4. **FMDL-3B-4 — Statement Current & Acceptance** — full statement Current, LKG, missingness/conflict maps and final `POINT_IN_TIME_STATEMENT_STORE_ACCEPTED` gate.

The system must not label FMDL-3B complete before gates 2–4 pass.

## Pilot design

The pilot reuses the accepted 13-issuer FMDL-3A stress sample and covers general non-financial issuers, banks, insurance, securities firms, pre-profit/negative-earnings issuers, and all five A-share boards.

SH/SZ/ChiNext/STAR use Eastmoney structured statements as primary and Sina as fallback. CNINFO owns announcement identity, revision identity and daily point-in-time availability. BSE issuers retain official-document source index and controlled quarantine until FMDL-3B-2 builds document extraction.

## Data layers

### Raw fact store

One row per issuer, source route, statement, report period, provider field and latest structured revision binding. It preserves the original provider field, source value and native-unit state, exact source route and location, official filing linkage, announcement and availability fields, revision sequence and effective interval, mapping state, and evidence/confidence labels.

Unmapped provider fields remain in the raw store and are never force-mapped.

### Normalized long store

One row per issuer, canonical line item, period, selected source and revision. It follows the Public Equity Investing normalization contract:

- original and standard line labels are both retained;
- missing values remain missing;
- cumulative Q1/H1/Q3 and annual FY bases are explicit;
- CNY and units are explicit;
- capex and dividends use explicit cash-flow sign rules;
- material primary/fallback conflicts become audit-only controlled exclusions;
- no source-less fact can be decision-grade.

### Revision ledger

Every identified official filing version receives a sequence and effective interval. When the provider exposes only the latest restated structured value, prior filings remain as `DOCUMENT_ONLY_PRIOR_REVISION_NO_HISTORICAL_STRUCTURED_VALUE`; the system does not fabricate historical pre-restatement values.

### Comparability and QA

The pilot emits `FMDL3B_COMPARABILITY_BRIDGE.csv`, `FMDL3B_CONFLICT_LOG.csv`, `FMDL3B_QA_FLAGS.csv`, and `FMDL3B_VALIDATION_CHECKS.csv`.

Balance-sheet and cash-flow tie-outs are run only when all required canonical inputs are present. A skipped check is not represented as a pass.

## Pilot exit gate

`FMDL3B1_ACCEPTED_NORMALIZATION_PILOT`

This gate authorizes full-universe engineering. It does not authorize financial factors, valuation conclusions, candidate promotion, portfolio actions or trading.