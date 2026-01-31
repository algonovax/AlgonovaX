#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

: "${KRAKEN_API_KEY:?missing KRAKEN_API_KEY}"
: "${KRAKEN_API_SECRET:?missing KRAKEN_API_SECRET}"

export EXCHANGE="kraken"
export LIVE_TRADING_ENABLED="1"
export PAPER_TRADING_ENABLED="0"
export REQUIRE_KILL_SWITCH_OFF_FOR_LIVE="1"
export KILL_SWITCH_PATH="./data/KILL_SWITCH"

rm -f "$ROOT/data/KILL_SWITCH" 2>/dev/null || true
echo "OK: armed LIVE KRAKEN (kill switch OFF + guards ON)"
