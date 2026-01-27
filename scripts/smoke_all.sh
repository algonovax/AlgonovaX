#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/smoke_engine_killswitch.sh
