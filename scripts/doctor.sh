#!/usr/bin/env bash
set -euo pipefail

REPO="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
cd "$REPO"

echo "== time =="
date
echo

echo "== service status =="
systemctl --user status algonovax.service --no-pager || true
echo

echo "== port 8001 listener =="
sudo lsof -iTCP:8001 -sTCP:LISTEN || true
echo

echo "== /health =="
curl -sS http://127.0.0.1:8001/health || true
echo
echo

echo "== last logs =="
tail -n 80 "$REPO/logs/api.log" 2>/dev/null || true
