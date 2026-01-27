#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HOME}/AlgonovaX"
cd "$ROOT"
. "$ROOT/.venv/bin/activate"

mkdir -p "$ROOT/logs" "$ROOT/data"

SESSION="algonovax-engine"
ts="$(date +%Y%m%d_%H%M%S)"
LOG="$ROOT/logs/engine.tmux.$ts.log"

export PYTHONUNBUFFERED=1
export ALGONOVAX_STRATEGY="${ALGONOVAX_STRATEGY:-ema_rsi_atr}"
export ALGONOVAX_PAIR="${ALGONOVAX_PAIR:-BTC/USD}"
export ALGONOVAX_MODE="${ALGONOVAX_MODE:-paper}"

rm -f "$ROOT/data/KILL_SWITCH" 2>/dev/null || true

if ! command -v tmux >/dev/null 2>&1; then
  echo "FAIL: tmux not installed. Run: pkg install -y tmux" >&2
  exit 1
fi

cmd="cd '$ROOT' && exec '$ROOT/.venv/bin/python' -u -X dev -m algonovax engine >> '$LOG' 2>&1"

tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION" || true
tmux new-session -d -s "$SESSION" /data/data/com.termux/files/usr/bin/bash -lc "$cmd"

echo "OK: started tmux session=$SESSION"
echo "log=$LOG"
