#!/usr/bin/env bash
set -euo pipefail
BRANCH="${1:?branch required}"
TITLE="${2:?title required}"
BODY_FILE="${3:?body file required}"
LABELS="${4:-wp3-2a,data-proposal}"
BASE="${5:-main}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

# Preserve generated changes, reset the automation branch to the latest base,
# then reapply only this run's generated changes.
git stash push --include-untracked --message wp3-2a-generated >/dev/null || true
git fetch origin "$BASE"
git fetch origin "$BRANCH:refs/remotes/origin/$BRANCH" >/dev/null 2>&1 || true
git checkout -B "$BRANCH" "origin/$BASE"
if git stash list | grep -q 'wp3-2a-generated'; then
  git stash pop >/dev/null
fi

git add .github automation docs investment_os_runtime
if git diff --cached --quiet; then
  echo "No repository changes; PR not created."
  exit 0
fi
git commit -m "$TITLE"
git push --force-with-lease origin HEAD:"refs/heads/$BRANCH"
if gh pr view "$BRANCH" --json number >/dev/null 2>&1; then
  gh pr edit "$BRANCH" --title "$TITLE" --body-file "$BODY_FILE"
else
  gh pr create --base "$BASE" --head "$BRANCH" --title "$TITLE" --body-file "$BODY_FILE"
fi
IFS=',' read -ra ITEMS <<< "$LABELS"
for label in "${ITEMS[@]}"; do
  gh pr edit "$BRANCH" --add-label "$label" || true
done
