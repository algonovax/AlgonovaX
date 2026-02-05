#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"
[ -d .git ] || { echo "FAIL: must run inside repo (missing .git)"; exit 1; }

PIDFILE="var/engine_runner.pid"
LOGFILE="var/engine_runner.log"

pid=""
[[ -f "$PIDFILE" ]] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"

running=0
if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
  running=1
else
  # fallback: discover by process name
  pid="$(pgrep -f 'scripts/engine_runner\.py' | head -n 1 || true)"
  [[ -n "${pid:-}" ]] && running=1 || running=0
fi

if [[ "$running" -eq 1 ]]; then
  echo "RUNNING pid=$pid"
else
  echo "NOT RUNNING"
fi

log=""
if [[ -f "$LOGFILE" ]]; then
  log="$(cat "$LOGFILE" 2>/dev/null || true)"
fi
if [[ -z "${log:-}" ]]; then
  log="$(ls -1t logs/engine.run.*.log 2>/dev/null | head -n 1 || true)"
fi

echo "--- tail ${log:-"(no log found)"} ---"
if [[ -n "${log:-}" && -f "$log" ]]; then
  tail -n 30 "$log" || true
fi

if [[ -n "${log:-}" && -f "$log.err" ]]; then
  echo "--- tail $log.err ---"
  tail -n 30 "$log.err" || true
fi
