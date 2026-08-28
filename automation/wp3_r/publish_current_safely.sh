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
paths=("$@")

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

staged_paths=0
for path in "${paths[@]}"; do
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

echo "GENERATED_PATHS"
git diff --cached --name-only
git commit -m "$commit_message"
generated_commit="$(git rev-parse HEAD)"

# Clean non-published diagnostics but retain the generated commit object.
git reset --hard HEAD
git clean -fd

git fetch origin "$base_branch" --no-tags

remote_exists=false
expected_remote_sha=""
if git ls-remote --exit-code --heads origin "refs/heads/$publish_branch" >/dev/null 2>&1; then
  remote_exists=true
  git fetch origin "$publish_branch:refs/remotes/origin/$publish_branch" --force --no-tags
  expected_remote_sha="$(git rev-parse "refs/remotes/origin/$publish_branch")"
  # Preserve all previously accepted rolling products, then merge the latest
  # protected main. This avoids one WP3-R workflow erasing another workflow's
  # Current files merely because both publish to the same rolling branch.
  git checkout -B "$publish_branch" "refs/remotes/origin/$publish_branch"
  if ! git merge --no-edit "origin/$base_branch"; then
    git merge --abort || true
    echo "WP3R_ROLLING_MAIN_MERGE_FAILED" >&2
    exit 2
  fi
else
  git checkout -B "$publish_branch" "origin/$base_branch"
fi

# Overlay only this workflow's governed products from its generated commit.
restored=0
for path in "${paths[@]}"; do
  if git cat-file -e "$generated_commit:$path" 2>/dev/null; then
    git checkout "$generated_commit" -- "$path"
    git add -- "$path"
    restored=$((restored + 1))
  fi
done
if [[ $restored -eq 0 ]]; then
  echo "WP3R_NO_GENERATED_PATHS_RESTORED" >&2
  exit 3
fi

if ! git diff --cached --quiet; then
  git commit -m "$commit_message"
fi

# The branch is now a descendant of the previous rolling branch (when present)
# and latest main. A force-with-lease is retained only as a race guard; normal
# publication is fast-forward and must never replace unrelated WP3-R state.
if [[ "$remote_exists" == "true" ]]; then
  git push     --force-with-lease="refs/heads/$publish_branch:$expected_remote_sha"     origin "HEAD:refs/heads/$publish_branch"
else
  git push origin "HEAD:refs/heads/$publish_branch"
fi

echo "PUBLISHED_BRANCH=$publish_branch"
echo "PREVIOUS_ROLLING_HEAD=${expected_remote_sha:-NONE}"
echo "GENERATED_COMMIT=$generated_commit"
echo "GOVERNED_PR_PROMOTION_DELEGATED=true"
