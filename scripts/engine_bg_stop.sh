#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

PIDFILE="data/engine.pid"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$PID" 2>/dev/null || true
  fi
fi

# fallback cleanup
pkill -TERM -f "scripts/engine_runner.py" 2>/dev/null || true
sleep 0.5
pkill -KILL -f "scripts/engine_runner.py" 2>/dev/null || true

rm -f "$PIDFILE" 2>/dev/null || true
echo "STOPPED"
