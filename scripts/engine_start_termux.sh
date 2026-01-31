#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs var data

if [ -f data/KILL_SWITCH ]; then
  echo "FAIL: data/KILL_SWITCH exists; remove it to start."
  exit 2
fi

if [ -f var/engine.pid ]; then
  pid="$(cat var/engine.pid 2>/dev/null || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    echo "OK: already running pid=$pid"
    exit 0
  fi
  rm -f var/engine.pid
fi

PYTHONUNBUFFERED=1 .venv/bin/python -u -m algonovax engine >> logs/engine.log 2>&1 &
echo $! > var/engine.pid
disown || true
echo "OK: started pid=$(cat var/engine.pid)"
