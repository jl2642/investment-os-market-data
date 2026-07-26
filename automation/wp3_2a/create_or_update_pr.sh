#!/usr/bin/env bash
set -Eeuo pipefail

BRANCH_BASE="${1:?branch required}"
TITLE="${2:?title required}"
BODY_FILE="${3:?body file required}"
LABELS="${4:-wp3-2a,data-proposal}"
BASE="${5:-main}"
RUN_KEY="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"
BRANCH="${BRANCH_BASE}-${RUN_KEY}"
RECEIPT_DIR="${RUN_DIR:-.wp3_2a_run}"
RECEIPT_FILE="$RECEIPT_DIR/PROPOSAL_PR_RECEIPT.json"
LINEAGE_RECEIPT_FILE="$RECEIPT_DIR/LINEAGE_DISPATCH_RECEIPT.json"

mkdir -p "$RECEIPT_DIR"

echo "Preparing governed PR branch: $BRANCH"
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

# Proposal and WP3-2B screening outputs live under the governed WP3-2A
# evidence/lineage area. Investment Current, Candidate, Research, account,
# simulation and order state stay out of scope.
git add investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A
if git diff --cached --quiet; then
  echo "No governed proposal changes; PR not created."
  exit 2
fi

echo "Staged governed paths:"
git diff --cached --name-only

git commit -m "$TITLE"
git push --set-upstream origin "HEAD:refs/heads/$BRANCH"

PR_URL=$(gh pr create \
  --base "$BASE" \
  --head "$BRANCH" \
  --title "$TITLE" \
  --body-file "$BODY_FILE")
echo "Created governed PR: $PR_URL"

gh pr view "$BRANCH" \
  --json number,url,state,headRefName,baseRefName,title \
  > "$RECEIPT_FILE"
cat "$RECEIPT_FILE"

IFS=',' read -ra ITEMS <<< "$LABELS"
for label in "${ITEMS[@]}"; do
  gh pr edit "$BRANCH" --add-label "$label" || true
done

# PRs created by GITHUB_TOKEN do not reliably emit a pull_request workflow.
# Dispatch the exact required Lineage Gate on the head branch so the protected
# check is attached to the proposal commit without human republishing.
started_epoch=$(date -u +%s)
gh workflow run wp3_2a_lineage_gate.yml \
  --repo "$GITHUB_REPOSITORY" \
  --ref "$BRANCH" \
  -f base_ref="$BASE" \
  -f enforce_wp3_2a_scope=true

run_id=""
run_url=""
run_status=""
for _ in $(seq 1 24); do
  gh run list \
    --repo "$GITHUB_REPOSITORY" \
    --workflow wp3_2a_lineage_gate.yml \
    --event workflow_dispatch \
    --branch "$BRANCH" \
    --limit 20 \
    --json databaseId,createdAt,status,conclusion,url \
    > /tmp/wp3_2a_lineage_runs.json

  receipt=$(STARTED_EPOCH="$started_epoch" python - <<'PY'
import datetime as dt
import json
import os

threshold = int(os.environ['STARTED_EPOCH']) - 10
candidates = []
for run in json.load(open('/tmp/wp3_2a_lineage_runs.json', encoding='utf-8')):
    stamp = str(run.get('createdAt') or '')
    try:
        epoch = int(dt.datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp())
    except Exception:
        continue
    if epoch >= threshold:
        candidates.append((epoch, run))
if candidates:
    run = sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
    print(f"{run['databaseId']}\t{run['url']}\t{run['status']}")
PY
  )
  if [[ -n "$receipt" ]]; then
    IFS=$'\t' read -r run_id run_url run_status <<< "$receipt"
    break
  fi
  sleep 5
done

if [[ -z "$run_id" ]]; then
  echo "Lineage Gate dispatch accepted but receipt not resolved." >&2
  exit 3
fi

python - <<PY
import json
from pathlib import Path
Path(${LINEAGE_RECEIPT_FILE@Q}).write_text(
    json.dumps({
        "run_id": int(${run_id@Q}),
        "url": ${run_url@Q},
        "status": ${run_status@Q},
        "branch": ${BRANCH@Q},
        "base": ${BASE@Q},
        "trade_authority": "NONE",
    }, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
cat "$LINEAGE_RECEIPT_FILE"
