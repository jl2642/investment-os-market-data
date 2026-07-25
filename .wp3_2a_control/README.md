# WP3-2A control channel

This directory is a transient GitHub Actions trigger channel. Connector-authored branches and pull requests let ChatGPT start governed workflows without asking the user to operate the GitHub Actions UI.

## Universe Refresh

Supported autonomous path:

1. create a one-use `automation/wp3-2a-run-*` branch from `main`;
2. add `.wp3_2a_control/run_request.json`;
3. open a transient pull request to `main`;
4. the refresh bridge validates the request, dispatches `wp3_2a_universe_refresh.yml` on `main`, records the downstream run ID and URL, and closes the transient PR;
5. ChatGPT monitors the downstream run, evidence and data-proposal PR.

Refresh request:

```json
{
  "accepted_session": "2026-07-24",
  "provider_policy": "sina_public",
  "create_pr": true
}
```

## Protected Universe Acceptance

After a reviewed data-proposal PR has been merged, the supported autonomous path is:

1. create a one-use `automation/wp3-2a-accept-*` branch from `main`;
2. add `.wp3_2a_control/accept_request.json`;
3. open a transient pull request to `main`;
4. the acceptance bridge validates the exact merged proposal path and confirmation phrase;
5. it dispatches `wp3_2a_accept_universe.yml` on `main`, records the run receipt, and closes the transient PR;
6. the protected environment `wp3-2a-data-acceptance` remains a human approval gate;
7. after approval, the workflow creates a separate acceptance PR for human merge.

Acceptance request:

```json
{
  "proposal_path": "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/PROPOSALS/WP3_2A_UNIVERSE_PROPOSAL_20260724_30162751251_1",
  "confirmation": "ACCEPT_UNIVERSE_PROPOSAL"
}
```

Trigger requests are never included in proposal or acceptance commits. Both bridges keep `trade_authority=NONE` and do not mutate Candidate, Research, real-account, simulation, or order state.
