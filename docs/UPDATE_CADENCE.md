# Update Cadence v1.0.0

## 1. Business timezone

All market-operating schedules use `Asia/Shanghai`. GitHub Actions cron expressions use UTC and must document the conversion.

## 2. FMDL-1 target cadence

### Trading calendar and universe

- Scheduled on weekdays before the daily snapshot or as part of the same run.
- Universe identity is refreshed each trading day during MVP hardening.
- After stability is demonstrated, a weekly full refresh plus daily status delta may be adopted.

### Daily market snapshot

- Target run time: 17:30 China Standard Time on weekdays.
- Equivalent GitHub Actions cron: 09:30 UTC, Monday–Friday.
- The workflow must first consult the trading calendar.
- On a confirmed non-trading day, record a successful `NO_OP_NON_TRADING_DAY`; do not create a false new snapshot.

### Contract validation

- Run on every pull request and push affecting `config/`, `schemas/`, `docs/` or pipeline code.

### Manual run

- `workflow_dispatch` is required for testing, recovery and controlled reruns.
- Manual reruns must create a new run ID and must not overwrite archived evidence.

## 3. Publication window

A daily candidate may be published only when:

- the expected trading session is complete;
- the source-reported date matches the expected trading date;
- freshness and quality gates pass;
- the manifest and archive are written before current pointers change.

## 4. Retry policy

- Maximum automatic attempts: 3 per source route.
- Retry class: transient connection, timeout or 5xx-like failure only.
- Suggested backoff: 15 seconds, 60 seconds, 180 seconds.
- Schema drift, empty critical data or wrong trading date are not fixed by blind retries; they trigger quarantine.

## 5. Retention

- `outputs/current/`: newest accepted release only.
- `outputs/archive/`: immutable dated accepted releases.
- Failed/quarantined run evidence: retain at least 30 days during MVP and operating acceptance.
- Raw captures: retain enough for reproducibility subject to repository-size and source-policy constraints.
- Large historical data may move to compressed release assets or rolling storage after FMDL-7; this is not required for FMDL-1.

## 6. GitHub free-tier control

- Use one Linux runner job where practical.
- Cache Python dependencies but not mutable market output.
- Avoid minute-level schedules and redundant full-history downloads.
- Daily snapshot should retrieve current market data, not rebuild the entire historical database.
- Weekly/monthly jobs must remain disabled until their implementation is accepted.

## 7. Downstream operating cadence

FMDL data generation does not automatically change Investment OS state.

- Daily data may support holdings/candidate monitoring.
- FMDL-2 screening is expected after the accepted daily dataset is available.
- Public Equity Investing deep research should be triggered only for prioritized candidates, not every listed security.
- Real portfolio action remains user-confirmed.

## 8. Schedule changes

Any schedule change must update `config/schedules.json`, document the UTC/business-time conversion and preserve a clear effective date.
