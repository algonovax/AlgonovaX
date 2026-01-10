#!/usr/bin/env bash
set -euo pipefail
cd "${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"

dump () {
  local f="$1"
  echo
  echo "===== $f ====="
  if [ -f "$f" ]; then
    sed -n '1,260p' "$f"
  else
    echo "(missing)"
  fi
}

dump "algonovax/app.py"
dump "algonovax/config.py"
dump "algonovax/health.py"
dump "algonovax/risk.py"
dump "algonovax/engine.py"

dump "runner.py"
dump "exchanges/paper.py"
dump "strategies/ema_rsi.py"
dump "utils/logger.py"
