#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/projects/AlgonovaX"

echo "== git =="
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not a git repo"; exit 1; }
git status -sb

BR="chore/finish-professionalize"
git checkout -b "$BR" 2>/dev/null || git checkout "$BR"

echo
echo "== repo root =="
pwd
echo
echo "== top files =="
ls -la
