#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

mkdir -p .git/hooks

src="$ROOT/scripts/hooks/pre-commit"
dst="$ROOT/.git/hooks/pre-commit"

if [ ! -f "$src" ]; then
  echo "FAIL: missing $src"
  exit 1
fi

# copy to avoid symlink issues on some environments
cp -f "$src" "$dst"
chmod +x "$dst"

echo "OK: installed git hooks"
