# FMDL-3B-1 — Financial Statement Normalization Pilot Acceptance

## Acceptance state

`FMDL3B1_ACCEPTED_NORMALIZATION_PILOT`

This gate confirms that the point-in-time raw fact, normalized long-form, source lineage, revision, comparability, conflict and QA contracts work on the deterministic 13-issuer stress sample. It authorizes FMDL-3B-2 full-universe engineering. It does **not** mark the full FMDL-3B phase complete.

## Canonical main-branch publication

- PR: `#13` — merged;
- merge commit: `6655ebd3143f95d84818bb085afbc931872e5a92`;
- explicit publication trigger: `703a8406b9d43edc30088ad8c5c3d0771c02899c`;
- data publication commit: `897a3a4298c3bf5cf8acbb1a68c798d3dccbb960`;
- release: `FMDL3B1_20260718T120917+0800`;
- published at: `2026-07-18T12:13:29+08:00`;
- status: `FMDL3B1_ACCEPTED_NORMALIZATION_PILOT`;
- independent validation: `19 / 19 PASS`;
- performed statement tie-out checks: `297 / 297 PASS`;
- hard failures: `0`;
- authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`;
- trade authority: `NONE`;
- next phase: `FMDL-3B-2`.

Canonical paths:

- `outputs/financials/pilot/current/FMDL3B1_RELEASE.json`;
- `outputs/financials/pilot/current/`;
- `outputs/financials/pilot/archive/FMDL3B1_20260718T120917+0800/`;
- `outputs/status/FMDL3B1_LAST_SUCCESS.json`.

## Final accepted Head evidence

- final Head: `e6d5bbaf9faf5aa6e2eaee2c0e46a6b7548e9c42`;
- final Head workflow: `29629754261` — success;
- final Head artifact: `8425096823`;
- artifact digest: `sha256:cbb76eb457ac8d98c3a01ea991eddd39d724899e24e47fbef8463e184b4d4ac4`;
- independently inspected semantic-safe candidate run: `FMDL3B1_20260718T115212+0800`;
- candidate independent validation: `19 / 19 PASS`;
- candidate statement tie-out checks: `297 / 297 PASS`.

The main publication reran the same contract and produced the canonical release above.

## Measured results

- sample issuers: `13`;
- supported / controlled quarantine: `11 / 2`;
- non-BSE three-statement bundle support: `100%`;
- official PIT match: `100%`;
- BSE official document index availability: `100%`;
- raw facts: `44,615`;
- mapped provider facts before primary/fallback selection: `6,548`;
- normalized long-form facts: `3,781`;
- decision-grade facts: `3,775`;
- unmapped raw facts retained without forced mapping: `38,067`;
- classified provider conflicts: `6`;
- unclassified conflicts: `0`;
- ambiguous same-source canonical mapping groups: `0` after semantic hardening;
- future facts: `0`;
- source-less decision-grade facts: `0`;
- duplicate effective intervals: `0`;
- revision-ledger entries: `159`;
- source-index rows: `79`;
- QA flags: `2`, both BSE controlled quarantine.

The pilot's mapped coverage is intentionally narrow relative to the full provider field set. The raw store preserves every extracted numeric provider fact, while only clearly supported aliases enter the normalized model-loading layer. FMDL-3B-2 must expand the registry from observed high-frequency unmapped fields without relaxing exact mapping or lineage controls.

## Semantic hardening completed

The first successful real run exposed two taxonomy defects that ordinary arithmetic validation would not detect:

1. Eastmoney exposes both cash-only and cash-and-cash-equivalent opening/closing balances. These are now separate canonical fields; the prior `84` same-source ambiguities are reduced to `0`.
2. `分配股利、利润或偿付利息支付的现金` includes interest and is no longer mapped to pure dividends. It is represented as `distribution_profit_interest_cash_paid`.

Six Eastmoney/Sina differences for this broad cash-flow line at China Merchants Bank remain visible as `CLASSIFIED_CONTROLLED_EXCLUSION`. No working value is silently selected.

## Accepted outputs

- `FMDL3B_RAW_FACTS.csv`;
- `FMDL3B_NORMALIZED_LONG.csv`;
- `FMDL3B_SOURCE_INDEX.csv`;
- `FMDL3B_REVISION_LEDGER.csv`;
- `FMDL3B_COMPARABILITY_BRIDGE.csv`;
- `FMDL3B_CONFLICT_LOG.csv`;
- `FMDL3B_AMBIGUOUS_MAPPING_GROUPS.csv`;
- `FMDL3B_QA_FLAGS.csv`;
- `FMDL3B_VALIDATION_CHECKS.csv`;
- `FMDL3B_SUPPORT_MAP.csv`;
- `FMDL3B_COVERAGE.csv`;
- decision, validation, manifest and release files.

## Controlled limitations

1. This is a deterministic pilot, not full-market statement coverage.
2. The two BSE issuers have official CNINFO document indexes but no structured decision-grade facts.
3. Prior official revisions are retained as document versions when providers expose only the latest structured value; historical pre-restatement values are never fabricated.
4. Unmapped provider fields remain raw/audit-only.
5. Six classified provider conflicts require official-document reconciliation during FMDL-3B-3.
6. No financial factor, investment conclusion, candidate promotion or portfolio action is authorized.

## FMDL-3B-2 authorization

FMDL-3B-2 must implement deterministic full-universe sharding, bounded runtime and storage, primary-source extraction, fallback-on-failure rather than unconditional duplication where appropriate, BSE CNINFO document extraction, field-frequency analysis, controlled quarantine, immutable manifests and resumable publication. Full FMDL-3B acceptance remains gated by FMDL-3B-3 and FMDL-3B-4.