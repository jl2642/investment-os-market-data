# FMDL-1D/E Acceptance — Data Quality Hardening + Scheduled Automation

## Release identity

- Phase: `FMDL-1D/E — Data Quality Hardening + Scheduled Automation`
- Acceptance state: `ACCEPTED_WITH_CONTROLLED_WARNINGS_AND_SCHEDULE_OBSERVATION`
- Implementation commit: `7bfcd692366718fe51391a5d58aa0f46d41ef37a`
- Stable data run: `FMDL1BC_20260716T165927+0800`
- As-of date: `2026-07-16`
- Initial publication time: `2026-07-16T17:46:35+08:00`
- Cost policy: `FREE_OR_FREE_TIER_ONLY`

## Acceptance evidence

The GitHub-hosted pull-request production workflow completed contract validation, deterministic tests, real free-source acquisition, candidate QA, publication staging, event-flag creation and operating evidence generation successfully.

Validated workflow runs:

- Contract validation: `29486998620` — SUCCESS
- Candidate validation: `29486998709` — SUCCESS
- Daily production validation: `29486998546` — SUCCESS
- Operating artifact digest: `sha256:27e9b0f15075d39c82ba6ec18a7d4999a1d9b33bf1895304b3640ee0a0ce5bc8`

The connector could not enumerate or dispatch ordinary main-branch schedule runs. Therefore, the first stable Current release was atomically bootstrapped from the already accepted main-branch B/C dataset by reusing its immutable Git blobs; no market values were recomputed, altered or fabricated. The installed production workflow remains active for subsequent weekday operation.

## Stable Current release

- Universe rows: `5,529`
- Snapshot rows: `5,529`
- Hard quality failures: `0`
- QA state: `PASS_WITH_WARNINGS`
- Market-wide provider: `sina_public`
- Universe SHA-256: `094595f4c7760a6a85cb214b35625d6e7f26a3eeba2716ecded8c999c7a621d1`
- Snapshot SHA-256: `4a35ded77b277ec2927ee6e8ee207757e896186b9db48fd2ee86b20aa33c8ba9`
- Event flags: `7`
- Event-flag SHA-256: `b5cb5fe2b0df1876e18e3f62a7b8bbc56e58f611fbe971a76c57db4998d01ee2`

Canonical files now exist under `outputs/current/`, with release control in `CURRENT_RELEASE.json` and operating state in `outputs/status/`.

## Last-known-good and failure controls

- A candidate cannot replace Current unless required files, run identity, as-of date, hashes, positive row counts and all hard gates pass.
- Hard failure writes quarantine evidence and preserves Current.
- `LAST_SUCCESS.json` changes only after a successful promotion.
- Regression tests prove a simulated hard failure does not overwrite the existing Current release.

## Schedule

- Workflow: `.github/workflows/fmdl-daily-production.yml`
- Business time: `17:30 Asia/Shanghai`
- Cron: `30 9 * * 1-5` UTC
- Non-trading day: `NO_OP_NON_TRADING_DAY`
- Already-current date: `NO_OP_ALREADY_CURRENT`
- Trading-calendar failure: fail closed and retain LKG
- Paid APIs and paid runners: prohibited

The first naturally scheduled main-branch write remains an operating observation item rather than a development blocker. Any failed run remains visible in GitHub Actions and cannot silently overwrite Current.

## Controlled warnings

- Industry coverage remains approximately 58.26%.
- Sina bulk fallback does not supply market-cap or valuation fields.
- One extreme-return record remains explicitly flagged for review.
- Eastmoney remains degraded on the GitHub Azure runner; Sina is the registered active fallback.

## Phase boundary

FMDL-1D/E is complete. Stable A-share Current data and scheduled operating controls now exist, but Investment OS consumption and 股票投资助手 CURRENT package binding remain FMDL-1F.

## Next authorized phase

`FMDL-1F — Investment OS Interface + Final FMDL-1 Acceptance`
