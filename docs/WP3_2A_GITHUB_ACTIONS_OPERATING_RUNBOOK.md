# WP3-2A GitHub Actions Operating Runbook

## Publication

From an authenticated workstation with GitHub CLI:

```bash
python WP3_2A_GITHUB_BOOTSTRAP.py \
  --repo jl2642/investment-os-market-data \
  --delta-zip 股票投资助手_WP3_2A_GITHUB_ACTIONS_HARDENED_DELTA_PATCH_20260725.zip \
  --workdir ./wp3_2a_bootstrap
```

Review and merge the bootstrap PR manually.

## Configuration after merge

```bash
python automation/wp3_2a/github_admin.py \
  --repo jl2642/investment-os-market-data status

python automation/wp3_2a/github_admin.py \
  --repo jl2642/investment-os-market-data configure
```

The configure command is fail-transparent:

- it records whether required environment reviewers were supported;
- it preserves existing required status checks;
- it adds `WP3-2A / Lineage Gate`;
- it does not merge pull requests;
- it does not trigger an investment action.

## First manual Universe Refresh

Use the latest provider session automatically:

```bash
python automation/wp3_2a/github_admin.py \
  --repo jl2642/investment-os-market-data \
  trigger --provider-policy configured --wait
```

Use the user-approved 2026-07-23 session only when the provider timestamp agrees:

```bash
python automation/wp3_2a/github_admin.py \
  --repo jl2642/investment-os-market-data \
  trigger --accepted-session 2026-07-23 \
  --provider-policy eastmoney_public --wait
```

## Audit the run and generated proposal PR

```bash
python automation/wp3_2a/github_admin.py \
  --repo jl2642/investment-os-market-data \
  review --output-dir .wp3_2a_admin/review
```

Review must confirm:

- raw bytes and SHA are present;
- acquisition manifest status is PASS;
- Gate v3 status is PASS;
- row count and unique code count are plausible;
- SSE, SZSE and BSE are covered;
- provider session evidence is present;
- Identity Diff additions/deletions/name changes are explainable;
- zero investment-object mutation proof is PASS;
- Runtime Acceptance is PASS;
- `orders=0`;
- `trade_authority=NONE`.

## Human-controlled progression

A successful refresh creates a data proposal only. The user must review and merge
that PR. Current promotion still requires the separate acceptance workflow and a
second human-merged PR. Governed screening is manual, research-only and
proposal-only.
