#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  run) exec ./scripts/engine_run.sh ;;
  stop) exec ./scripts/engine_stop.sh ;;
  logs) exec tail -f logs/engine.run.log ;;
  smoke) exec ./scripts/smoke_all.sh ;;
  *) echo "usage: $0 {run|stop|logs|smoke}" >&2; exit 2 ;;
esac
