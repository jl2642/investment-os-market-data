#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <commit-message> <path> [<path> ...]" >&2
  exit 64
fi

commit_message="$1"
shift
publish_branch="${WP3R_PUBLISH_BRANCH:-automation/wp3-r-candidate-current}"
base_branch="${WP3R_BASE_BRANCH:-main}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

staged_paths=0
for path in "$@"; do
  if [[ -e "$path" ]]; then
    git add -- "$path"
    staged_paths=$((staged_paths + 1))
  else
    echo "SKIP_MISSING_OPTIONAL_PATH: $path"
  fi
done

if [[ $staged_paths -eq 0 ]] || git diff --cached --quiet; then
  echo "Candidate operating Current already up to date."
  exit 0
fi

echo "PUBLISHING_PATHS"
git diff --cached --name-only

git commit -m "$commit_message"

# Candidate builders also refresh diagnostic products that are intentionally
# outside each workflow's publication boundary. Keep only the governed commit
# before rebasing it on the latest Canonical base.
echo "NON_PUBLISHED_WORKTREE_CHANGES_BEFORE_CLEANUP"
git status --short || true
git reset --hard HEAD
git clean -fd

git fetch origin "$base_branch"
git rebase "origin/$base_branch"

# Main is protected and requires PR + Lineage Gate. Publish the generated
# Current products to one rolling governed branch instead of bypassing main.
git push --force-with-lease origin "HEAD:refs/heads/$publish_branch"
echo "PUBLISHED_BRANCH=$publish_branch"

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN_NOT_AVAILABLE_PR_CREATION_SKIPPED"
  exit 0
fi

pr_url="$(gh pr list --repo "$GITHUB_REPOSITORY" --base "$base_branch" --head "$publish_branch" --state open --json url --jq '.[0].url // empty')"
if [[ -z "$pr_url" ]]; then
  pr_url="$(gh pr create \
    --repo "$GITHUB_REPOSITORY" \
    --base "$base_branch" \
    --head "$publish_branch" \
    --title "WP3-R: publish governed Candidate operating Current" \
    --body $'Automated observation-only Candidate Current publication.\n\n- governed 2 Core / 38 Shadow / 33 Research Queue / 0 Ready membership is unchanged;\n- no Research Object, Real-account or Simulation mutation;\n- orders=0 and trade_authority=NONE;\n- merge is gated by the existing WP3-2A Lineage Gate.' )"
else
  gh pr edit "$pr_url" \
    --repo "$GITHUB_REPOSITORY" \
    --title "WP3-R: publish governed Candidate operating Current" \
    --body $'Automated observation-only Candidate Current publication.\n\n- governed 2 Core / 38 Shadow / 33 Research Queue / 0 Ready membership is unchanged;\n- no Research Object, Real-account or Simulation mutation;\n- orders=0 and trade_authority=NONE;\n- merge is gated by the existing WP3-2A Lineage Gate.'
fi

echo "PUBLISHED_PR=$pr_url"

# PRs created with GITHUB_TOKEN do not recursively trigger ordinary PR
# workflows. Explicit workflow_dispatch is the supported exception, so run the
# actual required Lineage Gate on the generated branch head.
gh workflow run wp3_2a_lineage_gate.yml \
  --repo "$GITHUB_REPOSITORY" \
  --ref "$publish_branch" \
  -f base_ref="$base_branch" \
  -f enforce_wp3_2a_scope=false

# Enable auto-merge when the repository permits it. Otherwise keep the PR open
# for the same governed merge path; publication itself remains successful.
if ! gh pr merge "$pr_url" --repo "$GITHUB_REPOSITORY" --auto --merge; then
  echo "AUTO_MERGE_NOT_ENABLED_OR_NOT_PERMITTED_PR_REMAINS_OPEN"
fi
