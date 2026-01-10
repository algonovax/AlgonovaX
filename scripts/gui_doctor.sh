#!/usr/bin/env bash
set -euo pipefail

cd ${ALGONOVAX_ROOT:-$HOME/AlgonovaX}
source .venv/bin/activate

SERVICE="algonovax-gui.service"

ENV="$(systemctl --user show -p Environment --value "$SERVICE" || true)"
HOST="$(printf '%s\n' "$ENV" | tr ' ' '\n' | sed -n 's/^ALGONOVAX_GUI_HOST=//p' | tail -n1)"
PORT="$(printf '%s\n' "$ENV" | tr ' ' '\n' | sed -n 's/^ALGONOVAX_GUI_PORT=//p' | tail -n1)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8790}"

echo "== compile =="
python -m py_compile algonovax/gui/app.py

echo "== unit =="
systemctl --user is-enabled "$SERVICE" || true
systemctl --user is-active "$SERVICE" || true

PID="$(systemctl --user show -p MainPID --value "$SERVICE" || true)"
if [ -z "${PID:-}" ] || [ "$PID" = "0" ]; then
  echo "NO_MAINPID" >&2
  exit 2
fi

echo "== listen =="
# Only accept listeners owned by this service PID
LOCAL="$(ss -ltnp | awk -v p=":${PORT}" -v pid="pid=${PID}," '
  $4 ~ p && index($0, pid) { print $4; exit }
')"
if [ -z "${LOCAL:-}" ]; then
  echo "NO_LISTENER_FOR_PID=$PID on :$PORT" >&2
  ss -ltnp | grep ":${PORT}" || true
  exit 3
fi
echo "$LOCAL"

# Expected bind check
if [ "$HOST" = "127.0.0.1" ] || [ "$HOST" = "localhost" ]; then
  case "$LOCAL" in
    127.0.0.1:"$PORT"|[::1]:"$PORT"|::1:"$PORT") : ;;
    *) echo "MISMATCH: expected loopback on :$PORT, got $LOCAL" >&2; exit 4 ;;
  esac

  # Forbid wildcard binds for THIS PID when loopback is expected
  if ss -ltnp | awk -v p=":${PORT}" -v pid="pid=${PID}," '
      ($4 == "0.0.0.0"p || $4 == "[::]"p || $4 == "::"p) && index($0, pid) { found=1 }
      END { exit found?0:1 }
    '; then
    echo "MISMATCH: wildcard bind detected for PID=$PID on :$PORT" >&2
    ss -ltnp | grep ":${PORT}" || true
    exit 6
  fi
else
  if [ "$LOCAL" != "${HOST}:${PORT}" ]; then
    echo "MISMATCH: expected ${HOST}:${PORT}, got $LOCAL" >&2
    exit 4
  fi
fi

echo "== http =="
curl -fsS --max-time 2 "http://${HOST}:${PORT}/" >/dev/null && echo OK || { echo FAIL; exit 5; }

echo "GUI_DOCTOR_DONE"
