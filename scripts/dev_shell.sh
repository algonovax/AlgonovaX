#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"
. "$ROOT/.venv/bin/activate"
./scripts/setup/install_git_hooks.sh >/dev/null 2>&1 || true
exec bash -i
