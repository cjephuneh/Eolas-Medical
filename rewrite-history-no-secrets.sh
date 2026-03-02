#!/bin/bash
# Rewrite git history so no commit contains .env or secrets in .env.example.
# Run from repo root: /Users/mac/Documents/loganUSA/Eolas Medical
# After running, push with: git push -u remote main --force

set -e
cd "$(dirname "$0")"

echo "Creating new branch with no history (orphan)..."
git checkout --orphan temp-main

echo "Staging all files ( .env is in .gitignore so it will not be added )..."
git add -A

echo "Checking that .env is NOT staged..."
if git diff --cached --name-only | grep -q '\.env$'; then
  echo "ERROR: .env is staged! Remove it: git reset HEAD .env speed-to-response/.env 2>/dev/null; exit 1"
  git reset HEAD .env speed-to-response/.env 2>/dev/null || true
  git status
  exit 1
fi

echo "Committing clean state..."
git commit -m "Speed-to-Response: Eolas Medical (no secrets in repo)"

echo "Replacing main with clean history..."
git branch -D main 2>/dev/null || true
git branch -m main

echo "Done. Push with: git push -u remote main --force"
