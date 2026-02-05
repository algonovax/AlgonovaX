#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
PIDFILE="${ALGONOVAX_ENGINE_PIDFILE:-$BASE/var/engine.pid}"

if [ ! -f "$PIDFILE" ]; then
  echo "OK: not running (no pidfile)"
  exit 0
fi

PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ -z "${PID:-}" ]; then
  rm -f "$PIDFILE"
  echo "OK: not running (empty pidfile)"
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
  fi
fi

rm -f "$PIDFILE"
echo "OK: stopped"
