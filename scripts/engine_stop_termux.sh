#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

pid="$(cat var/engine.pid 2>/dev/null || true)"
if [ -z "${pid:-}" ]; then
  echo "OK: not running (no pid file)"
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  sleep 0.2
fi

rm -f var/engine.pid
echo "OK: stopped"
