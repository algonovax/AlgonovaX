#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

[ -d algonovax ] || { echo "FAIL: missing ./algonovax"; exit 1; }
[ -d tests ] || { echo "FAIL: missing ./tests"; exit 1; }
[ -f .venv/bin/activate ] || { echo "FAIL: missing .venv"; exit 1; }

. .venv/bin/activate

ruff --version
ruff check algonovax tests
pytest -q
