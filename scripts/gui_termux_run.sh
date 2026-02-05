#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
HOST="${ALGONOVAX_GUI_HOST:-127.0.0.1}"
PORT="${ALGONOVAX_GUI_PORT:-8790}"
LOG="${ALGONOVAX_GUI_LOG:-$BASE/logs/gui.log}"

PY="$BASE/.venv/bin/python"
[ -x "$PY" ] || PY=python3

mkdir -p "$(dirname "$LOG")"

# avoid double-start
if command -v ss >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | grep -qE "LISTEN.*:${PORT}\b"; then
    echo "OK: already listening on :$PORT"
    exit 0
  fi
fi

# run in foreground (use tmux/nohup if you want background)
exec "$PY" -m algonovax gui --host "$HOST" --port "$PORT" 2>&1 | tee -a "$LOG"
