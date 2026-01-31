#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

export EXCHANGE="paper"
export LIVE_TRADING_ENABLED="0"
export PAPER_TRADING_ENABLED="1"
export KILL_SWITCH_PATH="./data/KILL_SWITCH"

rm -f "$ROOT/data/KILL_SWITCH" 2>/dev/null || true
echo "OK: armed PAPER (kill switch OFF)"
