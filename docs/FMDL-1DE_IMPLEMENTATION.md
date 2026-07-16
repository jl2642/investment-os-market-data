# FMDL-1D/E — Data Quality Hardening + Scheduled Automation

## 1. Scope

This batch converts the accepted FMDL-1B/C candidate pipeline into a controlled operating data service. It owns:

- hard-gate publication blocking;
- last-known-good retention;
- quarantine evidence;
- atomic current-state promotion;
- event-review flags;
- operating status files;
- confirmed-trading-day scheduling;
- same-date no-op protection;
- GitHub-hosted daily execution and evidence artifacts.

It does not yet make Investment OS consume these files. That remains FMDL-1F.

## 2. Publication state machine

```text
SOURCE FETCH
  -> CANDIDATE
  -> SCHEMA + HARD/SOFT GATES
      -> hard failure: QUARANTINE + RETAIN CURRENT
      -> hard pass: EVENT FLAGS + ARCHIVE METADATA + PUBLISH CURRENT
```

Soft warnings remain visible and may produce `PUBLISHED_WITH_WARNINGS`. They never become silent PASS values.

## 3. Canonical operating paths

```text
outputs/current/
  A_SHARE_UNIVERSE.csv
  DAILY_MARKET_SNAPSHOT.csv
  A_SHARE_UNIVERSE_MANIFEST.json
  DAILY_MARKET_SNAPSHOT_MANIFEST.json
  A_SHARE_UNIVERSE_QUALITY.json
  DAILY_MARKET_SNAPSHOT_QUALITY.json
  MARKET_EVENT_FLAGS.csv
  CURRENT_RELEASE.json

outputs/status/
  LAST_RUN.json
  LAST_SUCCESS.json

outputs/archive/<as_of_date>/<run_id>/
  manifests, quality reports, run report and event flags

outputs/quarantine/<run_id>/
  failure report and available metadata
```

Full accepted CSV history is not duplicated inside archive folders. Git commit history and short-lived workflow artifacts provide the evidence trail while avoiding unnecessary free-repository growth.

## 4. Last-known-good rules

A candidate can replace `outputs/current/` only when:

1. all mandatory files exist;
2. run ID and as-of date agree across report and manifests;
3. file hashes match the manifests;
4. row counts are positive;
5. both datasets have zero hard failures.

A source exception, incomplete candidate, hash mismatch or hard quality failure must leave the current release untouched. `LAST_SUCCESS.json` changes only after a successful promotion.

## 5. Event flags

`MARKET_EVENT_FLAGS.csv` is review evidence, not an automatic correction layer. Initial flags are:

- `SUSPENDED_SECURITY`;
- `EXTREME_RETURN_REVIEW` for absolute daily returns above 35%;
- `ZERO_TURNOVER_REVIEW` for rows labelled traded with zero turnover.

The source observation is never overwritten merely because an event flag exists.

## 6. Schedule

Production workflow: `.github/workflows/fmdl-daily-production.yml`

- Business time: 17:30 Asia/Shanghai.
- GitHub cron: `30 9 * * 1-5` UTC.
- Scheduled runs require a positive result from the public China trading calendar.
- Non-trading days produce `NO_OP_NON_TRADING_DAY`.
- A date already published produces `NO_OP_ALREADY_CURRENT`.
- Manual dispatch supports explicit force and same-date refresh controls.

GitHub cron may start later than the nominal minute. Dataset timestamps and as-of dates, not workflow start punctuality, are authoritative.

## 7. Failure visibility

Every run attempts to write `outputs/status/LAST_RUN.json`. Failed workflows remain visibly failed in GitHub Actions and retain diagnostic artifacts for 14 days. No paid notification, paid runner or paid API is used.

## 8. Free-tier controls

- Linux GitHub-hosted runner only;
- one scheduled run per weekday;
- no minute-level polling;
- no full-history daily download;
- candidate/raw data retained primarily as workflow artifacts;
- no paid API or unapproved trial credits.

## 9. Acceptance gates

FMDL-1D/E is accepted only after a GitHub-hosted run demonstrates:

- contract validation PASS;
- deterministic tests PASS;
- real A-share acquisition PASS;
- current release written;
- current and status hashes/lineage present;
- event flags written;
- archive metadata written;
- no hard quality failure;
- scheduled workflow installed on main;
- a simulated hard failure test proves current-state preservation.

## 10. Phase boundary

FMDL-1D/E completion means the market-data repository can maintain a stable A-share current release automatically. FMDL-1F must still define the exact consumption bundle and update the 股票投资助手 CURRENT package before the full FMDL-1 phase is accepted.

## 11. Main-branch production acceptance

- State: `ACCEPTED_WITH_CONTROLLED_WARNINGS_AND_SCHEDULE_OBSERVATION`
- Stable run: `FMDL1BC_20260716T165927+0800`
- Stable as-of date: `2026-07-16`
- Initial Current publication: atomic Git-tree bootstrap from the already accepted main-branch B/C blobs.
- Scheduled production workflow: active at `17:30 Asia/Shanghai` on confirmed trading weekdays.
- First naturally scheduled main-branch bot write: operating observation item; not a development blocker.
- Detailed evidence: `docs/FMDL-1DE_ACCEPTANCE.md`.
