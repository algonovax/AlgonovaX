#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"
git rev-parse --show-toplevel >/dev/null

mkdir -p .git/hooks
cp -f "$ROOT/scripts/hooks/pre-commit" "$ROOT/.git/hooks/pre-commit"
chmod +x "$ROOT/.git/hooks/pre-commit"
echo "OK: installed git hooks"
