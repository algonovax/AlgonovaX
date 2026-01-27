#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p logs var data

# clean stale pid file
if [ -f var/engine.pid ]; then
  old="$(cat var/engine.pid 2>/dev/null || true)"
  if [ -n "${old:-}" ] && ! kill -0 "$old" 2>/dev/null; then
    rm -f var/engine.pid
  fi
fi

if pgrep -f 'python -u -m algonovax engine' >/dev/null 2>&1; then
  echo "engine already running" >&2
  exit 1
fi

rm -f data/KILL_SWITCH
log="logs/engine.run.log"
: > "$log"

( PYTHONUNBUFFERED=1 python -u -m algonovax engine >> "$log" 2>&1 ) &
pid=$!

# ensure we don't persist a dead pid
sleep 0.5
if ! kill -0 "$pid" 2>/dev/null; then
  echo "engine failed to start; see $log" >&2
  tail -n 120 "$log" >&2 || true
  exit 1
fi

echo "$pid" > var/engine.pid
echo "pid=$pid"
