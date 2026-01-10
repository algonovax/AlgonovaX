#!/usr/bin/env bash
set -euo pipefail

BASE="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
JOB="$BASE/data/backtest_job.json"
OUTDIR="$BASE/logs/backtests"
OUT="$OUTDIR/backtest.out"

mkdir -p "$OUTDIR"

if [[ ! -f "$JOB" ]]; then
  echo "missing job: $JOB" | tee "$OUT"
  exit 1
fi

# shellcheck disable=SC2002
cat "$JOB" > "$OUTDIR/last_job.json"

STRATEGY="$(python3 - <<'PY'
import json, os
p=os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")
j=json.load(open(p))
print(j.get("strategy","ema_rsi"))
PY
)"

SYMBOL="$(python3 - <<'PY'
import json, os
p=os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")
j=json.load(open(p))
print(j.get("symbol","BTC/USD"))
PY
)"

TIMEFRAME="$(python3 - <<'PY'
import json, os
p=os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")
j=json.load(open(p))
print(j.get("timeframe","1m"))
PY
)"

START="$(python3 - <<'PY'
import json, os
p=os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")
j=json.load(open(p))
print(j.get("start",""))
PY
)"

END="$(python3 - <<'PY'
import json, os
p=os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")
j=json.load(open(p))
print(j.get("end",""))
PY
)"

echo "=== AlgoNovaX Backtest ===" | tee "$OUT"
echo "ts=$(date -Is)" | tee -a "$OUT"
echo "strategy=$STRATEGY symbol=$SYMBOL timeframe=$TIMEFRAME start=$START end=$END" | tee -a "$OUT"
echo | tee -a "$OUT"

# Prefer your engine backtest if exists; fallback to "sim loop" placeholder.
if [[ -f "$BASE/scripts/backtest_engine.py" ]]; then
  "$BASE/.venv/bin/python" -u "$BASE/scripts/backtest_engine.py" \
    --strategy "$STRATEGY" --symbol "$SYMBOL" --timeframe "$TIMEFRAME" \
    ${START:+--start "$START"} ${END:+--end "$END"} 2>&1 | tee -a "$OUT"
else
  echo "WARNING: scripts/backtest_engine.py not found. Using placeholder run." | tee -a "$OUT"
  "$BASE/.venv/bin/python" - <<'PY' 2>&1 | tee -a "$OUT"
import time, json, os, random
job=json.load(open(os.path.expanduser("${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/backtest_job.json")))
equity=10000.0
print("job:", job)
for i in range(30):
    equity += random.uniform(-25, 35)
    print(f"step={i:02d} equity={equity:.2f}")
    time.sleep(0.05)
print("done")
PY
fi
