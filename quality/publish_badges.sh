#!/usr/bin/env bash
# Force-push a directory of badge SVGs as the single commit of the `badges` branch.
# Usage: quality/publish_badges.sh <dir>   (needs GH_TOKEN and GITHUB_REPOSITORY)
set -euo pipefail
cd "$1"
git init -q -b badges
git add -A
git -c user.name="github-actions[bot]" \
  -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit -q -m "PactFlow badges for ${GITHUB_SHA:-local}"
git push -q -f "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" badges
echo "published $(ls | wc -l) badges to the badges branch"
