#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT"

# --- paper sim env (persist across nohup) ---
export PAPER_DEFAULT_PRICE="${PAPER_DEFAULT_PRICE:-50000}"
export PAPER_PRICE_STEP="${PAPER_PRICE_STEP:-2}"
export PAPER_FEE_QUOTE="${PAPER_FEE_QUOTE:-0}"
export PAPER_FEE_RATE="${PAPER_FEE_RATE:-0.001}"


mkdir -p logs data

LOG="logs/engine.run.$(date +%Y%m%d_%H%M%S).log"
PIDFILE="data/engine.pid"

# keep last 20 logs
ls -1t logs/engine.run.*.log 2>/dev/null | tail -n +21 | xargs -r rm -f

. .venv/bin/activate

# start python in background, capture PID, then wait forever on it
python -u scripts/engine_runner.py >>"$LOG" 2>&1 &
PY_PID="$!"
echo "$PY_PID" > "$PIDFILE"
wait "$PY_PID"
