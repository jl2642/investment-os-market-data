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

# Main is protected and requires PR + Lineage Gate. Publish generated Current
# products to one rolling automation branch. The dedicated promotion workflow
# creates/updates the governed PR and dispatches the actual required gate.
if git ls-remote --exit-code --heads origin "$publish_branch" >/dev/null 2>&1; then
  git fetch origin "$publish_branch:refs/remotes/origin/$publish_branch"
  git push --force-with-lease="refs/heads/$publish_branch:refs/remotes/origin/$publish_branch" \
    origin "HEAD:refs/heads/$publish_branch"
else
  git push origin "HEAD:refs/heads/$publish_branch"
fi

echo "PUBLISHED_BRANCH=$publish_branch"
echo "GOVERNED_PR_PROMOTION_DELEGATED=true"
