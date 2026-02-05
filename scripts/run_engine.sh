#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: must run inside repo (missing .git)"; exit 1; }

mkdir -p logs var

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "FAIL: missing $PY (create venv first)"; exit 1; }

LOCK="var/engine_runner.lock"
PIDFILE="var/engine_runner.pid"
LOGFILE="var/engine_runner.log"

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "FAIL: engine_runner already running (lock: $LOCK)" >&2
  if [[ -f "$PIDFILE" ]]; then
    echo "PIDFILE=$(cat "$PIDFILE" 2>/dev/null || true)" >&2
  fi
  pgrep -af 'scripts/engine_runner\.py' || true
  exit 1
fi

LOG="logs/engine.run.$(date +%Y%m%d_%H%M%S).log"
: >"$LOG"

# record current run targets
echo "$LOG" >"$LOGFILE"
"$PY" -u scripts/engine_runner.py >"$LOG" 2>"$LOG.err" &
PID="$!"
echo "$PID" >"$PIDFILE"

echo "PID=$PID LOG=$LOG"
