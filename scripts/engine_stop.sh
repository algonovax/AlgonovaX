#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p var data

touch data/KILL_SWITCH

pid_file="var/engine.pid"
if [ -f "$pid_file" ]; then
  pid="$(cat "$pid_file" || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    # give it a moment to exit on its own
    for _ in 1 2 3 4 5; do
      sleep 0.5
      kill -0 "$pid" 2>/dev/null || break
    done
    kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
fi

# kill any stragglers
pids="$(pgrep -f 'python -u -m algonovax engine' || true)"
[ -n "${pids:-}" ] && kill $pids 2>/dev/null || true
