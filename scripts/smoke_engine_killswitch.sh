#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

rm -f data/KILL_SWITCH
mkdir -p logs
ts="$(date +%Y%m%d_%H%M%S)"
log="logs/smoke.engine.killswitch.$ts.log"

set +e
PYTHONUNBUFFERED=1 python -u -m algonovax engine >>"$log" 2>&1 &
pid=$!
sleep 2
touch data/KILL_SWITCH
wait "$pid"
rc=$?
set -e

tail -n 30 "$log"
if [ "$rc" -eq 2 ]; then echo "PASS (killswitch exit=2)"; else echo "FAIL (exit=$rc)"; fi
tail -n 30 "$log"
test "$rc" -eq 2
