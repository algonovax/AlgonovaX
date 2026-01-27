#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-check}" in
  check)
    ruff check .
    pytest -q
    python -c "import algonovax"
    ;;
  *)
    echo "usage: $0 [check]" >&2
    exit 2
    ;;
esac
