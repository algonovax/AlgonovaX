#!/usr/bin/env bash
set -euo pipefail

ENGINE_SERVICE="${ENGINE_SERVICE:-algonovax-engine.service}"
KS_HARD="${KS_HARD:-${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/KILL_SWITCH}"
KS_SOFT="${KS_SOFT:-${ALGONOVAX_ROOT:-$HOME/AlgonovaX}/data/KILL_SWITCH_SOFT}"

if [[ -f "$KS_HARD" || -f "$KS_SOFT" ]]; then
  systemctl --user stop "$ENGINE_SERVICE" || true
fi
