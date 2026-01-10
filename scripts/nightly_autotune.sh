#!/usr/bin/env bash
set -euo pipefail

ROOT="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$ROOT" || { echo "ERROR: missing $ROOT"; exit 1; }

if [ -f ".venv/bin/activate" ]; then
  source ".venv/bin/activate"
fi

STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
LOG="logs/autotune_${STAMP}.log"

mkdir -p logs data/registry data/candles

: "${DAYS:=45}"
: "${TRAIN_ITERS:=60}"
: "${EVAL_TOP:=8}"

: "${FEE_RATE:=0.001}"
: "${SLIPPAGE_RATE:=0.0003}"
: "${STAKE_QUOTE:=100}"

# Train/test windows (must match baseline.yaml)
: "${TRAIN_DAYS:=30}"
: "${TEST_DAYS:=15}"

# Dynamic MIN_CANDLES for windows (5m => 288 candles/day). Use 90% to tolerate API gaps.
MIN_CANDLES_TRAIN="$(( (TRAIN_DAYS * 288 * 90) / 100 ))"
MIN_CANDLES_TEST="$(( (TEST_DAYS  * 288 * 90) / 100 ))"

echo "=== AlgoNovaX Nightly Autotune ===" | tee -a "$LOG"
echo "UTC: $STAMP" | tee -a "$LOG"
echo "DAYS=$DAYS TRAIN_ITERS=$TRAIN_ITERS EVAL_TOP=$EVAL_TOP" | tee -a "$LOG"
echo "TRAIN_DAYS=$TRAIN_DAYS TEST_DAYS=$TEST_DAYS" | tee -a "$LOG"
echo "MIN_CANDLES_TRAIN=$MIN_CANDLES_TRAIN MIN_CANDLES_TEST=$MIN_CANDLES_TEST" | tee -a "$LOG"
echo "COSTS fee=$FEE_RATE slip=$SLIPPAGE_RATE stake=$STAKE_QUOTE" | tee -a "$LOG"
echo | tee -a "$LOG"

echo "[1/4] Fetch candles from Coinbase..." | tee -a "$LOG"
python - <<'PY' | tee -a "$LOG"
import time, json, datetime, requests
from pathlib import Path
import os

ROOT = Path.cwd()
OUT_DIR = ROOT / "data" / "candles"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT = "BTC-USD"
GRAN = 300  # 5m
DAYS = int(os.environ.get("DAYS","45"))

now = int(time.time())
start = now - DAYS*24*60*60

def iso(ts):
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")

sess = requests.Session()
base = "https://api.exchange.coinbase.com"

rows = []
seen = set()
chunk = 24*60*60

t = start
while t < now:
    t2 = min(t + chunk, now)
    r = sess.get(
        f"{base}/products/{PRODUCT}/candles",
        params={"granularity": GRAN, "start": iso(t), "end": iso(t2)},
        timeout=30,
    )
    r.raise_for_status()
    for row in r.json():
        ts = int(row[0])
        if ts in seen:
            continue
        seen.add(ts)
        low, high, open_, close, vol = map(float, row[1:])
        rows.append([ts*1000, open_, high, low, close, vol])
    time.sleep(0.25)
    t += chunk

rows.sort(key=lambda x: x[0])
start_ms = rows[0][0]
end_ms = rows[-1][0]
out = OUT_DIR / f"kraken_BTC_USD_5m_{start_ms}_{end_ms}.json"
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("WROTE", out)
print("candles=", len(rows))
PY

CANDLE_FILE="$(ls -1t data/candles/kraken_BTC_USD_5m_*.json | head -n 1)"
echo "CANDLE_FILE=$CANDLE_FILE" | tee -a "$LOG"
echo | tee -a "$LOG"

echo "[2/4] Train candidates..." | tee -a "$LOG"
CANDLE_FILE="$CANDLE_FILE" \
MIN_CANDLES="$MIN_CANDLES_TRAIN" \
FEE_RATE="$FEE_RATE" SLIPPAGE_RATE="$SLIPPAGE_RATE" STAKE_QUOTE="$STAKE_QUOTE" \
TRAIN_DAYS="$TRAIN_DAYS" TEST_DAYS="$TEST_DAYS" \
python -u scripts/train_candidate.py --iterations "$TRAIN_ITERS" 2>&1 | tee -a "$LOG" || true

echo | tee -a "$LOG"

echo "[3/4] Evaluate candidates..." | tee -a "$LOG"
CANDLE_FILE="$CANDLE_FILE" \
MIN_CANDLES="$MIN_CANDLES_TEST" \
FEE_RATE="$FEE_RATE" SLIPPAGE_RATE="$SLIPPAGE_RATE" STAKE_QUOTE="$STAKE_QUOTE" \
TRAIN_DAYS="$TRAIN_DAYS" TEST_DAYS="$TEST_DAYS" \
python -u scripts/evaluate_candidate.py --top "$EVAL_TOP" 2>&1 | tee -a "$LOG" || true

echo | tee -a "$LOG"

echo "[4/4] Promote if pass..." | tee -a "$LOG"
python -u scripts/promote_if_pass.py 2>&1 | tee -a "$LOG" || true

echo
echo "DONE. log=$LOG" | tee -a "$LOG"
