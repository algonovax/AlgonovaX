#!/usr/bin/env bash
set -euo pipefail

SERVICE="algonovax-gui.service"

ENV="$(systemctl --user show -p Environment --value "$SERVICE" || true)"
HOST="$(printf '%s\n' "$ENV" | tr ' ' '\n' | sed -n 's/^ALGONOVAX_GUI_HOST=//p' | tail -n1)"
PORT="$(printf '%s\n' "$ENV" | tr ' ' '\n' | sed -n 's/^ALGONOVAX_GUI_PORT=//p' | tail -n1)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8790}"

PID="$(systemctl --user show -p MainPID --value "$SERVICE" || true)"
if [ -z "${PID:-}" ] || [ "$PID" = "0" ]; then
  echo "GUI healthcheck failed: no MainPID" >&2
  exit 7
fi

url="http://${HOST}:${PORT}/"

for i in {1..40}; do
  # require the listener for this PID on this port
  if ss -ltnp | awk -v p=":${PORT}" -v pid="pid=${PID}," '
      $4 ~ p && index($0, pid) { found=1 }
      END { exit found?0:1 }
    ' >/dev/null 2>&1; then
    if curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
      exit 0
    fi
  fi
  sleep 0.25
done

echo "GUI healthcheck failed: $url not reachable for PID=$PID" >&2
exit 7
