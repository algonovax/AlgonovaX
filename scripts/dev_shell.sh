#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"
. "$ROOT/.venv/bin/activate"
exec bash -i
