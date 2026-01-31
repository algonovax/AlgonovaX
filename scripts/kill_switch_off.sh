#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
rm -f "$ROOT/data/KILL_SWITCH" 2>/dev/null || true
echo "OK: kill switch removed"
