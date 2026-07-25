#!/usr/bin/env bash
set -Eeuo pipefail

BRANCH_BASE="${1:?branch required}"
TITLE="${2:?title required}"
BODY_FILE="${3:?body file required}"
LABELS="${4:-wp3-2a,data-proposal}"
BASE="${5:-main}"
RUN_KEY="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
BRANCH="${BRANCH_BASE}-${RUN_KEY}"
LOG_DIR="${RUN_DIR:-.wp3_2a_run}"
LOG_FILE="$LOG_DIR/CREATE_OR_UPDATE_PR.log"
EXIT_FILE="$LOG_DIR/CREATE_OR_UPDATE_PR_EXIT_CODE.txt"
RECEIPT_FILE="$LOG_DIR/PROPOSAL_PR_RECEIPT.json"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$EXIT_FILE"; echo "create_or_update_pr exit_code=$rc branch=$BRANCH"' EXIT

echo "Preparing proposal PR branch: $BRANCH"
echo "Base branch: $BASE"
echo "trade_authority=NONE"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

# Preserve this run's generated proposal, reset onto the latest base, and
# reapply only the generated working-tree changes. Each run publishes to a
# unique branch so no force push or stale lease is required.
git stash push --include-untracked --message "wp3-2a-generated-$RUN_KEY" >/dev/null || true
git fetch origin "$BASE"
git checkout -B "$BRANCH" "origin/$BASE"
if git stash list | grep -q "wp3-2a-generated-$RUN_KEY"; then
  git stash pop >/dev/null
fi

# Stage only the governed WP3-2A evidence/proposal area. Investment Current,
# Candidate, Research, account, simulation and order state stay out of scope.
git add investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A
if git diff --cached --quiet; then
  echo "No governed proposal changes; PR not created."
  exit 2
fi

echo "Staged proposal paths:"
git diff --cached --name-only

git commit -m "$TITLE"
git push --set-upstream origin "HEAD:refs/heads/$BRANCH"

PR_URL=$(gh pr create \
  --base "$BASE" \
  --head "$BRANCH" \
  --title "$TITLE" \
  --body-file "$BODY_FILE")
echo "Created proposal PR: $PR_URL"

gh pr view "$BRANCH" \
  --json number,url,state,headRefName,baseRefName,title \
  > "$RECEIPT_FILE"
cat "$RECEIPT_FILE"

IFS=',' read -ra ITEMS <<< "$LABELS"
for label in "${ITEMS[@]}"; do
  gh pr edit "$BRANCH" --add-label "$label" || true
done
