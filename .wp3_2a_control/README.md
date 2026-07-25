# WP3-2A control channel

This directory is a transient GitHub Actions trigger channel. A branch named `automation/wp3-2a-run-*` may add `run_request.json` here to start a Universe Refresh without using the GitHub UI.

The request file is never included in data-proposal commits. Supported fields:

```json
{
  "accepted_session": "2026-07-24",
  "provider_policy": "sina_public",
  "create_pr": true
}
```

The workflow validates the request, retains evidence, keeps `trade_authority=NONE`, and never mutates Candidate, Research, account, simulation, or order state.
