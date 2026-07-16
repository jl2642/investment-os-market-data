# FMDL-1B/C Acceptance — A-share Universe Builder + Daily Market Snapshot

## Release identity

- Phase: `FMDL-1B/C — A-share Universe Builder + Daily Market Snapshot`
- Acceptance state: `ACCEPTED_WITH_CONTROLLED_WARNINGS`
- Main implementation commit: `7b97e16506236619a51186da663563105f6fc924`
- Registered-lineage fix commit: `456297a38643eddf01609e6f8b1c22885186ea62`
- Final real candidate data commit: `08d950bbf8ee8aec88eedbdba384aaf6ea3ecde7`
- Run ID: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Generated at: `2026-07-16T16:59:27+08:00`
- AKShare version: `1.18.64`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`

## Real execution evidence

The GitHub-hosted production runner completed all of the following successfully:

1. Frozen-contract validation.
2. Deterministic regression tests.
3. Real free-source market-wide acquisition.
4. Canonical normalization.
5. Schema and quality-gate evaluation.
6. Manifest and hash generation.
7. Commit of real candidate data and raw evidence to the main branch.
8. Exact reconciliation of runtime provider IDs with the frozen source registry.

The Eastmoney market-wide endpoint disconnected the GitHub Azure runner. The explicit registered fallback `akshare.stock_zh_a_spot` / `sina_public` completed successfully. The fallback, volume unit and upstream failure are preserved in the manifest and run report rather than silently substituted.

## Accepted datasets

### A-share universe

- Rows: `5,529`
- Columns: `22`
- Schema errors: `0`
- Duplicate natural keys: `0`
- Symbol validity: `100%`
- Required identity fill: `100%`
- Listing-date fill: `100%`
- Hard failures: `0`
- QA: `PASS_WITH_WARNINGS`
- Candidate status: `DEGRADED`
- SHA-256: `094595f4c7760a6a85cb214b35625d6e7f26a3eeba2716ecded8c999c7a621d1`

Controlled warning: free exchange enrichment provides industry coverage of approximately `58.26%`, below the soft target of `90%`. This does not affect security identity or full-market coverage and remains a later enrichment item.

### Daily market snapshot

- Rows: `5,529`
- Columns: `21`
- Universe coverage: `100%`
- Traded rows: `5,525`
- Positive close ratio for traded rows: `100%`
- Negative volume rows: `0`
- Negative turnover rows: `0`
- Maximum return-reconciliation difference: `0.0005` percentage points
- Hard failures: `0`
- QA: `PASS_WITH_WARNINGS`
- Candidate status: `DEGRADED`
- SHA-256: `4a35ded77b277ec2927ee6e8ee207757e896186b9db48fd2ee86b20aa33c8ba9`

Controlled warnings:

- The Sina fallback bulk interface does not provide market-cap or valuation fields; FMDL-3 owns those fields.
- One extreme-return row remains a soft event-review warning and does not break return reconciliation.
- Three source rows encoded with zero prices were deterministically classified as suspended rather than treated as -100% traded returns: `002677.SZ`, `301234.SZ`, `920685.BJ`.

## Registered sources

The final runtime lineage uses exact registered provider IDs:

- `sina_public`
- `sse_public`
- `szse_public`
- `bse_public`
- `eastmoney_public` remains registered as the degraded preferred bulk route.

## Accepted deliverables

```text
outputs/candidate/A_SHARE_UNIVERSE.csv
outputs/candidate/DAILY_MARKET_SNAPSHOT.csv
outputs/candidate/A_SHARE_UNIVERSE_MANIFEST.json
outputs/candidate/DAILY_MARKET_SNAPSHOT_MANIFEST.json
outputs/candidate/A_SHARE_UNIVERSE_QUALITY.json
outputs/candidate/DAILY_MARKET_SNAPSHOT_QUALITY.json
outputs/candidate/FMDL_1BC_RUN_REPORT.json
outputs/candidate/FMDL_1BC_RUN_REPORT.md
datasets/raw/2026-07-16/FMDL1BC_20260716T165927+0800/
```

## Phase boundary

FMDL-1B/C is accepted because real A-share universe and daily snapshot datasets were produced on GitHub-hosted infrastructure and every hard gate passed.

This acceptance does **not** promote the candidate files to `outputs/current/`, establish a scheduled daily operating release, or make Investment OS consume the files. Those controls remain with:

- `FMDL-1D — Data Quality and Last-known-good Hardening`
- `FMDL-1E — Scheduled GitHub Actions Automation`
- `FMDL-1F — Investment OS Interface and Final FMDL-1 Acceptance`

## Next authorized batch

`FMDL-1D/E — Data Quality Hardening + Scheduled Automation`
