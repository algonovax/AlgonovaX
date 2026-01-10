#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://127.0.0.1:${ALGONOVAX_PORT:-8012}/api/status >/dev/null
