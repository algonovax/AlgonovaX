#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
PIDFILE="${ALGONOVAX_ENGINE_PIDFILE:-$BASE/var/engine.pid}"
LOG="${ALGONOVAX_ENGINE_LOG:-$BASE/logs/engine.log}"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    echo "RUNNING pid=$PID"
    exit 0
  fi
fi

echo "NOT RUNNING"
echo "--- tail logs/engine.log ---"
tail -n 40 "$LOG" 2>/dev/null || true
exit 1
