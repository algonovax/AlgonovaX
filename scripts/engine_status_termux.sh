#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
LOG="${ALGONOVAX_ENGINE_LOG:-$BASE/logs/engine.log}"
PIDFILE="${ALGONOVAX_ENGINE_PIDFILE:-$BASE/var/engine.pid}"

cd "$BASE"

_tail_log() {
  echo "--- tail logs/engine.log ---"
  tail -n 120 "$LOG" 2>/dev/null || true
}

if [ ! -f "$PIDFILE" ]; then
  echo "NOT RUNNING"
  _tail_log
  exit 0
fi

PID="$(cat "$PIDFILE" 2>/dev/null || true)"

if [ -z "${PID:-}" ] || ! printf '%s' "$PID" | grep -qE '^[0-9]+$'; then
  rm -f "$PIDFILE" 2>/dev/null || true
  echo "NOT RUNNING (stale pidfile removed)"
  _tail_log
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  echo "RUNNING pid=$PID"
  exit 0
fi

rm -f "$PIDFILE" 2>/dev/null || true
echo "NOT RUNNING (stale pidfile removed)"
_tail_log
exit 0
