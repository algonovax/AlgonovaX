#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
mkdir -p "$ROOT/data"
: > "$ROOT/data/KILL_SWITCH"
echo "OK: kill switch ON ($ROOT/data/KILL_SWITCH)"
