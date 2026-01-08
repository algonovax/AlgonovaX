#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EXCHANGE="${EXCHANGE:-binance}"
MODE="${MODE:-testnet}"   # testnet | live
PY="${PY:-$ROOT/.venv/bin/python}"

REPORT_DIR="$ROOT/data"
REPORT_JSON="$REPORT_DIR/audit_report.json"
mkdir -p "$REPORT_DIR"

# ts prints the current UTC timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# on_err reports the failing exit code, line number, and command plus root, exchange, mode, and python path to stderr, then exits with that code.
on_err() {
  local ec=$?
  echo "AUDIT_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  echo "root=$ROOT exchange=$EXCHANGE mode=$MODE py=$PY" >&2
  exit "$ec"
}
trap on_err ERR

# fail prints an error message prefixed with AUDIT_FAIL to stderr and exits with status 1.
fail() { echo "AUDIT_FAIL: $*" >&2; exit 1; }
# need ensures the named command exists in PATH and calls fail (exiting the script) with an error if it is not found.
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }

echo "== AlgoNovaX LIVE READINESS AUDIT =="
echo "time=$(ts)"
echo "root=$ROOT"
echo "exchange=$EXCHANGE"
echo "mode=$MODE"
echo

need git
need awk
need sed

test -d "$ROOT/.git" || fail "Not a git repo: $ROOT"
test -x "$PY" || fail "Python venv missing/executable not found: $PY"
"$PY" -V || fail "Python not runnable: $PY"

echo "== Gate 0.5: Python deps =="
"$PY" - <<'PY'
import sys
mods = ["ccxt"]
bad=[]
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        bad.append((m, repr(e)))
if bad:
    for m,e in bad:
        print(f"ERR_MISSING {m} {e}", file=sys.stderr)
    raise SystemExit(2)
print("OK")
PY
echo

echo "== Gate 1: Python import sanity =="
"$PY" - <<'PY'
import os, sys, pkgutil, importlib
from pathlib import Path

root = Path(os.getcwd())
pkg = root / "algonovax"
if not pkg.exists():
    print("ERR: missing ./algonovax package dir", file=sys.stderr)
    sys.exit(2)

try:
    import algonovax  # noqa
except Exception as e:
    print(f"ERR: cannot import algonovax: {e!r}", file=sys.stderr)
    sys.exit(3)

errors = []
for m in pkgutil.walk_packages([str(pkg)], prefix="algonovax."):
    try:
        importlib.import_module(m.name)
    except Exception as e:
        errors.append((m.name, repr(e)))

if errors:
    for name, e in errors[:200]:
        print(f"ERR_IMPORT {name} {e}", file=sys.stderr)
    sys.exit(4)

print("OK")
PY
echo

echo "== Gate 2: Required files/dirs =="
req=( "config" "data" "scripts" "algonovax" )
for p in "${req[@]}"; do
  test -e "$ROOT/$p" || fail "Missing required path: $p"
done
echo "OK"
echo

echo "== Gate 3: Kill-switch hooks present =="
git grep -nE "KILL_SWITCH|killswitch|kill switch" -- "algonovax" "scripts" >/dev/null \
  || fail "No kill switch references found in code"
echo "OK"
echo

echo "== Gate 4: Risk guard hooks present =="
git grep -nE "max_daily_loss|maxDailyLoss|daily_loss|circuit_breaker|max_consecutive_losses|max_position|position_limit|notional|minNotional" -- "algonovax" >/dev/null \
  || fail "No risk-guard references found (daily loss / circuit breaker / position limits / notional guards)"
echo "OK"
echo

echo "== Gate 5: Binance adapter path exists =="
git grep -nE "ccxt\.binance|ccxt\.binanceus|binanceus|binance" -- "algonovax" "scripts" >/dev/null \
  || fail "No Binance adapter usage found (ccxt.binance / ccxt.binanceus / binance refs)"
echo "OK"
echo

echo "== Gate 6: Credential env vars (presence only) =="
missing=()
case "$EXCHANGE" in
  binance)
    [[ -n "${BINANCE_API_KEY-}" && -n "${BINANCE_API_SECRET-}" ]] || missing+=(BINANCE_API_KEY BINANCE_API_SECRET)
    ;;
  binanceus|binance_us)
    [[ -n "${BINANCEUS_API_KEY-}" && -n "${BINANCEUS_API_SECRET-}" ]] || missing+=(BINANCEUS_API_KEY BINANCEUS_API_SECRET)
    ;;
  *)
    fail "Unknown EXCHANGE=$EXCHANGE (expected binance or binanceus)"
    ;;
esac
((${#missing[@]}==0)) || fail "Missing credential env vars: ${missing[*]}"
echo "OK"
echo

echo "== Gate 7: Exchange connectivity + market metadata (NO orders) =="
EXCHANGE="$EXCHANGE" MODE="$MODE" "$PY" - <<'PY'
import os, sys
import ccxt

exchange = os.getenv("EXCHANGE", "binance")
mode = os.getenv("MODE", "testnet")

def mk():
    if exchange == "binance":
        ex = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True,
        })
        if hasattr(ex, "set_sandbox_mode") and mode == "testnet":
            ex.set_sandbox_mode(True)
        return ex
    if exchange in ("binanceus","binance_us"):
        return ccxt.binanceus({
            "apiKey": os.getenv("BINANCEUS_API_KEY"),
            "secret": os.getenv("BINANCEUS_API_SECRET"),
            "enableRateLimit": True,
        })
    raise SystemExit(f"Unsupported exchange: {exchange}")

try:
    ex = mk()
    markets = ex.load_markets()
    candidates = ["BTC/USDT", "BTC/USD", "ETH/USDT", "ETH/USD"]
    sym = next((s for s in candidates if s in markets), None)
    if not sym:
        print("ERR: none of candidate symbols found", file=sys.stderr)
        sys.exit(2)
    m = markets[sym]
    print("OK")
    print("symbol", sym)
    print("precision", m.get("precision"))
    print("limits", m.get("limits"))
except Exception as e:
    print(f"ERR: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(3)
PY
echo

echo "== Gate 8: Live trading requires explicit enable flag =="
LIVE_FLAG="$ROOT/config/ENABLE_LIVE_TRADING"
if [[ "$MODE" == "live" ]]; then
  [[ -f "$LIVE_FLAG" ]] || fail "LIVE blocked. Create $LIVE_FLAG"
  val="$(tr -d ' \n\r\t' <"$LIVE_FLAG" 2>/dev/null || true)"
  [[ "$val" == "I_UNDERSTAND_I_CAN_LOSE_MONEY" ]] || fail "LIVE blocked. $LIVE_FLAG must contain: I_UNDERSTAND_I_CAN_LOSE_MONEY"
fi
echo "OK"
echo

cat >"$REPORT_JSON" <<JSON
{
  "time_utc": "$(ts)",
  "root": "$ROOT",
  "exchange": "$EXCHANGE",
  "mode": "$MODE",
  "result": "PASS"
}
JSON

echo "AUDIT_PASS"
echo "WROTE $REPORT_JSON"