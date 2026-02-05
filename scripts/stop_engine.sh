#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: must run inside repo (missing .git)"; exit 1; }
cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

pids="$(pgrep -f 'scripts/engine_runner\.py' || true)"
if [ -z "${pids:-}" ]; then
  echo "OK: no runners"
  exit 0
fi

echo "Stopping (TERM): $pids"
kill $pids 2>/dev/null || true

# grace period up to 12s (engine heartbeat is ~10s in your log)
for i in $(seq 1 12); do
  sleep 1
  if ! pgrep -f 'scripts/engine_runner\.py' >/dev/null 2>&1; then
    echo "OK: stopped"
    exit 0
  fi
done

pids2="$(pgrep -f 'scripts/engine_runner\.py' || true)"
if [ -n "${pids2:-}" ]; then
  echo "Force stopping (KILL): $pids2"
  kill -9 $pids2 2>/dev/null || true
  sleep 1
fi

pgrep -af 'scripts/engine_runner\.py' || echo "OK: stopped"
