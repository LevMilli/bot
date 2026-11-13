#!/usr/bin/env bash
# Roll back one merged PR by opening a revert PR. Paper only.
#
#   paper-bots/tools/rollback.sh 708          # revert PR #708 (opens a PR, does not merge)
#   paper-bots/tools/rollback.sh last         # revert the newest merge on main
#
# The fastest fix for a bad deploy is the host's own "Redeploy" on the last good
# deployment (see docs/RUNBOOK.md, "Roll back a bad deploy"). This script is the
# follow-up so main matches what is running. It never pushes to main and never
# merges; a person reviews the revert PR. Needs git and gh.
set -euo pipefail
target="${1:-}"
if [ -z "$target" ]; then
  echo "Usage: $0 <PR number>|last" >&2
  exit 2
fi
git fetch -q origin main
if [ "$target" = "last" ]; then
  sha=$(git log -1 --format=%H origin/main)
else
  sha=$(git log origin/main --format='%H %s' | awk -v pr="(#$target)" 'index($0, pr) {print $1; exit}')
fi
if [ -z "${sha:-}" ]; then
  echo "Could not find that PR on main." >&2
  exit 1
fi
title=$(git log -1 --format=%s "$sha")
branch="revert-${sha:0:7}"
wt="/tmp/rollback-${sha:0:7}"
git worktree add -q -B "$branch" "$wt" origin/main
cd "$wt"
git revert --no-edit "$sha"
git commit --amend -q -m "Revert: $title" -m "Rolls back ${sha:0:7}. Paper only." -m "Co-authored-by: Perplexity <noreply@perplexity.ai>"
git push -q -f origin "$branch"
gh pr create --head "$branch" --base main --title "Revert: $title" \
  --body "Rolls back ${sha:0:7} (${title}). Opened by paper-bots/tools/rollback.sh. Review before merging."
echo "Opened a revert PR for: $title"
