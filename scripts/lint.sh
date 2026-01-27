#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

src_dir=""
for d in algonovax AlgoNovaX AlgonovaX; do
  if [ -d "$d" ]; then src_dir="$d"; break; fi
done

test_dir=""
for d in tests test; do
  if [ -d "$d" ]; then test_dir="$d"; break; fi
done

[ -n "$src_dir" ] || { echo "FAIL: missing source dir"; exit 1; }
[ -n "$test_dir" ] || { echo "FAIL: missing tests dir"; exit 1; }

ruff check "$src_dir" "$test_dir"
