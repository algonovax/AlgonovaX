#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

PIDFILE="var/engine_runner.pid"
LOGFILE="var/engine_runner.logpath"

if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
else
  pid=""
fi

if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
  echo "RUNNING pid=$pid"
else
  echo "NOT RUNNING"
  pgrep -af 'scripts/engine_runner\.py' || true
fi

if [[ -f "$LOGFILE" ]]; then
  log="$(cat "$LOGFILE" 2>/dev/null || true)"
  if [[ -n "${log:-}" && -f "$log" ]]; then
    echo "--- tail $log ---"
    tail -n 40 "$log" || true
  fi
fi
