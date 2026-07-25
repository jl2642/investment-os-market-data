# WP3-2A Repository Settings and Two-Phase Rollout

## 1. Capability facts

- The required check name is exactly `WP3-2A / Lineage Gate`.
- The required lineage workflow runs for every pull request targeting `main`.
  It deliberately has no `paths` filter, because a skipped required workflow can
  leave the check pending and block merges.
- Investment-object mutation enforcement is activated only for branches matching
  `automation/wp3-2a-*`.
- The repository default `GITHUB_TOKEN` permission remains read-only. Individual
  jobs request only the permissions they need.
- GitHub Actions must not be allowed to approve pull requests.

## 2. Environment plan caveat

Create these environments:

- `wp3-2a-data-acceptance`
- `wp3-2a-screening-approval`

When GitHub supports required reviewers for the repository plan and visibility,
set `@jl2642` as the reviewer. On GitHub Free, required reviewers are available
only for public repositories. For a private Free repository, the fallback control
is:

1. exact workflow confirmation phrase;
2. a separate generated pull request;
3. human review and human merge;
4. no direct write to `main`.

The administration tool detects this condition and records the fallback rather
than claiming that a required reviewer was configured.

## 3. Two-phase rollout

### Phase A — publish implementation

1. Apply the hardened delta patch to a branch.
2. Run automation tests and the existing 35 Runtime tests.
3. Open a bootstrap pull request.
4. Review and merge the bootstrap pull request manually.

Do not configure `WP3-2A / Lineage Gate` as a required check before the workflow
exists on `main`.

### Phase B — configure and activate

After the bootstrap PR is merged:

1. Run `python automation/wp3_2a/github_admin.py status`.
2. Run `python automation/wp3_2a/github_admin.py configure`.
3. Confirm the two environments exist.
4. Confirm branch protection requires:
   - a pull request;
   - at least one approval;
   - code-owner review;
   - `WP3-2A / Lineage Gate`;
   - conversation resolution;
   - no force pushes;
   - no deletions.
5. Run the first manual Universe Refresh.
6. Review the workflow artifact and generated data-proposal PR.
7. Approve the pending PR workflow run when GitHub requests approval for a PR
   created by `GITHUB_TOKEN`.
8. Do not merge an acceptance or screening PR without user review.

## 4. Actions settings

Recommended repository settings:

- Default workflow permissions: read-only.
- GitHub Actions approving PRs: disabled.
- GitHub Actions policy: GitHub-owned actions plus repository-local code.
- Secret policy: no broker credentials, no trade credentials and no order API
  tokens.
- `trade_authority=NONE`.

## 5. Controlled PR chain

```text
Universe Refresh
  -> Gate v3 PASS inside refresh run
  -> data-proposal PR
  -> required Lineage Gate
  -> human review and merge
  -> manual acceptance workflow
  -> acceptance PR
  -> human merge
  -> manual proposal-only screening
  -> screening proposal PR
```

No step automatically modifies Candidate membership, Research Objects, the
simulation ledger, the real account or orders.
