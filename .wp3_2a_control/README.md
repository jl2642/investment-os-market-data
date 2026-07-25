# WP3-2A control channel

This directory is a transient GitHub Actions trigger channel. A branch named `automation/wp3-2a-run-*` may add `run_request.json` here without using the GitHub Actions UI.

Because connector-created branch pushes are not guaranteed to emit an observable workflow run, the supported autonomous path is:

1. create a one-use `automation/wp3-2a-run-*` branch from `main`;
2. add `.wp3_2a_control/run_request.json`;
3. open a transient pull request to `main`;
4. the bridge validates the request, dispatches `wp3_2a_universe_refresh.yml` on `main`, records the downstream run ID and URL as a PR comment, and closes the transient PR;
5. ChatGPT reads the receipt and monitors the downstream run, logs, artifacts and proposal PR.

Supported fields:

```json
{
  "accepted_session": "2026-07-24",
  "provider_policy": "sina_public",
  "create_pr": true
}
```

The trigger request is never included in a data-proposal commit. The bridge keeps `trade_authority=NONE` and never mutates Candidate, Research, account, simulation, or order state.
