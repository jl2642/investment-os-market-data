#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <commit-message> <path> [<path> ...]" >&2
  exit 64
fi

commit_message="$1"
shift

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
# outside each workflow's publication boundary. A dirty worktree makes
# `git pull --rebase` exit 128. Keep the committed Current products and remove
# every non-published tracked/untracked by-product before rebasing.
echo "NON_PUBLISHED_WORKTREE_CHANGES_BEFORE_CLEANUP"
git status --short || true
git reset --hard HEAD
git clean -fd

git fetch origin main
git rebase origin/main
git push origin HEAD:main
