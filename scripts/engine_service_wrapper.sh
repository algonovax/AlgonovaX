#!/usr/bin/env bash
set -euo pipefail

LOCK="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/engine.lock"
PY="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/.venv/bin/python"
RUNNER="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/scripts/engine_runner.py"

# If lock is held, exit 0 (service remains inactive, no restart loop)
if ! /usr/bin/flock -n "$LOCK" -c "exec '$PY' -u '$RUNNER'"; then
  echo "[engine] lock held: $LOCK (another instance running?)"
  exit 0
fi
