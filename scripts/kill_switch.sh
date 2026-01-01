#!/usr/bin/env bash
set -euo pipefail
KS="${KILL_SWITCH_PATH:-$HOME/projects/AlgonovaX/data/KILL_SWITCH}"
mkdir -p "$(dirname "$KS")"
case "${1:-}" in
  on)
    : > "$KS"
    echo "KILL SWITCH: ON ($KS)"
    ;;
  off)
    rm -f "$KS"
    echo "KILL SWITCH: OFF ($KS)"
    ;;
  status)
    if [ -f "$KS" ]; then
      echo "KILL SWITCH: ON ($KS)"
      exit 0
    fi
    echo "KILL SWITCH: OFF ($KS)"
    exit 1
    ;;
  *)
    echo "Usage: $0 {on|off|status}"
    exit 2
    ;;
esac
