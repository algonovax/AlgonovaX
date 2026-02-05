#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: must run inside repo (missing .git)"; exit 1; }
cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

mkdir -p logs var

PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "FAIL: missing $PY (create venv first)" >&2
  exit 1
fi

LOG="logs/engine.run.$(date +%Y%m%d_%H%M%S).log"
LOCK="var/engine_runner.lock"
PIDFILE="var/engine_runner.pid"
LOGFILE="var/engine_runner.logpath"

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "FAIL: engine_runner already running (lock: $LOCK)" >&2
  pgrep -af 'scripts/engine_runner\.py' || true
  exit 1
fi

"$PY" -u scripts/engine_runner.py >"$LOG" 2>&1 &
PID=$!

echo "$PID" > "$PIDFILE"
echo "$LOG" > "$LOGFILE"

echo "PID=$PID LOG=$LOG"
