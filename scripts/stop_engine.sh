#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: must run inside repo (missing .git)"; exit 1; }

PIDFILE="var/engine_runner.pid"
LOCK="var/engine_runner.lock"

pids="$(pgrep -f 'scripts/engine_runner\.py' || true)"

# prefer pidfile if valid
if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    pids="$pid"
  fi
fi

if [[ -z "${pids:-}" ]]; then
  echo "OK: no runners"
  rm -f "$PIDFILE" "$LOCK" 2>/dev/null || true
  exit 0
fi

echo "Stopping (TERM): $pids"
kill $pids 2>/dev/null || true

# wait up to ~3s
for _ in 1 2 3; do
  sleep 1
  pids2="$(pgrep -f 'scripts/engine_runner\.py' || true)"
  [[ -z "${pids2:-}" ]] && break
done

pids2="$(pgrep -f 'scripts/engine_runner\.py' || true)"
if [[ -n "${pids2:-}" ]]; then
  echo "Force stopping (KILL): $pids2"
  kill -9 $pids2 2>/dev/null || true
fi

rm -f "$PIDFILE" "$LOCK" 2>/dev/null || true
pgrep -af 'scripts/engine_runner\.py' || echo "OK: stopped"
