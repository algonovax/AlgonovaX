#!/usr/bin/env bash
# Never kills your terminal. Logs everything.
set -u

REPO="$HOME/projects/AlgonovaX"
LOGDIR="$REPO/logs"
mkdir -p "$LOGDIR"

LOG="$LOGDIR/safe_run_$(date +%Y%m%d_%H%M%S).log"

{
  echo "===== safe_run start $(date) ====="
  echo "pwd=$(pwd)"
  echo "repo=$REPO"
  echo

  cd "$REPO" || { echo "[FATAL] repo missing"; exit 1; }

  echo "== systemd status =="
  systemctl --user status algonovax.service --no-pager -l || true
  echo

  echo "== port 8001 listener =="
  sudo lsof -iTCP:8001 -sTCP:LISTEN || true
  echo

  echo "== health =="
  curl -sS http://127.0.0.1:8001/health || true
  echo
  echo

  echo "== logs (project) =="
  tail -n 120 "$REPO/logs/api.log" 2>/dev/null || echo "(no $REPO/logs/api.log yet)"
  echo
  echo "===== safe_run end $(date) ====="
} 2>&1 | tee -a "$LOG"

echo "[OK] wrote $LOG"
