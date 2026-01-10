#!/usr/bin/env bash
set -Eeuo pipefail

host="api.binance.us"

echo "== getent ahosts =="
getent ahosts "$host" | head -n 20 || true
echo

echo "== dig A/AAAA (if installed) =="
if command -v dig >/dev/null 2>&1; then
  dig +short A "$host" || true
  dig +short AAAA "$host" || true
else
  echo "dig not installed (sudo apt-get install -y dnsutils)"
fi
echo
