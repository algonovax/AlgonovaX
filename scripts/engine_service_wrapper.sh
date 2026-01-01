#!/usr/bin/env bash
set -euo pipefail

LOCK="$HOME/projects/AlgonovaX/data/engine.lock"
PY="$HOME/projects/AlgonovaX/.venv/bin/python"
RUNNER="$HOME/projects/AlgonovaX/scripts/engine_runner.py"

# If lock is held, exit 0 (service remains inactive, no restart loop)
if ! /usr/bin/flock -n "$LOCK" -c "exec '$PY' -u '$RUNNER'"; then
  echo "[engine] lock held: $LOCK (another instance running?)"
  exit 0
fi
