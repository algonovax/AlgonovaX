#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="${HOME}/AlgonovaX"
SESSION="algonovax-engine"

touch "$ROOT/data/KILL_SWITCH" 2>/dev/null || true
sleep 1

if command -v tmux >/dev/null 2>&1; then
  tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION" || true
fi

echo "OK: stop requested"
