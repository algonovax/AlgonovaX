#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: missing .git"; exit 1; }

mkdir -p logs var data

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "FAIL: missing venv python: $PY"; exit 1; }

command -v flock >/dev/null 2>&1 || { echo "FAIL: missing flock"; exit 1; }

PIDFILE="var/engine_runner.pid"
LOCK="var/engine_runner.lock"
LOGFILE="var/engine_runner.log"

# runner collision check
if pgrep -af 'scripts/engine_runner\.py' >/dev/null 2>&1; then
  echo "FAIL: engine_runner process already exists:"
  pgrep -af 'scripts/engine_runner\.py' || true
  exit 1
fi

# pidfile hygiene
if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "FAIL: pidfile points to running pid=$pid"
    exit 1
  fi
fi

# kill switch path sanity
KS="${KILL_SWITCH_PATH:-$ROOT/data/KILL_SWITCH}"
echo "KILL_SWITCH_PATH=$KS"
touch "$KS" 2>/dev/null && rm -f "$KS" 2>/dev/null || true

# latest logs
latest="$(ls -1t logs/engine.run.*.log 2>/dev/null | head -n 1 || true)"
echo "LATEST_STDOUT=${latest:-}"
echo "LATEST_STDERR=${latest:+$latest.err}"

echo "OK: doctor passed"
