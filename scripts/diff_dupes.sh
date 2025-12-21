#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/projects/AlgonovaX"

echo "== duplicates check =="
pairs=(
  "exchanges/base.py algonovax/exchanges/base.py"
  "exchanges/paper.py algonovax/exchanges/paper.py"
  "exchanges/kraken.py algonovax/exchanges/kraken.py"
  "exchanges/binance_us.py algonovax/exchanges/binance_us.py"
  "strategies/ema_rsi.py algonovax/strategies/ema_rsi.py"
)

for p in "${pairs[@]}"; do
  a="${p%% *}"
  b="${p##* }"
  echo
  echo "----- $a  vs  $b -----"
  if [ -f "$a" ] && [ -f "$b" ]; then
    diff -u "$a" "$b" | sed -n '1,220p' || true
  else
    echo "(one missing)"
  fi
done

echo
echo "== runner imports =="
python3 - <<'PY'
import ast, pathlib
p = pathlib.Path("runner.py")
if not p.exists():
    print("runner.py missing")
    raise SystemExit(0)
t = ast.parse(p.read_text())
imps=[]
for n in ast.walk(t):
    if isinstance(n, ast.Import):
        imps += [a.name for a in n.names]
    if isinstance(n, ast.ImportFrom):
        imps.append(f"{n.module} (from)")
print("\n".join(sorted(set(imps))))
PY
