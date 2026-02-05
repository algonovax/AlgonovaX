#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$BASE" || { echo "FAIL: cannot cd to $BASE"; exit 1; }

PY="$BASE/.venv/bin/python"
RUNNER="$BASE/scripts/engine_runner.py"
PIDFILE="$BASE/var/engine.pid"
LOGDIR="${ALGONOVAX_LOG_DIR:-$BASE/logs}"
LOGFILE="$LOGDIR/engine.log"

OVR_ENV="$BASE/var/engine.override.env"

mkdir -p "$BASE/var" "$BASE/data" "$LOGDIR"

# Safety: refuse to start if any kill switch is present
if [ -e "$BASE/data/KILL_SWITCH" ] || [ -e "$BASE/data/KILL_SWITCH_SOFT" ] || [ -e "$BASE/data/KILL_SWITCH_HARD" ]; then
  echo "FAIL: killswitch present; remove data/KILL_SWITCH* before starting"
  ls -la "$BASE/data/KILL_SWITCH"* 2>/dev/null || true
  exit 2
fi

# Load GUI-applied env (Termux override file)
if [ -f "$OVR_ENV" ]; then
  # only export allowed keys; ignore anything else
  while IFS= read -r line || [ -n "${line:-}" ]; do
    line="${line%%$'\r'}"
    [ -z "${line}" ] && continue
    case "$line" in
      \#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    case "$key" in
      EXCHANGE|PAPER_TRADING_ENABLED|LIVE_TRADING_ENABLED|SYMBOL|TIMEFRAME|MAX_DAILY_LOSS_USD|MAX_OPEN_POSITIONS|KILL_SWITCH_PATH)
        # strip surrounding quotes if present
        case "$val" in
          \"*\") val="${val#\"}"; val="${val%\"}" ;;
          \'*\') val="${val#\'}"; val="${val%\'}" ;;
        esac
        export "$key=$val"
        ;;
      *) : ;;
    esac
  done < "$OVR_ENV"
fi

# Ensure defaults if not set
: "${KILL_SWITCH_PATH:=$BASE/data/KILL_SWITCH}"
export KILL_SWITCH_PATH

# Don't double-start
if [ -f "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${old:-}" ] && kill -0 "$old" 2>/dev/null; then
    echo "OK: already running pid=$old"
    exit 0
  fi
  rm -f "$PIDFILE" || true
fi

# Start
if [ ! -x "$PY" ]; then
  echo "FAIL: missing venv python at $PY"
  exit 1
fi
if [ ! -f "$RUNNER" ]; then
  echo "FAIL: missing runner at $RUNNER"
  exit 1
fi

# Launch detached
nohup "$PY" "$RUNNER" >>"$LOGFILE" 2>&1 &
pid="$!"
echo "$pid" > "$PIDFILE"
echo "OK: started pid=$pid"
