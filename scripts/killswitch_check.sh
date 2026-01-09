#!/usr/bin/env bash
set -euo pipefail

ENGINE_SERVICE="${ENGINE_SERVICE:-algonovax-engine.service}"
KS_HARD="${KS_HARD:-$HOME/projects/AlgonovaX/data/KILL_SWITCH}"
KS_SOFT="${KS_SOFT:-$HOME/projects/AlgonovaX/data/KILL_SWITCH_SOFT}"

if [[ -f "$KS_HARD" || -f "$KS_SOFT" ]]; then
  systemctl --user stop "$ENGINE_SERVICE" || true
fi
