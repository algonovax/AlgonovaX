#!/usr/bin/env bash
set -euo pipefail
cd ${ALGONOVAX_ROOT:-$HOME/AlgonovaX}
source .venv/bin/activate
"$@"
