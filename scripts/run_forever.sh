#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/projects/AlgonovaX"
source .venv/bin/activate

LOG="logs/mvp_$(date +%Y%m%d_%H%M%S).log"
echo "LOG=$LOG" | tee -a "$LOG"

while true; do
  echo "=== START $(date -Is) ===" | tee -a "$LOG"
  python -u scripts/run_mvp.py >>"$LOG" 2>&1 || echo "EXIT_CODE=$? $(date -Is)" | tee -a "$LOG"
  sleep 2
done
