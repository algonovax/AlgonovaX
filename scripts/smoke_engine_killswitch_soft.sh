#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

./scripts/engine_stop_termux.sh || true
rm -f var/engine.pid data/KILL_SWITCH data/KILL_SWITCH_SOFT data/KILL_SWITCH_HARD 2>/dev/null || true

./scripts/engine_start_termux.sh
sleep 1

# confirm running
if ! ./scripts/engine_status_termux.sh | rg -q "RUNNING"; then
  echo "FAIL: engine not running after start"
  ./scripts/engine_status_termux.sh || true
  exit 1
fi

# trip SOFT
: > data/KILL_SWITCH_SOFT
sleep 1

if ./scripts/engine_status_termux.sh | rg -q "RUNNING"; then
  echo "FAIL: engine still running after SOFT killswitch"
  ./scripts/engine_status_termux.sh || true
  exit 1
fi

echo "PASS: soft killswitch stops engine"
