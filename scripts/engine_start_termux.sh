#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
LOG="${ALGONOVAX_ENGINE_LOG:-$BASE/logs/engine.log}"
PIDFILE="${ALGONOVAX_ENGINE_PIDFILE:-$BASE/var/engine.pid}"

PY="$BASE/.venv/bin/python"
[ -x "$PY" ] || PY=python3

mkdir -p "$(dirname "$LOG")" "$(dirname "$PIDFILE")"
cd "$BASE"

# refuse to start if killswitch is on
if [ -e "$BASE/data/KILL_SWITCH" ] || [ -e "$BASE/data/KILL_SWITCH_SOFT" ] || [ -e "$BASE/data/KILL_SWITCH_HARD" ]; then
  echo "FAIL: killswitch present; remove data/KILL_SWITCH* before starting"
  ls -la "$BASE/data/KILL_SWITCH"* 2>/dev/null || true
  exit 2
fi


if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    echo "OK: already running pid=$PID"
    exit 0
  fi
fi

nohup "$PY" "$BASE/scripts/engine_runner.py" >>"$LOG" 2>&1 &
PID="$!"
echo "$PID" >"$PIDFILE"
echo "OK: started pid=$PID"
