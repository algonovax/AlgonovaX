#!/usr/bin/env bash
set -euo pipefail

ex="${EXCHANGE:-}"
if [[ "$ex" != "binanceus" ]]; then
  exit 0
fi

# must have creds for binanceus
: "${BINANCEUS_API_KEY:?missing BINANCEUS_API_KEY}"
: "${BINANCEUS_API_SECRET:?missing BINANCEUS_API_SECRET}"

python scripts/diag/binanceus_auth_smoke.py >/dev/null
