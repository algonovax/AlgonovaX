#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

PIDFILE="data/engine.pid"

# if already running, refuse
if pgrep -af "scripts/engine_runner.py" >/dev/null 2>&1; then
  echo "ALREADY_RUNNING:"
  pgrep -af "scripts/engine_runner.py" || true
  exit 0
fi

nohup ./scripts/run_termux_engine.sh >/dev/null 2>&1 &
sleep 0.4

echo "ENGINE_PIDFILE=$(cat "$PIDFILE" 2>/dev/null || echo MISSING)"
echo "LATEST_LOG=$(ls -1t logs/engine.run.*.log 2>/dev/null | head -n 1 || true)"
