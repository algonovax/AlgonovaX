#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

pid="$(cat var/engine.pid 2>/dev/null || true)"
if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
  echo "RUNNING pid=$pid"
else
  [ -f var/engine.pid ] && rm -f var/engine.pid || true
  echo "NOT RUNNING"
fi

echo "--- tail logs/engine.log ---"
tail -n 60 logs/engine.log 2>/dev/null || true
