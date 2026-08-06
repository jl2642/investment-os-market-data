# Round 1 — A-share Governed Daily Production

## Scope

Round 1 converts the existing A-share market Current, incremental history, factor refresh and screening chain into one governed daily transaction.

The change is deliberately limited to data production and publication controls. It does not change portfolio quantities, costs, Candidate membership, orders or investment authority.

## Root cause

The previous production sequence relied on three scheduled workflows writing directly to `main`:

1. FMDL daily market Current;
2. FMDL 2B-4 incremental history and factors;
3. FMDL 2C screening.

That model conflicts with protected-branch governance. Replacing each direct push with an independent result branch would also break the data dependency because screening would no longer consume the same run's refreshed market and factor state.

## Accepted design

`.github/workflows/fmdl-daily-production.yml` is the sole scheduled production owner.

Within one checked-out transaction it runs, in order:

1. latest completed-session market Current;
2. Investment OS interface refresh and freshness validation;
3. incremental history and factor operating chain;
4. screening candidate build and independent validation;
5. screening Current materialization.

The accepted transaction is published as:

- one immutable GitHub Actions artifact; and
- one unique `automation/fmdl-daily-<run_id>-a<attempt>` run branch.

Direct writes to protected `main` are disabled. Canonical promotion requires a Draft PR, CI, lineage review and merge.

The former FMDL 2B-4 and FMDL 2C workflows remain as component validation and manually dispatched evidence workflows. They have no schedule and no Canonical write path.

## Operating boundary

- `trade_authority=NONE`
- orders: `0`
- portfolio quantity and cost mutations: not in scope
- Candidate membership mutation: not in scope
- market, history, factor and screening output refresh: in scope

## Acceptance

Round 1 is accepted only after:

1. workflow and regression tests pass;
2. the PR diff contains no direct `main` publication command;
3. the first governed daily run creates a unique run branch and immutable artifact;
4. the branch contains market Current, history Current, factor Current and screening Current from one transaction;
5. repeated runs are idempotent or explicitly no-op;
6. continuous operation is observed for at least three completed A-share trading sessions.
