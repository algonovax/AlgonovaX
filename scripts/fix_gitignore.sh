#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

on_err() {
  local ec=$?
  echo "FIX_GITIGNORE_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  exit "$ec"
}
trap on_err ERR

GI="$ROOT/.gitignore"
TMP="$ROOT/.gitignore.__tmp__.$$"

cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING_CMD: $1" >&2; exit 2; }; }
need awk
need grep
need cat
need rm

[[ -f "$GI" ]] || : > "$GI"

awk '!seen[$0]++ {print}' "$GI" > "$TMP"

ensure() {
  local line="$1"
  grep -qxF "$line" "$TMP" || printf '%s\n' "$line" >> "$TMP"
}

ensure ""
ensure "# ---- local secrets ----"
ensure "config/secrets.env"

ensure ""
ensure "# ---- backups / temp ----"
ensure "*.bak.*"
ensure "*~"
ensure "*.tmp"
ensure "*.log"
ensure "data/"
ensure "scripts/_bak/"
ensure "_quarantine/"

ensure ""
ensure "# ---- python cache/venv ----"
ensure "__pycache__/"
ensure "*.pyc"
ensure ".venv/"

cat "$TMP" > "$GI"

echo "OK: updated .gitignore"
echo "Next: git add .gitignore"
